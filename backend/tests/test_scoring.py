"""Скоринг: каждый фактор по отдельности, стоп-факторы и границы классов."""

from dataclasses import replace
from datetime import date

import pytest

from app.services.scoring import ScoringInput, months_between, score

TODAY = date(2026, 10, 21)

# Базовый «нейтральный» клиент: каждый тест меняет один параметр и смотрит на один фактор.
BASE = ScoringInput(
    amount=1_000_000,
    term_months=12,
    base_rate=24.0,
    revenue_12m=10_000_000,  # сумма = 10% выручки
    revenue_prev_year=10_000_000,  # выручка без изменений
    monthly_debt_payments=0,
    registered_at=date(2024, 10, 1),  # 2 года
    company_status="active",
    tax_debt=False,
    mass_address=False,
    active_loans=0,
    max_overdue_days_2y=0,
    closed_loans_without_overdue=0,  # истории нет
    today=TODAY,
)


def points(data: ScoringInput, code: str) -> int:
    return next(f.points for f in score(data).factors if f.code == code)


def test_months_between():
    assert months_between(date(2026, 4, 21), TODAY) == 6
    assert months_between(date(2026, 4, 22), TODAY) == 5


@pytest.mark.parametrize(
    ("registered", "expected"),
    [(date(2026, 1, 1), 0), (date(2025, 10, 22), 0), (date(2025, 10, 21), 10), (date(2023, 10, 21), 10), (date(2023, 9, 21), 15)],
)
def test_business_age(registered, expected):
    # считаем полные месяцы: 6–11 → 0; 12–36 (1–3 года) → +10; 37 и больше → +15
    assert points(replace(BASE, registered_at=registered), "business_age") == expected


@pytest.mark.parametrize(("amount", "expected"), [(2_000_000, 15), (2_000_001, 5), (5_000_000, 5), (5_000_001, -15)])
def test_amount_to_revenue(amount, expected):
    # до 20% → +15; 20–50% → +5; больше 50% → −15 (выручка 10 млн)
    assert points(replace(BASE, amount=amount, term_months=60, base_rate=0.0), "amount_to_revenue") == expected


@pytest.mark.parametrize(
    ("existing", "expected"),
    [(0, 15), (50_000, 15), (50_001, 5), (200_000, 5), (200_001, -20)],
)
def test_debt_load(existing, expected):
    # Выручка 12 млн → 1 млн в месяц. Новый платёж: 1,2 млн на 12 мес. под 0% = 100 000 ₽.
    # Нагрузка = (существующие платежи + 100 000) / 1 000 000:
    # до 15% → +15; 15–30% → +5; больше 30% → −20
    data = replace(BASE, amount=1_200_000, base_rate=0.0, revenue_12m=12_000_000, monthly_debt_payments=existing)
    assert points(data, "debt_load") == expected


@pytest.mark.parametrize(
    ("overdue", "closed", "expected"),
    [(0, 3, 15), (0, 0, 0), (1, 3, -10), (30, 0, -10), (31, 2, -25), (89, 0, -25)],
)
def test_credit_history(overdue, closed, expected):
    # закрытые кредиты без просрочек → +15; истории нет → 0; просрочка до 30 дней → −10; 31–89 → −25
    data = replace(BASE, max_overdue_days_2y=overdue, closed_loans_without_overdue=closed)
    assert points(data, "credit_history") == expected


@pytest.mark.parametrize(("prev", "expected"), [(9_000_000, 5), (10_000_000, 0), (14_000_000, 0), (15_000_000, -10), (0, 0)])
def test_revenue_trend(prev, expected):
    # выручка 10 млн: рост → +5; падение до 30% → 0; падение больше 30% → −10; нет данных → 0
    assert points(replace(BASE, revenue_prev_year=prev), "revenue_trend") == expected


def test_tax_debt_and_mass_address():
    assert points(replace(BASE, tax_debt=True), "tax_debt") == -15
    assert points(replace(BASE, mass_address=True), "mass_address") == -5
    assert points(BASE, "tax_debt") == points(BASE, "mass_address") == 0


@pytest.mark.parametrize(
    ("change", "expected_stop"),
    [
        (dict(company_status="liquidating"), "company_status"),
        (dict(company_status="bankrupt"), "company_status"),
        (dict(max_overdue_days_2y=90), "overdue_90"),
        (dict(registered_at=date(2026, 5, 1)), "young_business"),
    ],
)
def test_stop_factors(change, expected_stop):
    result = score(replace(BASE, **change))
    assert result.stopped
    assert [f.code for f in result.stop_factors] == [expected_stop]


def test_no_stop_factor_for_good_company():
    assert not score(BASE).stopped
    assert not score(replace(BASE, max_overdue_days_2y=89, registered_at=date(2026, 4, 21))).stopped


def test_total_is_clipped_and_classes():
    best = replace(
        BASE, registered_at=date(2015, 1, 1), closed_loans_without_overdue=5, revenue_prev_year=5_000_000
    )
    r = score(best)
    assert r.total_score == 100 and r.risk_class == "A"  # 40+15+15+15+15+5 = 105 → 100

    worst = replace(
        BASE, amount=9_000_000, revenue_prev_year=20_000_000, max_overdue_days_2y=60, tax_debt=True, mass_address=True
    )
    r = score(worst)
    assert r.total_score == 0 and r.risk_class == "D"


@pytest.mark.parametrize(("score_value", "cls"), [(70, "A"), (69, "B"), (55, "B"), (54, "C"), (40, "C"), (39, "D")])
def test_class_boundaries(score_value, cls):
    from app.services.scoring_config import config

    assert next(rc["class"] for rc in config()["risk_classes"] if score_value >= rc["min_score"]) == cls


def test_every_factor_is_explained():
    r = score(BASE)
    assert {f.code for f in r.factors} == {
        "business_age", "amount_to_revenue", "debt_load", "credit_history", "revenue_trend", "tax_debt", "mass_address"
    }
    assert all(f.title and f.comment and f.value for f in r.factors)
    assert r.total_score == 40 + sum(f.points for f in r.factors)
