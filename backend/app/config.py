"""Настройки приложения.

Все значения читаются из переменных окружения (список и описание — в .env.example).
Значения по умолчанию подходят для локального запуска без Docker.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+psycopg://stupeni:stupeni@localhost:5432/stupeni"
    mock_external_url: str = "http://localhost:8001"

    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"
    jwt_ttl_minutes: int = 60 * 12

    # Демо-режим: подсказка с тестовыми аккаунтами на экране входа.
    demo_mode: bool = True
    # Пароль тестовых аккаунтов (создаются при первом запуске).
    demo_password: str = "demo12345"

    # Воркер: пауза между этапами конвейера (чтобы на демо было видно движение статуса)
    # и частота опроса очереди задач.
    stage_delay_seconds: float = 2.0
    worker_poll_seconds: float = 1.0

    # Внешние сервисы: таймаут одного запроса, число попыток и пауза между ними.
    external_timeout_seconds: float = 3.0
    external_retries: int = 3
    external_retry_pause_seconds: float = 1.0

    upload_dir: str = "/data/uploads"


settings = Settings()
