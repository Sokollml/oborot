"""Воркер кредитного конвейера. Запуск: python -m app.worker

Бесконечный цикл:
  1. взять задачу из очереди (queue.claim_job);
  2. провести заявку по конвейеру (pipeline.process_application);
  3. отметить задачу выполненной — или вернуть в очередь / отметить ошибку.

Остановка (docker compose stop → SIGTERM): дорабатываем текущий этап, возвращаем задачу
в очередь и выходим. После запуска воркер продолжит с того же места.
"""

import logging
import signal
import time

from app.config import settings
from app.db import SessionLocal
from app.enums import AppStatus
from app.models import Application, Job
from app.services.state_machine import Actor, can_transition, transition
from app.worker import queue
from app.worker.pipeline import process_application

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("worker")

_running = True


def _stop(signum, _frame) -> None:
    global _running
    log.info("получен сигнал %s — доделываю текущий этап и останавливаюсь", signum)
    _running = False


def _send_to_manual_review(job: Job) -> None:
    """Задача провалилась окончательно — заявка не должна зависнуть, отдаём её человеку."""
    with SessionLocal() as db, db.begin():
        app: Application | None = db.get(Application, job.application_id, with_for_update=True)
        if app and can_transition(app.status, AppStatus.MANUAL_REVIEW, Actor.system().type):
            transition(db, app, AppStatus.MANUAL_REVIEW, Actor.system(), comment="Техническая ошибка обработки. Заявку проверит специалист.")


def run_once() -> bool:
    """Обработать одну задачу. Возвращает False, если очередь пуста."""
    job = queue.claim_job()
    if job is None:
        return False
    log.info("задача %s: заявка %s (попытка %s)", job.id, job.application_id, job.attempts)
    if job.attempts > settings.job_max_attempts:
        # Попыток больше лимита — значит, процесс воркера уже несколько раз умирал на этой задаче
        # (не исключение, а падение целиком). Не крутим её бесконечно: отдаём заявку человеку.
        queue.fail_job(job.id, "Воркер несколько раз останавливался на этой задаче")
        _send_to_manual_review(job)
        return True
    try:
        completed = process_application(
            job.application_id,
            should_stop=lambda: not _running,
            heartbeat=lambda: queue.extend_lease(job.id),
        )
    except Exception as exc:  # noqa: BLE001 — любую ошибку фиксируем в задаче, воркер продолжает жить
        log.exception("задача %s упала", job.id)
        if queue.fail_job(job.id, f"{type(exc).__name__}: {exc}"):
            _send_to_manual_review(job)
        return True
    if completed:
        queue.finish_job(job.id)
    else:
        queue.release_job(job.id)
        log.info("задача %s возвращена в очередь", job.id)
    return True


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("воркер запущен")
    while _running:
        try:
            if not run_once():
                time.sleep(settings.worker_poll_seconds)
        except Exception:  # база недоступна и т.п. — ждём и пробуем снова
            log.exception("ошибка цикла воркера")
            time.sleep(settings.worker_poll_seconds * 3)
    log.info("воркер остановлен")


if __name__ == "__main__":
    main()

