"""Крайние случаи: гонка «специалист меняет условия — клиент принимает», внутренние комментарии,
подбор пароля, задача, на которой воркер падает целиком."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.enums import JobStatus
from app.main import app
from app.models import Job
from app.worker.__main__ import run_once
from tests.helpers import create_draft, submit
from tests.scenarios import SCENARIOS
from tests.test_analyst import decide
from tests.test_pipeline import run_scenario


def test_client_cannot_accept_offer_changed_by_analyst(client1, analyst):
    """Клиент смотрел на одни условия, а специалист успел их поменять — принять старые нельзя."""
    app_id = run_scenario(client1, SCENARIOS["1_romashka"])
    seen = client1.get(f"/api/applications/{app_id}").json()["decision"]["id"]

    r = decide(analyst, app_id, action="approve", amount=1_500_000, term_months=12, rate=24.0, comment="Снизили сумму")
    assert r.json()["application"]["status"] == "OFFER"

    stale = client1.post(f"/api/applications/{app_id}/offer/accept", json={"decision_id": seen})
    assert stale.status_code == 409 and "изменились" in stale.json()["detail"]

    current = client1.get(f"/api/applications/{app_id}").json()["decision"]
    assert current["id"] != seen and current["amount"] == 1_500_000
    ok = client1.post(f"/api/applications/{app_id}/offer/accept", json={"decision_id": current["id"]})
    assert ok.json()["status"] == "SIGNING"


def test_accept_without_version_still_works(client1):
    """Старые клиенты API (без decision_id) принимают текущее предложение, как раньше."""
    app_id = run_scenario(client1, SCENARIOS["1_romashka"])
    assert client1.post(f"/api/applications/{app_id}/offer/accept").json()["status"] == "SIGNING"


def test_internal_reject_comment_is_hidden_from_client(client1, analyst):
    app_id = run_scenario(client1, SCENARIOS["6_tishina"])
    decide(analyst, app_id, action="reject", client_reason="Не удалось проверить кредитную историю", comment="Внутреннее: подозрение на дробление")

    history = client1.get(f"/api/applications/{app_id}/history").json()
    assert history[-1]["to_status"] == "REJECTED" and history[-1]["comment"] is None
    assert all("дробление" not in (h["comment"] or "") for h in history)
    assert client1.get(f"/api/applications/{app_id}").json()["decision"]["reasons"] == ["Не удалось проверить кредитную историю"]


def test_login_is_throttled_after_many_failures(client1):
    guest = TestClient(app)
    for _ in range(10):
        assert guest.post("/api/auth/login", json={"email": "guess@demo.local", "password": "wrong"}).status_code == 401
    r = guest.post("/api/auth/login", json={"email": "guess@demo.local", "password": "wrong"})
    assert r.status_code == 429 and "5 минут" in r.json()["detail"]
    # Другие пользователи входят как обычно
    assert guest.post("/api/auth/login", json={"email": "client2@demo.local", "password": settings.demo_password}).status_code == 200


def test_job_that_keeps_killing_worker_goes_to_specialist(client1, db):
    """Процесс воркера умирал на задаче (не исключение — падение целиком) больше лимита попыток:
    задача не крутится вечно, заявку получает специалист."""
    app_id = create_draft(client1)
    submit(client1, app_id)
    job = db.scalar(select(Job).where(Job.application_id == app_id))
    job.status = JobStatus.RUNNING
    job.attempts = settings.job_max_attempts
    job.run_after = datetime.now(UTC) - timedelta(seconds=1)  # аренда истекла
    db.commit()

    assert run_once() is True
    db.expire_all()
    assert db.get(Job, job.id).status == JobStatus.FAILED
    assert client1.get(f"/api/applications/{app_id}").json()["status"] == "MANUAL_REVIEW"


def test_logout_revokes_token_on_server():
    """Выход отзывает токен: сохранённая копия cookie больше не открывает кабинет."""
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": "client1@demo.local", "password": settings.demo_password}).status_code == 200
    stolen = c.cookies.get("access_token")
    assert c.get("/api/auth/me").status_code == 200

    assert c.post("/api/auth/logout").status_code == 204
    replay = TestClient(app)
    replay.cookies.set("access_token", stolen)
    assert replay.get("/api/auth/me").status_code == 401
    # Новый вход выдаёт новый токен — он работает
    assert c.post("/api/auth/login", json={"email": "client1@demo.local", "password": settings.demo_password}).status_code == 200
    assert c.get("/api/auth/me").status_code == 200


def test_cookie_is_secure_behind_https_proxy():
    c = TestClient(app)
    body = {"email": "client2@demo.local", "password": settings.demo_password}
    plain = c.post("/api/auth/login", json=body)
    assert "secure" not in plain.headers["set-cookie"].lower()  # локальный http-стенд — cookie обычная
    https = c.post("/api/auth/login", json=body, headers={"X-Forwarded-Proto": "https"})
    assert "secure" in https.headers["set-cookie"].lower()
