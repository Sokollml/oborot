"""Возможности «своего» банка: обороты по счёту, предодобренный лимит, переписка по заявке."""

from sqlalchemy import select

from app.models import Company, Notification
from tests.helpers import create_draft, submit
from tests.scenarios import SCENARIOS
from tests.test_pipeline import run_scenario


def company_id(db, inn: str) -> int:
    return db.scalar(select(Company.id).where(Company.inn == inn, Company.owner_user_id == 1))


def potential(client, cid: int, consent: bool = True):
    return client.post(f"/api/companies/{cid}/potential", json={"consent": consent})


# ---------- Выручка из оборотов по счёту ----------


def test_revenue_prefilled_for_bank_client(client1):
    r = client1.post("/api/applications", json={"product_code": "EXPRESS", "inn": "0010000017", "purpose": "urgent"})
    app = r.json()
    assert app["revenue_prefilled"] is True
    assert (app["revenue_12m"], app["revenue_prev_year"]) == (30_000_000, 26_000_000)


def test_no_prefill_without_account(client1):
    app = client1.post("/api/applications", json={"product_code": "WORKING", "inn": "0010000024", "purpose": "stock_salary"}).json()
    assert app["revenue_prefilled"] is False and app["revenue_12m"] is None


def test_analyst_sees_revenue_vs_turnover(client1, analyst):
    sc = dict(SCENARIOS["5_techno"], revenue_12m=200_000_000)  # заявили больше, чем видно по счёту
    app_id = run_scenario(client1, sc)
    checks = {c["source"]: c for c in analyst.get(f"/api/analyst/applications/{app_id}").json()["checks"]}
    declared = next(line for line in checks["account"]["lines"] if line["label"] == "Заявлено в анкете")
    assert declared["level"] == "bad" and "+67%" in declared["value"]


# ---------- Предодобренный лимит ----------


def test_potential_requires_consent(client1, db):
    create_draft(client1)
    assert potential(client1, company_id(db, "0010000017"), consent=False).status_code == 422


def test_potential_for_good_client(client1, db):
    create_draft(client1)
    body = potential(client1, company_id(db, "0010000017")).json()["potential"]
    assert body["status"] == "ok"
    offers = {o["product_code"]: o for o in body["offers"]}
    assert offers["EXPRESS"]["amount"] == 3_000_000  # весь лимит продукта
    assert 13_000_000 <= offers["WORKING"]["amount"] < 15_000_000  # упирается в долговую нагрузку
    assert body["max_amount"] == offers["WORKING"]["amount"]
    assert body["drivers"] and body["tips"]
    # Сохранилось и видно в списке компаний
    listed = next(c for c in client1.get("/api/companies").json() if c["inn"] == "0010000017")
    assert listed["potential"]["max_amount"] == body["max_amount"] and listed["potential"]["calculated_at"]


def test_potential_limited_by_overdue(client2, db):
    create_draft(client2, inn="001000001006")
    cid = db.scalar(select(Company.id).where(Company.inn == "001000001006"))
    body = potential(client2, cid).json()["potential"]
    offers = {o["product_code"]: o["amount"] for o in body["offers"]}
    # Просрочка 15 дней не даёт класс A на крупную сумму: лимит меньше 2 млн, о которых просит сценарий 2
    assert body["status"] == "ok" and offers["EXPRESS"] == 900_000 and body["max_amount"] < 2_000_000
    assert any("без просрочек" in t for t in body["tips"])


def test_potential_other_statuses(client1, db):
    for inn in ("0010000024", "0010000056", "0010000063"):
        client1.post("/api/applications", json={"product_code": "EXPRESS", "inn": inn, "purpose": "urgent"})
    assert potential(client1, company_id(db, "0010000024")).json()["potential"]["status"] == "no_account"
    assert potential(client1, company_id(db, "0010000056")).json()["potential"]["status"] == "unavailable"
    young = potential(client1, company_id(db, "0010000063")).json()["potential"]
    assert young["status"] == "none" and "6 месяцев" in young["text"]


def test_potential_of_other_client_company_is_404(client1, client2, db):
    create_draft(client1)
    assert potential(client2, company_id(db, "0010000017")).status_code == 404


# ---------- Переписка ----------


def test_messages_between_client_and_analyst(client1, client2, analyst, db):
    app_id = create_draft(client1)
    assert client1.post(f"/api/applications/{app_id}/messages", json={"text": "Вопрос"}).status_code == 409  # черновик
    submit(client1, app_id)

    r = client1.post(f"/api/applications/{app_id}/messages", json={"text": "Нужна ли выписка?"})
    assert r.status_code == 200 and r.json()[0]["author_role"] == "client"
    assert db.scalar(select(Notification).where(Notification.user_id == 3, Notification.text.like("Клиент написал%")))

    r = analyst.post(f"/api/analyst/applications/{app_id}/messages", json={"text": "Нет, обороты по счёту видим"})
    assert [m["author_role"] for m in r.json()] == ["client", "analyst"]
    assert r.json()[1]["author_name"] == "Мария Петрова"
    assert any("Специалист ответил" in n["text"] for n in client1.get("/api/notifications").json()["items"])

    assert client2.get(f"/api/applications/{app_id}/messages").status_code == 403
    assert client1.get(f"/api/applications/{app_id}/messages").json()[1]["text"] == "Нет, обороты по счёту видим"


def test_potential_tips_are_relevant(client1, db):
    create_draft(client1)
    body = potential(client1, company_id(db, "0010000017")).json()["potential"]
    # У «Ромашки» нет налогового долга и массового адреса — таких советов быть не должно
    assert not any("налоговой" in t or "адрес" in t for t in body["tips"])
    assert any("нагрузк" in t for t in body["tips"])  # упирается именно в долговую нагрузку
    assert not any("Сумма кредита" in d for d in body["drivers"])
