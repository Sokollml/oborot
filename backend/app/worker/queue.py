"""Очередь задач в PostgreSQL (таблица jobs). Отдельный брокер (Redis, RabbitMQ) не нужен.

Как воркер берёт задачу (claim_job):
    SELECT ... FOR UPDATE SKIP LOCKED
- FOR UPDATE блокирует выбранную строку, чтобы её не взял кто-то ещё;
- SKIP LOCKED говорит «если строка уже занята другим воркером — пропусти её, не жди».
Поэтому можно запустить несколько воркеров, и они никогда не возьмут одну задачу дважды.

Как переживаем падение воркера («аренда» задачи):
- взяв задачу, воркер помечает её running и ставит run_after = сейчас + JOB_LEASE_SECONDS;
- если воркер упал и не отчитался, после истечения аренды задача снова считается свободной,
  и её подхватит следующий запуск воркера;
- при штатной остановке (docker compose stop) воркер сразу возвращает задачу в очередь.
Конвейер возобновляется с того статуса, где остановился (см. pipeline.py).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select

from app.config import settings
from app.db import SessionLocal
from app.enums import JobStatus
from app.models import Job


def _now() -> datetime:
    return datetime.now(UTC)


def claim_job() -> Job | None:
    """Взять одну свободную задачу (или задачу с истёкшей арендой). Возвращает None, если очередь пуста."""
    with SessionLocal() as db, db.begin():
        now = _now()
        job = db.scalar(
            select(Job)
            .where(
                or_(
                    and_(Job.status == JobStatus.PENDING, Job.run_after <= now),
                    and_(Job.status == JobStatus.RUNNING, Job.run_after <= now),  # аренда истекла — воркер упал
                )
            )
            .order_by(Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        job.status = JobStatus.RUNNING
        job.attempts += 1
        job.run_after = now + timedelta(seconds=settings.job_lease_seconds)
        return job


def finish_job(job_id: int) -> None:
    with SessionLocal() as db, db.begin():
        job = db.get(Job, job_id)
        job.status = JobStatus.DONE
        job.last_error = None


def release_job(job_id: int) -> None:
    """Вернуть задачу в очередь сразу (штатная остановка воркера)."""
    with SessionLocal() as db, db.begin():
        job = db.get(Job, job_id)
        job.status = JobStatus.PENDING
        job.run_after = _now()


def fail_job(job_id: int, error: str) -> bool:
    """Ошибка при обработке. Возвращает True, если попытки исчерпаны и задача окончательно провалена."""
    with SessionLocal() as db, db.begin():
        job = db.get(Job, job_id)
        job.last_error = error[:2000]
        if job.attempts >= settings.job_max_attempts:
            job.status = JobStatus.FAILED
            return True
        job.status = JobStatus.PENDING
        job.run_after = _now() + timedelta(seconds=5 * job.attempts)  # пауза растёт с каждой попыткой
        return False
