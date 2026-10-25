"""Клиент внешних сервисов (ЕГРЮЛ, ФНС, БКИ) и АБС банка (обороты по счёту). В проекте за ними стоит наш мок-сервис.

Надёжность: каждый запрос ограничен таймаутом (EXTERNAL_TIMEOUT_SECONDS, по умолчанию 3 с),
при сбое делаем повтор с паузой — всего EXTERNAL_RETRIES попыток (по умолчанию 3).
Если сервис так и не ответил — ExternalServiceError, и воркер отправит заявку специалисту,
а не оставит её «висеть».
"""

import logging
import time
from typing import Any

import httpx

from app.config import settings
from app.enums import CheckSource

log = logging.getLogger(__name__)

SOURCE_NAMES = {
    CheckSource.EGRUL: "реестр юрлиц (ЕГРЮЛ)",
    CheckSource.FNS: "налоговая (ФНС)",
    CheckSource.BKI: "бюро кредитных историй (БКИ)",
    CheckSource.ACCOUNT: "расчётный счёт в банке",
}
PATHS = {
    CheckSource.EGRUL: "egrul",
    CheckSource.FNS: "fns",
    CheckSource.BKI: "bki",
    CheckSource.ACCOUNT: "abs/accounts",
}


class ExternalServiceError(Exception):
    """Сервис не ответил после всех попыток."""


class CompanyNotFoundInRegistry(Exception):
    """Сервис ответил, но такой компании у него нет (повторять бессмысленно)."""


def fetch(source: CheckSource, inn: str, *, retries: int | None = None, timeout: float | None = None) -> dict[str, Any]:
    url = f"{settings.mock_external_url}/{PATHS[source]}/{inn}"
    retries = retries or settings.external_retries
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            response = httpx.get(url, timeout=timeout or settings.external_timeout_seconds)
            if response.status_code == 404:
                raise CompanyNotFoundInRegistry(inn)
            response.raise_for_status()
            return response.json()
        except CompanyNotFoundInRegistry:
            raise
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            log.warning("%s: попытка %s/%s не удалась (%s)", source, attempt, retries, last_error)
            if attempt < retries:
                time.sleep(settings.external_retry_pause_seconds)
    raise ExternalServiceError(f"{SOURCE_NAMES[source]} не отвечает: {last_error}")
