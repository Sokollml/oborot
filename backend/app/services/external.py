"""Клиент внешних сервисов (ЕГРЮЛ, ФНС, БКИ). В проекте за ними стоит наш мок-сервис.

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
}


class ExternalServiceError(Exception):
    """Сервис не ответил после всех попыток."""


class CompanyNotFoundInRegistry(Exception):
    """Сервис ответил, но такой компании у него нет (повторять бессмысленно)."""


def fetch(source: CheckSource, inn: str) -> dict[str, Any]:
    url = f"{settings.mock_external_url}/{source}/{inn}"
    last_error = ""
    for attempt in range(1, settings.external_retries + 1):
        try:
            response = httpx.get(url, timeout=settings.external_timeout_seconds)
            if response.status_code == 404:
                raise CompanyNotFoundInRegistry(inn)
            response.raise_for_status()
            return response.json()
        except CompanyNotFoundInRegistry:
            raise
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            log.warning("%s: попытка %s/%s не удалась (%s)", source, attempt, settings.external_retries, last_error)
            if attempt < settings.external_retries:
                time.sleep(settings.external_retry_pause_seconds)
    raise ExternalServiceError(f"{SOURCE_NAMES[source]} не отвечает: {last_error}")
