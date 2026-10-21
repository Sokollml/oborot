"""Воркер кредитного конвейера. Запуск: python -m app.worker

Сейчас (фаза 0) это только «пульс»: проверяет базу и пишет в лог.
В фазе 2 здесь появится обработка очереди задач из таблицы jobs.
"""

import logging
import signal
import time

from sqlalchemy import text

from app.config import settings
from app.db import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s worker: %(message)s")
log = logging.getLogger("worker")

_running = True


def _stop(signum, _frame) -> None:
    # docker compose stop присылает SIGTERM — аккуратно выходим из цикла.
    global _running
    log.info("получен сигнал %s, останавливаюсь", signum)
    _running = False


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("воркер запущен")
    while _running:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        time.sleep(settings.worker_poll_seconds)
    log.info("воркер остановлен")


if __name__ == "__main__":
    main()
