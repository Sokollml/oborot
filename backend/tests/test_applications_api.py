"""API заявок: доступ к чужим заявкам, идемпотентность отправки, 409 на недопустимые действия."""

from sqlalchemy import func, select

from app.models import Job
from tests.helpers import create_draft, submit


def test_other_client_gets_403(client1, client2):
    app_id = create_draft(client1)
    for method, path in [
        ("get", f"/api/applications/{app_id}"),
        ("get", f"/api/applications/{app_id}/history"),
        ("patch", f"/api/applications/{app_id}"),
        ("post", f"/api/applications/{app_id}/cancel"),
    ]:
        r = getattr(client2, method)(path, **({"json": {}} if method == "patch" else {}))
        assert r.status_code == 403, (path, r.text)
    assert submit(client2, app_id).status_code == 403


def test_my_list_contains_only_my_applications(client1, client2):
    create_draft(client1)
    create_draft(client2, inn="001000001006")
    assert len(client1.get("/api/applications").json()) == 1
    assert client2.get("/api/applications").json()[0]["company_name"] == "ИП Тестов Тест Тестович"


def test_submit_is_idempotent(client1, db):
    app_id = create_draft(client1)
    first = submit(client1, app_id, key="same-key-123")
    second = submit(client1, app_id, key="same-key-123")
    assert first.status_code == second.status_code == 200
    assert second.json()["status"] == "SUBMITTED"
    # Ровно одна задача для воркера, а не две.
    assert db.scalar(select(func.count()).select_from(Job).where(Job.application_id == app_id)) == 1


def test_submit_again_with_new_key_is_409(client1):
    app_id = create_draft(client1)
    assert submit(client1, app_id).status_code == 200
    r = submit(client1, app_id)
    assert r.status_code == 409
    assert "уже отправлена" in r.json()["detail"]


def test_submit_requires_idempotency_key(client1):
    app_id = create_draft(client1)
    assert client1.post(f"/api/applications/{app_id}/submit").status_code == 422


def test_incomplete_draft_explains_what_is_missing(client1):
    r = client1.post("/api/applications", json={"product_code": "INVEST", "inn": "0010000049", "purpose": "equipment"})
    app_id = r.json()["id"]
    r = submit(client1, app_id)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "сумму" in detail and "залог" in detail and "согласие" in detail


def test_amount_outside_product_limits(client1):
    app_id = create_draft(client1, amount=5_000_000)  # EXPRESS — до 3 млн
    r = submit(client1, app_id)
    assert r.status_code == 422 and "3 000 000 ₽" in r.json()["detail"]


def test_patch_after_submit_is_409(client1):
    app_id = create_draft(client1)
    submit(client1, app_id)
    assert client1.patch(f"/api/applications/{app_id}", json={"amount": 1_000_000}).status_code == 409


def test_actions_in_wrong_status_are_409(client1):
    app_id = create_draft(client1)
    assert client1.post(f"/api/applications/{app_id}/offer/accept").status_code == 409
    assert client1.post(f"/api/applications/{app_id}/sign", json={"code": "000000"}).status_code == 409
    submit(client1, app_id)
    assert client1.post(f"/api/applications/{app_id}/cancel").status_code == 409


def test_cancel_draft(client1):
    app_id = create_draft(client1)
    r = client1.post(f"/api/applications/{app_id}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"


def test_inn_errors_are_human(client1):
    r = client1.get("/api/companies/lookup", params={"inn": "123"})
    assert r.status_code == 422 and "10 цифр" in r.json()["detail"]
    r = client1.get("/api/companies/lookup", params={"inn": "0010000018"})
    assert r.status_code == 422 and "контрольная" in r.json()["detail"]
    r = client1.get("/api/companies/lookup", params={"inn": "0010000994"})  # верный формат, но нет в реестре
    assert r.status_code == 404


def test_requires_login():
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).get("/api/applications").status_code == 401


def test_clone_after_cancel_copies_form(client1):
    app_id = create_draft(client1, amount=1_500_000)
    assert client1.post(f"/api/applications/{app_id}/clone").status_code == 409  # черновик клонировать незачем
    client1.post(f"/api/applications/{app_id}/cancel")
    r = client1.post(f"/api/applications/{app_id}/clone")
    assert r.status_code == 201
    new = r.json()
    assert new["id"] != app_id and new["status"] == "DRAFT"
    assert new["amount"] == 1_500_000 and new["revenue_12m"] == 30_000_000
    assert new["bki_consent"] is False


def test_notifications(client1, client2):
    app_id = create_draft(client1)
    submit(client1, app_id)
    body = client1.get("/api/notifications").json()
    assert body["unread_count"] == 1 and "отправлена" in body["items"][0]["text"]
    note_id = body["items"][0]["id"]
    assert client2.post(f"/api/notifications/{note_id}/read").status_code == 404  # чужое уведомление
    assert client1.post(f"/api/notifications/{note_id}/read").status_code == 204
    assert client1.get("/api/notifications").json()["unread_count"] == 0
