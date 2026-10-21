"""Скоринг — оценка заявки в баллах по прозрачным правилам.

Как считаем:
1. Сначала стоп-факторы (ликвидация/банкротство, просрочка 90+ дней, бизнесу < 6 месяцев).
   Если есть хоть один — дальше не считаем, решение «отказ».
2. Иначе стартуем с base_score (40) и по каждому фактору добавляем или вычитаем баллы.
3. Итог обрезаем до 0–100 и переводим в класс риска A/B/C/D.

Каждый фактор сохраняется отдельно (код, значение, баллы, пояснение) — аналитик и жюри
видят, ПОЧЕМУ получился такой балл. Все цифры берутся из scoring_config.yaml.

Почему не машинное обучение: нет реальных данных для обучения, а банку и клиенту важно
объяснить каждое решение. Правила легко проверить и поменять.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.finance import annuity_payment
from app.services.scoring_config import config


@dataclass
class ScoringInput:
    """Всё, что нужно для оценки: анкета клиента + ответы внешних сервисов."""

    amount: int
    term_months: int
    base_rate: float
    revenue_12m: int
    revenue_prev_year: int
    monthly_debt_payments: int
    registered_at: date
    company_status: str
    tax_debt: bool
    mass_address: bool
    active_loans: int
    max_overdue_days_2y: int
    closed_loans_without_overdue: int
    today: date = field(default_factory=date.today)


@dataclass
class Factor:
    code: str
    title: str  # название фактора для людей
    value: str  # значение для людей: «5 лет 4 мес.», «6,7%»
    points: int
    comment: str  # объяснение простыми словами

    def as_dict(self) -> dict[str, Any]:
        return vars(self).copy()


@dataclass
class ScoringResult:
    total_score: int
    risk_class: str
    factors: list[Factor]
    stop_factors: list[Factor]
    model_version: str
    metrics: dict[str, float]  # сырые числа для советов клиенту (нагрузка, доля выручки…)

    @property
    def stopped(self) -> bool:
        return bool(self.stop_factors)


def months_between(start: date, end: date) -> int:
    """Полных месяцев между датами."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def _age_text(months: int) -> str:
    years, rest = divmod(months, 12)
    parts = []
    if years:
        word = "год" if years % 10 == 1 and years % 100 != 11 else "года" if 2 <= years % 10 <= 4 and not 12 <= years % 100 <= 14 else "лет"
        parts.append(f"{years} {word}")
    if rest or not years:
        parts.append(f"{rest} мес.")
    return " ".join(parts)


def _pct(value: float) -> str:
    return f"{value:.1f}%".replace(".", ",")


def _band(bands: list[dict[str, Any]], value: float) -> int:
    """Баллы из первой полосы, где value <= upto (upto: null — без верхней границы)."""
    for band in bands:
        if band["upto"] is None or value <= band["upto"]:
            return int(band["points"])
    raise ValueError("В конфиге нет полосы без верхней границы")


def score(data: ScoringInput) -> ScoringResult:
    cfg = config()
    f = cfg["factors"]
    age_months = months_between(data.registered_at, data.today)

    # ---- 1. Стоп-факторы ----
    stop = cfg["stop_factors"]
    stops: list[Factor] = []
    if data.company_status in stop["company_statuses"]:
        label = "банкротство" if data.company_status == "bankrupt" else "ликвидация"
        stops.append(Factor("company_status", "Статус компании", label, 0, "Компания в процессе ликвидации или банкротства"))
    if data.max_overdue_days_2y > stop["max_overdue_days"]:
        stops.append(
            Factor("overdue_90", "Просрочка по кредитам", f"{data.max_overdue_days_2y} дн.", 0, "Просрочка больше 90 дней за последние 2 года")
        )
    if age_months < stop["min_business_age_months"]:
        stops.append(
            Factor("young_business", "Возраст бизнеса", _age_text(age_months), 0, "Бизнес работает меньше 6 месяцев")
        )

    # ---- 2. Факторы с баллами ----
    factors: list[Factor] = []

    pts = _band(f["business_age_months"], age_months)
    factors.append(Factor("business_age", "Возраст бизнеса", _age_text(age_months), pts, "Чем дольше работает бизнес, тем он устойчивее"))

    amount_ratio = data.amount / data.revenue_12m * 100 if data.revenue_12m else 1000.0
    pts = _band(f["amount_to_revenue_pct"], amount_ratio)
    factors.append(
        Factor("amount_to_revenue", "Сумма кредита к выручке", _pct(amount_ratio), pts, "Какую долю годовой выручки составляет кредит")
    )

    new_payment = annuity_payment(data.amount, data.base_rate, data.term_months)
    monthly_revenue = data.revenue_12m / 12
    debt_load = (data.monthly_debt_payments + new_payment) / monthly_revenue * 100 if monthly_revenue else 1000.0
    pts = _band(f["debt_load_pct"], debt_load)
    factors.append(
        Factor(
            "debt_load",
            "Долговая нагрузка",
            _pct(debt_load),
            pts,
            "Какую часть месячной выручки будут забирать платежи по всем кредитам, включая новый",
        )
    )

    ch = f["credit_history"]
    if data.max_overdue_days_2y == 0 and data.closed_loans_without_overdue > 0:
        pts, value, comment = ch["clean_closed_loans"], f"закрыто без просрочек: {data.closed_loans_without_overdue}", "Хорошая кредитная история"
    elif data.max_overdue_days_2y == 0:
        pts, value, comment = ch["no_history"], "закрытых кредитов нет", "Кредитной истории пока мало — это нейтрально"
    elif data.max_overdue_days_2y <= 30:
        pts, value, comment = ch["overdue_up_to_30"], f"просрочка до {data.max_overdue_days_2y} дн.", "Была небольшая просрочка платежа"
    else:
        pts, value, comment = ch["overdue_31_89"], f"просрочка {data.max_overdue_days_2y} дн.", "Была заметная просрочка платежа"
    factors.append(Factor("credit_history", "Кредитная история", value, pts, comment))

    rt = f["revenue_trend"]
    if data.revenue_prev_year > 0:
        change = (data.revenue_12m - data.revenue_prev_year) / data.revenue_prev_year * 100
        if change > 0:
            pts, comment = rt["growth"], "Выручка растёт"
        elif change < -rt["drop_over_pct"]:
            pts, comment = rt["big_drop"], "Выручка сильно упала"
        else:
            pts, comment = 0, "Выручка примерно на прежнем уровне"
        value = ("+" if change > 0 else "") + _pct(change)
    else:
        pts, comment, value, change = 0, "Нет данных за прошлый год", "нет данных", 0.0
    factors.append(Factor("revenue_trend", "Выручка год к году", value, pts, comment))

    factors.append(
        Factor(
            "tax_debt",
            "Налоговый долг",
            "есть" if data.tax_debt else "нет",
            f["tax_debt"] if data.tax_debt else 0,
            "Долг перед налоговой" if data.tax_debt else "Долгов перед налоговой нет",
        )
    )
    factors.append(
        Factor(
            "mass_address",
            "Массовый адрес",
            "да" if data.mass_address else "нет",
            f["mass_address"] if data.mass_address else 0,
            "По адресу компании зарегистрировано много фирм" if data.mass_address else "Адрес регистрации обычный",
        )
    )

    # ---- 3. Итог и класс ----
    raw = cfg["base_score"] + sum(x.points for x in factors)
    total = max(cfg["min_score"], min(cfg["max_score"], raw))
    risk_class = next(rc["class"] for rc in cfg["risk_classes"] if total >= rc["min_score"])

    return ScoringResult(
        total_score=total,
        risk_class=risk_class,
        factors=factors,
        stop_factors=stops,
        model_version=cfg["model_version"],
        metrics={
            "age_months": age_months,
            "amount_to_revenue_pct": amount_ratio,
            "debt_load_pct": debt_load,
            "new_payment": new_payment,
            "revenue_change_pct": change,
        },
    )
