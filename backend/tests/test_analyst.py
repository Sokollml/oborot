"""Кабинет специалиста и документы: сценарии 3, 5, 6 до конца, права доступа, загрузка файлов."""

from sqlalchemy import select

from app.models import Notification
from app.worker.__main__ import run_once
from tests.scenarios import SCENARIOS
from tests.test_pipeline import run_scenario

PDF = b"%PDF-1.4\n% demo statement\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def upload(client, app_id: int, content: bytes, name: str = "statement.pdf"):
    doc_id = client.get(f"/api/applications/{app_id}").json()["documents"][-1]["id"]
    return client.post(
        f"/api/applications/{app_id}/documents",
        data={"document_request_id": str(doc_id)},
        files={"file": (name, content, "application/octet-stream")},
    )


def decide(analyst, app_id: int, **body):
    return analyst.post(f"/api/analyst/applications/{app_id}/decision", json=body)


def test_client_has_no_access_to_analyst_cabinet(client1):
    assert client1.get("/api/analyst/queue").status_code == 403
    assert client1.get("/api/analyst/applications/1").status_code == 403


def test_scenario_5_invest_manual_approve(client1, analyst, db):
    app_id = run_scenario(client1, SCENARIOS["5_techno"])

    # В очереди «ждут меня» и с классом риска
    queue = analyst.get("/api/analyst/queue").json()
    item = next(q for q in queue if q["id"] == app_id)
    assert item["status"] == "MANUAL_REVIEW" and item["risk_class"] == "A"

    # Специалисту пришло уведомление
    assert db.scalar(select(Notification).where(Notification.user_id == 3, Notification.application_id == app_id))

    card = analyst.get(f"/api/analyst/applications/{app_id}").json()
    assert {c["source"] for c in card["checks"]} == {"egrul", "fns", "bki", "account"}
    assert all(c["level"] == "ok" for c in card["checks"])
    assert len(card["scoring"]["factors"]) == 7
    rec = card["recommendation"]
    assert rec["action"] == "approve" and rec["amount"] == 20_000_000
    assert card["available_actions"] == ["approve", "request_docs", "reject"]

    # Без комментария нельзя
    r = decide(analyst, app_id, action="approve", amount=20_000_000, term_months=48, rate=18.0, comment=" ")
    assert r.status_code == 422

    r = decide(analyst, app_id, action="approve", amount=20_000_000, term_months=48, rate=18.0, comment="Залог ликвидный, риск низкий")
    assert r.status_code == 200, r.text
    assert r.json()["application"]["status"] == "OFFER"

    client_view = client1.get(f"/api/applications/{app_id}").json()
    assert client_view["decision"]["type"] == "approve"
    assert client_view["decision"]["made_by"] == "analyst"
    assert client_view["decision"]["reasons"] == ["Залог ликвидный, риск низкий"]


def test_scenario_3_documents_then_manual_counter(client1, analyst):
    app_id = run_scenario(client1, SCENARIOS["3_vector"])
    app = client1.get(f"/api/applications/{app_id}").json()
    assert app["status"] == "INFO_REQUESTED"
    assert app["documents"][0]["doc_type"] == "bank_statement"

    # Плохие файлы — понятные ошибки
    r = upload(client1, app_id, b"just text")
    assert r.status_code == 422 and "PDF, JPG или PNG" in r.json()["detail"]
    r = upload(client1, app_id, PDF + b"0" * (10 * 1024 * 1024))
    assert r.status_code == 422 and "10 МБ" in r.json()["detail"]

    # Нормальная выписка → заявка снова на проверке
    r = upload(client1, app_id, PDF)
    assert r.status_code == 200 and r.json()["status"] == "CHECKING"
    assert r.json()["documents"][0]["status"] == "uploaded"

    assert run_once() is True
    assert client1.get(f"/api/applications/{app_id}").json()["status"] == "MANUAL_REVIEW"  # без нового запроса документов

    card = analyst.get(f"/api/analyst/applications/{app_id}").json()
    rec = card["recommendation"]
    assert rec["action"] == "counter" and rec["amount"] == 7_000_000

    doc_id = card["application"]["documents"][0]["id"]
    download = analyst.get(f"/api/analyst/documents/{doc_id}")
    assert download.status_code == 200 and download.content == PDF
    assert client1.get(f"/api/analyst/documents/{doc_id}").status_code == 403

    r = decide(analyst, app_id, action="approve", amount=rec["amount"], term_months=24, rate=rec["rate"], comment="Выписка подтверждает выручку, снижаем сумму")
    assert r.json()["application"]["status"] == "OFFER"
    decision = client1.get(f"/api/applications/{app_id}").json()["decision"]
    assert decision["type"] == "counter" and decision["amount"] == 7_000_000

    # Клиент принимает и подписывает
    code = client1.post(f"/api/applications/{app_id}/offer/accept").json()["signing_code"]
    assert client1.post(f"/api/applications/{app_id}/sign", json={"code": code}).json()["status"] == "ISSUED"


def test_scenario_6_analyst_requests_docs_rejects_and_overrides(client1, analyst):
    app_id = run_scenario(client1, SCENARIOS["6_tishina"])
    card = analyst.get(f"/api/analyst/applications/{app_id}").json()
    bki = next(c for c in card["checks"] if c["source"] == "bki")
    assert bki["level"] == "bad" and not bki["ok"]
    assert card["scoring"] is None
    assert card["recommendation"]["action"] == "request_docs"

    r = decide(analyst, app_id, action="request_docs", doc_types=["bank_statement", "financial_report"], comment="БКИ недоступно, проверим по документам")
    assert r.json()["application"]["status"] == "INFO_REQUESTED"
    assert len(r.json()["application"]["documents"]) == 2

    # Пока загружен один из двух — ждём второй
    docs = client1.get(f"/api/applications/{app_id}").json()["documents"]
    first = client1.post(
        f"/api/applications/{app_id}/documents",
        data={"document_request_id": str(docs[0]["id"])},
        files={"file": ("a.pdf", PDF, "application/pdf")},
    )
    assert first.json()["status"] == "INFO_REQUESTED"
    second = client1.post(
        f"/api/applications/{app_id}/documents",
        data={"document_request_id": str(docs[1]["id"])},
        files={"file": ("b.png", PNG, "image/png")},
    )
    assert second.json()["status"] == "CHECKING"
    run_once()
    assert client1.get(f"/api/applications/{app_id}").json()["status"] == "MANUAL_REVIEW"

    r = decide(analyst, app_id, action="reject", client_reason="Не удалось подтвердить кредитную историю", comment="Отказ: нет данных БКИ")
    assert r.json()["application"]["status"] == "REJECTED"
    assert client1.get(f"/api/applications/{app_id}").json()["decision"]["reasons"] == ["Не удалось подтвердить кредитную историю"]

    # Специалист передумал — отменяет отказ
    assert r.json()["available_actions"] == ["approve"]
    r = decide(analyst, app_id, action="approve", amount=1_000_000, term_months=12, rate=26.0, comment="Клиент принёс справку из БКИ, история чистая")
    assert r.json()["application"]["status"] == "OFFER"


def test_analyst_cannot_decide_while_checking(client1, analyst):
    from tests.helpers import create_draft, submit

    app_id = create_draft(client1)
    submit(client1, app_id)
    r = decide(analyst, app_id, action="reject", comment="рано")
    assert r.status_code == 409


def test_approve_validates_product_limits(client1, analyst):
    app_id = run_scenario(client1, SCENARIOS["5_techno"])
    r = decide(analyst, app_id, action="approve", amount=90_000_000, term_months=48, rate=18.0, comment="ok")
    assert r.status_code == 422 and "Сумма" in r.json()["detail"]


def test_queue_filters(client1, analyst):
    run_scenario(client1, SCENARIOS["5_techno"])
    run_scenario(client1, SCENARIOS["1_romashka"])
    assert {q["status"] for q in analyst.get("/api/analyst/queue").json()} == {"MANUAL_REVIEW"}
    assert len(analyst.get("/api/analyst/queue", params={"view": "all"}).json()) == 2
    assert analyst.get("/api/analyst/queue", params={"view": "all", "product": "EXPRESS"}).json()[0]["product_code"] == "EXPRESS"
    assert analyst.get("/api/analyst/queue", params={"status": "OFFER"}).json()[0]["status"] == "OFFER"


def test_upload_not_allowed_outside_info_requested(client1):
    app_id = run_scenario(client1, SCENARIOS["1_romashka"])
    r = client1.post(
        f"/api/applications/{app_id}/documents",
        data={"document_request_id": "1"},
        files={"file": ("a.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 409
