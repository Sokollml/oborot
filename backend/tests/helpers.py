"""Вспомогательные функции для тестов: создать и заполнить заявку через API."""

import uuid

from fastapi.testclient import TestClient

FULL_FORM = {
    "revenue_12m": 30_000_000,
    "revenue_prev_year": 26_000_000,
    "monthly_debt_payments": 50_000,
    "employees": 12,
    "bki_consent": True,
}


def create_draft(
    client: TestClient,
    *,
    inn: str = "0010000017",
    product: str = "EXPRESS",
    amount: int = 2_000_000,
    term: int = 12,
    purpose: str = "urgent",
    **form,
) -> int:
    r = client.post(
        "/api/applications",
        json={"product_code": product, "inn": inn, "purpose": purpose, "amount": amount, "term_months": term},
    )
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]
    r = client.patch(f"/api/applications/{app_id}", json={**FULL_FORM, **form})
    assert r.status_code == 200, r.text
    return app_id


def submit(client: TestClient, app_id: int, key: str | None = None):
    return client.post(f"/api/applications/{app_id}/submit", headers={"Idempotency-Key": key or uuid.uuid4().hex})
