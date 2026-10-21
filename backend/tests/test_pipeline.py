"""Конвейер целиком: сценарии 1–6 через API + воркер, и надёжность очереди."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.enums import JobStatus
from app.models import Job, Scoring
from app.worker import queue
from app.worker.__main__ import run_once
from app.worker.pipeline import process_application
from tests.helpers import create_draft, submit
from tests.scenarios import SCENARIOS, form


def run_scenario(client, scenario: dict) -> int:
    f = form(scenario)
    app_id = create_draft(
        client,
        inn=f.pop("inn"),
        product=f.pop("product"),
        amount=f.pop("amount"),
        term=f.pop("term"),
        purpose=f.pop("purpose"),
        **f,
    )
    assert submit(client, app_id).status_code == 200
    assert run_once() is True  # воркер забрал задачу и провёл заявку по конвейеру
    return app_id


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_scenario_reaches_expected_status(name, client1, db):
    sc = SCENARIOS[name]
    app_id = run_scenario(client1, sc)

    body = client1.get(f"/api/applications/{app_id}").json()
    assert body["status"] == sc["expect_status"], body

    scoring = db.scalar(select(Scoring).where(Scoring.application_id == app_id))
    if sc["expect_class"]:
        assert scoring.risk_class == sc["expect_class"], scoring.factors
    decision = body["decision"]
    if sc["expect_decision"]:
        assert decision["type"] == sc["expect_decision"]
        assert decision["reasons"], "у решения должны быть понятные причины"
    else:
        assert decision is None
    if sc.get("expect_amount"):
        assert decision["amount"] == sc["expect_amount"]


def test_scenario_1_full_happy_path(client1):
    """Ромашка: одобрение → принять → подписать кодом → деньги зачислены."""
    app_id = run_scenario(client1, SCENARIOS["1_romashka"])
    r = client1.post(f"/api/applications/{app_id}/offer/accept")
    assert r.json()["status"] == "SIGNING"
    code = r.json()["signing_code"]
    assert len(code) == 6
    assert client1.post(f"/api/applications/{app_id}/sign", json={"code": "000000" if code != "000000" else "111111"}).status_code == 422
    r = client1.post(f"/api/applications/{app_id}/sign", json={"code": code})
    assert r.json()["status"] == "ISSUED"
    assert r.json()["next_action"]["title"] == "Деньги зачислены"

    timeline = [h["to_status"] for h in client1.get(f"/api/applications/{app_id}/history").json()]
    assert timeline == ["DRAFT", "SUBMITTED", "CHECKING", "SCORING", "OFFER", "SIGNING", "ISSUED"]

    loans = client1.get("/api/loans").json()
    assert [loan["id"] for loan in loans] == [app_id] and loans[0]["decision"]["amount"] == 2_000_000


def test_scenario_4_rejection_explains_why(client1):
    app_id = run_scenario(client1, SCENARIOS["4_zakat"])
    decision = client1.get(f"/api/applications/{app_id}").json()["decision"]
    assert "ликвидации" in decision["reasons"][0]
    assert decision["advice"]


def test_scenario_6_unavailable_bureau_goes_to_manual_review(client1):
    app_id = run_scenario(client1, SCENARIOS["6_tishina"])
    history = client1.get(f"/api/applications/{app_id}/history").json()
    assert history[-1]["to_status"] == "MANUAL_REVIEW"
    assert "БКИ" in history[-1]["comment"]


# ---------- Надёжность очереди ----------


def test_empty_queue():
    assert run_once() is False


def test_worker_picks_up_job_after_crash(client1, db):
    """Воркер взял задачу и «упал» — после истечения аренды задачу подхватывает следующий запуск."""
    app_id = create_draft(client1)
    submit(client1, app_id)

    job = queue.claim_job()  # первый воркер взял задачу…
    assert job is not None
    assert queue.claim_job() is None  # …и пока аренда действует, второй её не видит

    # «Время прошло»: аренда истекла, а первый воркер так и не отчитался.
    db.get(Job, job.id).run_after = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert run_once() is True
    assert client1.get(f"/api/applications/{app_id}").json()["status"] == "OFFER"
    db.expire_all()
    finished = db.get(Job, job.id)
    assert finished.status == JobStatus.DONE and finished.attempts == 2


def test_stopped_worker_resumes_from_current_status(client1):
    """Штатная остановка посреди конвейера: этапы не повторяются, заявка доходит до конца."""
    app_id = create_draft(client1)
    submit(client1, app_id)

    calls = iter([False, True])  # сделать один этап и «получить SIGTERM»
    assert process_application(app_id, should_stop=lambda: next(calls, True)) is False
    assert client1.get(f"/api/applications/{app_id}").json()["status"] == "CHECKING"

    assert process_application(app_id) is True
    history = [h["to_status"] for h in client1.get(f"/api/applications/{app_id}/history").json()]
    assert history == ["DRAFT", "SUBMITTED", "CHECKING", "SCORING", "OFFER"]  # без повторов
