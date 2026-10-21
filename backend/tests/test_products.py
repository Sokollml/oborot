"""Подбор продукта, аннуитет, проверка ИНН."""

import pytest

from app.services.finance import annuity_payment
from app.services.inn import is_valid_inn


def test_annuity_formula():
    # 1 200 000 ₽ на 12 мес. под 12% годовых → 106 619 ₽ в месяц (проверено по калькулятору)
    assert annuity_payment(1_200_000, 12.0, 12) == 106_619
    assert annuity_payment(1_200_000, 0.0, 12) == 100_000


@pytest.mark.parametrize(
    ("inn", "ok"),
    [("0010000017", True), ("001000001006", True), ("0010000994", True), ("0010000018", False), ("12345", False)],
)
def test_inn_checksum(inn, ok):
    assert is_valid_inn(inn) is ok


@pytest.mark.parametrize(
    ("purpose", "amount", "term", "expected"),
    [
        ("urgent", 2_000_000, 12, "EXPRESS"),
        ("stock_salary", 5_000_000, 12, "WORKING"),
        ("equipment", 20_000_000, 48, "INVEST"),
        ("equipment", 3_000_000, 24, "WORKING"),
        ("urgent", 10_000_000, 12, "WORKING"),  # экспресс до 3 млн — берём следующий подходящий
    ],
)
def test_recommendation(client1, purpose, amount, term, expected):
    r = client1.post("/api/products/recommend", json={"purpose": purpose, "amount": amount, "term_months": term})
    assert r.status_code == 200
    body = r.json()
    assert body["recommended"]["product"]["code"] == expected
    assert body["recommended"]["fits"] is True
    assert body["recommended"]["monthly_payment_from"] > 0


def test_recommendation_when_nothing_fits(client1):
    r = client1.post("/api/products/recommend", json={"purpose": "urgent", "amount": 80_000_000, "term_months": 12})
    rec = r.json()["recommended"]
    assert rec["fits"] is False
    assert "измените параметры" in rec["reason"]
