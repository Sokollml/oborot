"""Общая настройка тестов.

Тестам нужен PostgreSQL. По умолчанию берётся база из docker compose (порт 5433 на хосте):
    docker compose up -d db && cd backend && uv run pytest
Другой адрес можно задать через TEST_DATABASE_URL. База stupeni_test создаётся автоматически.

Внешние сервисы (ЕГРЮЛ/ФНС/БКИ) в тестах не вызываются по сети: fetch() подменяется
на чтение тех же синтетических данных, что лежат в mock-external.
"""

import importlib.util
import os
from pathlib import Path

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://stupeni:stupeni@localhost:5433/stupeni_test"
)
# Важно: до импорта app.* — движок БД создаётся при импорте.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("STAGE_DELAY_SECONDS", "0")
os.environ.setdefault("EXTERNAL_RETRY_PAUSE_SECONDS", "0")
os.environ["MOCK_DELAY_SECONDS"] = "0"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.enums import CheckSource  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.seed import seed  # noqa: E402
from app.services import external  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
MOCK_MAIN = BACKEND_DIR.parent / "mock-external" / "app" / "main.py"


def _ensure_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database():
    _ensure_database()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Перед каждым тестом — пустая база с продуктами и тестовыми пользователями."""
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    with SessionLocal() as db:
        seed(db)
    yield


def _load_mock_module():
    spec = importlib.util.spec_from_file_location("mock_external_main", MOCK_MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mock = _load_mock_module()
_mock_client = TestClient(_mock.app)


def fake_fetch(source: CheckSource, inn: str) -> dict:
    """Ответ мок-сервиса без сети. «Зависший» БКИ сразу даёт ошибку, как после всех повторов."""
    company = _mock.COMPANIES.get(inn)
    if company and source == CheckSource.BKI and company.get("bki_timeout"):
        raise external.ExternalServiceError("бюро кредитных историй (БКИ) не отвечает: timeout")
    response = _mock_client.get(f"/{source}/{inn}")
    if response.status_code == 404:
        raise external.CompanyNotFoundInRegistry(inn)
    return response.json()


@pytest.fixture(autouse=True)
def _fake_external(monkeypatch):
    monkeypatch.setattr(external, "fetch", fake_fetch)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def login(email: str) -> TestClient:
    client = TestClient(app)
    r = client.post("/api/auth/login", json={"email": email, "password": "demo12345"})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def client1() -> TestClient:
    return login("client1@demo.local")


@pytest.fixture
def client2() -> TestClient:
    return login("client2@demo.local")


@pytest.fixture
def analyst() -> TestClient:
    return login("analyst@demo.local")
