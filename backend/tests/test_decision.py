"""Таблица кредитных решений: продукт × класс риска."""

from dataclasses import replace
from datetime import date

import pytest

from app.enums import AppStatus
from app.services.decision import decide
from app.services.scoring import Factor, ScoringInput, ScoringResult

DATA = ScoringInput(
    amount=2_000_000, term_months=12, base_rate=24.0, revenue_12m=10_000_000, revenue_prev_year=9_000_000,
    monthly_debt_payments=50_000, registered_at=date(2024, 1, 1), company_status="active", tax_debt=False,
    mass_address=False, active_loans=1, max_overdue_days_2y=0, closed_loans_without_overdue=2,
)


def result(risk_class: str, factors: list[Factor] | None = None, stops: list[Factor] | None = None) -> ScoringResult:
    return ScoringResult(
        total_score={"A": 80, "B": 60, "C": 45, "D": 20}[risk_class],
        risk_class=risk_class,
        factors=factors or [],
        stop_factors=stops or [],
        model_version="test",
        metrics={"age_months": 24},
    )


MIN_AMOUNT = {"EXPRESS": 100_000, "WORKING": 500_000, "INVEST": 1_000_000}

S = AppStatus


@pytest.mark.parametrize(
    ("product", "risk_class", "kind", "status"),
    [
        ("EXPRESS", "A", "approve", S.OFFER),
        ("EXPRESS", "B", "counter", S.OFFER),
        ("EXPRESS", "C", "reject", S.REJECTED),
        ("EXPRESS", "D", "reject", S.REJECTED),
        ("WORKING", "A", "approve", S.OFFER),
        ("WORKING", "B", "manual", S.MANUAL_REVIEW),
        ("WORKING", "C", "info", S.INFO_REQUESTED),
        ("WORKING", "D", "reject", S.REJECTED),
        ("INVEST", "A", "manual", S.MANUAL_REVIEW),
        ("INVEST", "B", "manual", S.MANUAL_REVIEW),
        ("INVEST", "C", "manual", S.MANUAL_REVIEW),
        ("INVEST", "D", "reject", S.REJECTED),
    ],
)
def test_decision_matrix(product, risk_class, kind, status):
    outcome = decide(product, product, MIN_AMOUNT[product], DATA, result(risk_class), docs_already_requested=False)
    assert (outcome.kind, outcome.target_status) == (kind, status)


def test_approve_rate_and_payment():
    o = decide("EXPRESS", "Экспресс", 100_000, DATA, result("A"), False)
    assert o.amount == 2_000_000 and o.term == 12
    assert o.rate == 24.0  # класс A — без надбавки
    assert o.monthly_payment == 189_119  # аннуитет 2 млн, 24%, 12 мес.


def test_counter_offer_is_70_percent_with_surcharge():
    o = decide("EXPRESS", "Экспресс", 100_000, DATA, result("B"), False)
    assert o.amount == 1_400_000
    assert o.rate == 26.0  # 24 + 2 п.п. за класс B
    assert any("1 400 000 ₽" in r for r in o.reasons)


def test_counter_below_product_minimum_becomes_reject():
    small = replace(DATA, amount=120_000)  # 70% = 84 000 < минимума 100 000
    assert decide("EXPRESS", "Экспресс", 100_000, small, result("B"), False).kind == "reject"


def test_info_requests_bank_statement():
    o = decide("WORKING", "Оборотный", 500_000, DATA, result("C"), False)
    assert o.request_docs == ["bank_statement"]


def test_after_documents_always_manual():
    # Документы уже запрашивали — даже класс C по WORKING идёт к человеку, а не на новый запрос.
    o = decide("WORKING", "Оборотный", 500_000, DATA, result("C"), docs_already_requested=True)
    assert o.target_status == S.MANUAL_REVIEW


def test_stop_factor_rejects_with_human_reason_and_advice():
    stop = Factor("young_business", "Возраст бизнеса", "4 мес.", 0, "")
    o = decide("WORKING", "Оборотный", 500_000, DATA, replace(result("A"), stop_factors=[stop], metrics={"age_months": 4}), False)
    assert o.target_status == S.REJECTED
    assert "4 мес." in o.reasons[0]
    assert "через 2 мес." in o.advice[0]


def test_reject_gives_reasons_and_amount_advice():
    factors = [
        Factor("debt_load", "Долговая нагрузка", "45,0%", -20, ""),
        Factor("amount_to_revenue", "Сумма к выручке", "60,0%", -15, ""),
        Factor("business_age", "Возраст", "2 года", 10, ""),
    ]
    o = decide("EXPRESS", "Экспресс", 100_000, DATA, result("D", factors), False)
    assert len(o.reasons) == 2 and "45,0%" in o.reasons[0]  # самый тяжёлый фактор — первым
    assert o.advice and o.advice[0].startswith("Снизьте сумму до")
