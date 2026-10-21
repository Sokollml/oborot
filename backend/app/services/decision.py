"""Кредитное решение — отдельно от скоринга.

Скоринг отвечает на вопрос «насколько надёжен клиент» (балл и класс A–D).
Решение отвечает на вопрос «что делаем с этой заявкой»: одобряем, предлагаем меньшую сумму,
просим документы, отдаём специалисту или отказываем. Таблица «продукт × класс» — в scoring_config.yaml.

Для клиента формируем 2–3 понятные причины и совет, что можно сделать.
"""

import math
from dataclasses import dataclass, field

from app.enums import AppStatus, DecisionType
from app.services.finance import annuity_payment
from app.services.scoring import Factor, ScoringInput, ScoringResult
from app.services.scoring_config import config

POSITIVE = {
    "business_age": "Бизнес работает {value} — это говорит об устойчивости",
    "amount_to_revenue": "Сумма кредита — {value} годовой выручки, это посильно для бизнеса",
    "debt_load": "Платежи по всем кредитам займут {value} месячной выручки — нагрузка комфортная",
    "credit_history": "Хорошая кредитная история: кредиты закрывались без просрочек",
    "revenue_trend": "Выручка за год выросла ({value})",
}
NEGATIVE = {
    "amount_to_revenue": "Сумма кредита — {value} годовой выручки, это много для бизнеса такого размера",
    "debt_load": "Платежи по всем кредитам заберут {value} месячной выручки — это высокая нагрузка",
    "credit_history": "В кредитной истории есть просрочка ({value})",
    "revenue_trend": "Выручка за год снизилась ({value})",
    "tax_debt": "Есть долг перед налоговой",
    "mass_address": "Компания зарегистрирована на адресе, где много других фирм",
}
STOP_REASONS = {
    "company_status": "Компания в процессе ликвидации или банкротства — в таком статусе кредит выдать нельзя",
    "overdue_90": "За последние 2 года была просрочка по кредиту больше 90 дней ({value})",
    "young_business": "Бизнес работает {value}, а нужно хотя бы 6 месяцев",
}


@dataclass
class Outcome:
    kind: str  # approve | counter | manual | info | reject (из decision_matrix)
    target_status: AppStatus
    history_comment: str
    decision_type: DecisionType | None = None  # None — решения пока нет (ручное рассмотрение)
    amount: int | None = None
    term: int | None = None
    rate: float | None = None
    monthly_payment: int | None = None
    reasons: list[str] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)
    request_docs: list[str] = field(default_factory=list)


def _rub(value: float) -> str:
    return f"{int(value):,}".replace(",", " ") + " ₽"


def _top(factors: list[Factor], positive: bool, n: int = 3) -> list[str]:
    texts = POSITIVE if positive else NEGATIVE
    chosen = sorted(
        (f for f in factors if (f.points > 0 if positive else f.points < 0) and f.code in texts),
        key=lambda f: -abs(f.points),
    )
    return [texts[f.code].format(value=f.value) for f in chosen[:n]]


def _max_comfortable_amount(data: ScoringInput) -> int:
    """Сумма, при которой доля к выручке и долговая нагрузка в комфортной зоне (для совета)."""
    adv = config()["advice"]
    by_revenue = data.revenue_12m * adv["comfortable_amount_to_revenue_pct"] / 100
    free_payment = data.revenue_12m / 12 * adv["comfortable_debt_load_pct"] / 100 - data.monthly_debt_payments
    if free_payment <= 0:
        return 0
    i = data.base_rate / 100 / 12
    by_load = free_payment * (1 - (1 + i) ** -data.term_months) / i if i else free_payment * data.term_months
    return int(math.floor(min(by_revenue, by_load) / 10_000) * 10_000)


def _advice(result: ScoringResult, data: ScoringInput, min_amount: int) -> list[str]:
    codes = {f.code for f in result.factors if f.points < 0}
    advice: list[str] = []
    if codes & {"amount_to_revenue", "debt_load"}:
        best = _max_comfortable_amount(data)
        if best >= min_amount:
            advice.append(f"Снизьте сумму до {_rub(best)} или увеличьте срок — так платёж станет посильнее")
        else:
            advice.append("Сначала уменьшите текущую долговую нагрузку — погасите часть действующих кредитов")
    if "credit_history" in codes:
        advice.append("Платите по текущим кредитам без просрочек — через 6–12 месяцев история станет лучше")
    if "tax_debt" in codes:
        advice.append("Погасите долг перед налоговой и подайте заявку снова")
    age = int(result.metrics["age_months"])
    if age < 12 and not advice:
        advice.append(f"Вернитесь через {12 - age} мес., когда бизнесу исполнится год — шансы вырастут")
    return advice[:2]


def _stop_advice(result: ScoringResult) -> list[str]:
    codes = {f.code for f in result.stop_factors}
    if "young_business" in codes:
        wait = max(1, config()["stop_factors"]["min_business_age_months"] - int(result.metrics["age_months"]))
        return [f"Вернитесь через {wait} мес. — тогда заявку можно будет рассмотреть"]
    if "overdue_90" in codes:
        return ["Подайте заявку снова, когда с момента большой просрочки пройдёт 2 года"]
    return ["Если статус компании изменится, подайте заявку снова"]


def decide(
    product_code: str,
    product_name: str,
    product_min_amount: int,
    data: ScoringInput,
    result: ScoringResult,
    docs_already_requested: bool,
) -> Outcome:
    cfg = config()

    # 1. Стоп-факторы — отказ сразу.
    if result.stopped:
        return Outcome(
            kind="reject",
            target_status=AppStatus.REJECTED,
            history_comment="Стоп-фактор: " + "; ".join(f.comment for f in result.stop_factors),
            decision_type=DecisionType.REJECT,
            reasons=[STOP_REASONS[f.code].format(value=f.value) for f in result.stop_factors][:3],
            advice=_stop_advice(result),
        )

    # 2. Документы уже запрашивали — теперь решает только человек (без бесконечного цикла запросов).
    if docs_already_requested:
        return Outcome(
            kind="manual",
            target_status=AppStatus.MANUAL_REVIEW,
            history_comment=f"Документы получены, класс {result.risk_class} — решение принимает специалист",
        )

    kind = cfg["decision_matrix"][product_code][result.risk_class]
    rate = data.base_rate + cfg["rate_surcharge"][result.risk_class]

    if kind == "approve":
        return Outcome(
            kind=kind,
            target_status=AppStatus.OFFER,
            history_comment=f"Автоодобрение: класс {result.risk_class}, {result.total_score} баллов",
            decision_type=DecisionType.APPROVE,
            amount=data.amount,
            term=data.term_months,
            rate=rate,
            monthly_payment=annuity_payment(data.amount, rate, data.term_months),
            reasons=_top(result.factors, positive=True),
        )

    if kind == "counter":
        co = cfg["counter_offer"]
        amount = int(math.floor(data.amount * co["ratio"] / co["round_to"]) * co["round_to"])
        if amount >= product_min_amount:
            payment = annuity_payment(amount, rate, data.term_months)
            return Outcome(
                kind=kind,
                target_status=AppStatus.OFFER,
                history_comment=f"Контрпредложение: класс {result.risk_class}, сумма {_rub(amount)} вместо {_rub(data.amount)}",
                decision_type=DecisionType.COUNTER,
                amount=amount,
                term=data.term_months,
                rate=rate,
                monthly_payment=payment,
                reasons=_top(result.factors, positive=False, n=2)
                + [f"Готовы одобрить {_rub(amount)} — платёж {_rub(payment)} в месяц"],
            )
        kind = "reject"  # меньшая сумма не проходит по условиям продукта

    if kind == "manual":
        why = (
            f"«{product_name}» всегда рассматривает специалист"
            if all(v == "manual" for k, v in cfg["decision_matrix"][product_code].items() if k != "D")
            else f"Класс {result.risk_class} — решение принимает специалист"
        )
        return Outcome(kind=kind, target_status=AppStatus.MANUAL_REVIEW, history_comment=f"{why} ({result.total_score} баллов)")

    if kind == "info":
        return Outcome(
            kind=kind,
            target_status=AppStatus.INFO_REQUESTED,
            history_comment=f"Класс {result.risk_class}: нужна выписка по счёту, чтобы подтвердить выручку",
            decision_type=DecisionType.INFO,
            reasons=["Чтобы принять решение, нужно подтвердить выручку выпиской по расчётному счёту"],
            request_docs=["bank_statement"],
        )

    # reject
    reasons = _top(result.factors, positive=False) or ["Совокупность факторов пока не позволяет одобрить кредит"]
    return Outcome(
        kind="reject",
        target_status=AppStatus.REJECTED,
        history_comment=f"Отказ: класс {result.risk_class}, {result.total_score} баллов",
        decision_type=DecisionType.REJECT,
        reasons=reasons,
        advice=_advice(result, data, product_min_amount),
    )
