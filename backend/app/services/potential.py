"""Предодобренный лимит («кредитный потенциал») для компании на обслуживании в банке.

Идея как у лидеров рынка: банк уже видит обороты клиента по счёту, поэтому может заранее сказать
«вам доступно до X ₽» — без анкеты и документов.

Как считаем (прозрачно и тем же скорингом, что и заявки):
1. берём данные реестра, налоговой, кредитной истории и обороты по счёту за 12 и предыдущие 12 месяцев;
2. для каждого беззалогового продукта ищем максимальную сумму, при которой заявка получила бы
   АВТОМАТИЧЕСКОЕ одобрение (по таблице решений из scoring_config.yaml);
3. показываем лучший вариант, из чего сложился лимит и что поможет его увеличить.

Это предварительная оценка: точное решение — после заявки.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

from app.enums import CheckSource
from app.models import Company, Product
from app.services import external
from app.services.finance import annuity_payment
from app.services.scoring import ScoringInput, score
from app.services.scoring_config import config

# Для каких продуктов и на какой срок считаем лимит (залоговый INVEST всегда решает специалист).
POTENTIAL_PRODUCTS = {"EXPRESS": 12, "WORKING": 24}
STEP = 50_000

TIPS = {
    "debt_load": "Снизьте текущую долговую нагрузку — погасите часть действующих кредитов",
    "amount_to_revenue": "Проводите больше выручки через счёт в банке — лимит растёт вместе с оборотами",
    "credit_history": "Платите по кредитам без просрочек — через 6–12 месяцев лимит вырастет",
    "revenue_trend": "Лимит вырастет, когда выручка снова пойдёт вверх",
    "tax_debt": "Погасите долг перед налоговой",
    "mass_address": "Смените юридический адрес на собственный или арендованный офис",
    "business_age": "Лимит вырастет, когда бизнесу исполнится год, и ещё раз — после трёх лет",
}

# Факторы, которые описывают сам бизнес (подходят для объяснения «из чего сложился лимит»).
DRIVER_CODES = {"business_age", "credit_history", "revenue_trend"}
# Нейтральные (0 баллов) факторы, которые можно улучшить.
NEUTRAL_TIPS = {
    "business_age": "Лимит вырастет, когда бизнесу исполнится год",
    "credit_history": "Небольшой кредит, погашенный вовремя, создаст кредитную историю — лимит вырастет",
    "revenue_trend": "Лимит вырастет, когда выручка пойдёт вверх",
}


def _fetch_all(inn: str) -> dict[CheckSource, dict[str, Any]]:
    """Четыре источника параллельно; короткий таймаут — клиент ждёт на экране."""

    def one(source: CheckSource) -> dict[str, Any]:
        try:
            return external.fetch(source, inn, retries=1, timeout=2.0)
        except (external.ExternalServiceError, external.CompanyNotFoundInRegistry) as exc:
            return {"error": str(exc) or "нет ответа"}

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(zip(CheckSource, pool.map(one, CheckSource), strict=True))
    return results


def _input(amount: int, term: int, rate: float, data: dict[CheckSource, dict[str, Any]]) -> ScoringInput:
    egrul, fns, bki, acc = (data[s] for s in (CheckSource.EGRUL, CheckSource.FNS, CheckSource.BKI, CheckSource.ACCOUNT))
    return ScoringInput(
        amount=amount,
        term_months=term,
        base_rate=rate,
        revenue_12m=acc["revenue_12m"],
        revenue_prev_year=acc["revenue_prev_12m"],
        monthly_debt_payments=bki.get("current_monthly_payments", 0),
        registered_at=date.fromisoformat(egrul["registered_at"]),
        company_status=egrul["status"],
        tax_debt=fns["tax_debt"],
        mass_address=fns["mass_address"],
        active_loans=bki["active_loans"],
        max_overdue_days_2y=bki["max_overdue_days_2y"],
        closed_loans_without_overdue=bki["closed_loans_without_overdue"],
    )


def _auto_approved(product_code: str, inp: ScoringInput) -> bool:
    result = score(inp)
    return not result.stopped and config()["decision_matrix"][product_code][result.risk_class] == "approve"


def _max_amount(product: Product, term: int, data: dict) -> int:
    """Наибольшая сумма с шагом 50 000 ₽, при которой было бы автоодобрение (0 — если ни при какой)."""
    best = 0
    amount = product.min_amount
    while amount <= product.max_amount:
        if _auto_approved(product.code, _input(amount, term, product.base_rate, data)):
            best = amount
        amount += STEP
    return best


def calculate(company: Company, products: list[Product]) -> dict[str, Any]:
    data = _fetch_all(company.inn)
    acc = data[CheckSource.ACCOUNT]

    if "error" in acc or not acc.get("has_account"):
        return {
            "status": "no_account",
            "title": "Лимит рассчитаем по заявке",
            "text": "Компания не обслуживается в банке, поэтому оборотов мы не видим. Подайте заявку — выручку подтвердим выпиской.",
        }
    failed = [external.SOURCE_NAMES[s] for s, v in data.items() if "error" in v]
    if failed:
        return {
            "status": "unavailable",
            "title": "Не получилось рассчитать",
            "text": f"Сейчас не отвечает {', '.join(failed)}. Попробуйте обновить позже или подайте заявку — её рассмотрит специалист.",
        }

    by_code = {p.code: p for p in products}
    offers = []
    for code, term in POTENTIAL_PRODUCTS.items():
        p = by_code[code]
        amount = _max_amount(p, term, data)
        if amount:
            offers.append({
                "product_code": code,
                "product_name": p.name,
                "amount": amount,
                "term_months": term,
                "rate": p.base_rate,
                "monthly_payment": annuity_payment(amount, p.base_rate, term),
            })

    # Из чего сложился лимит и что поможет его увеличить — по факторам на максимальной сумме продукта.
    reference = by_code["WORKING"]
    ref = score(_input(reference.max_amount, POTENTIAL_PRODUCTS["WORKING"], reference.base_rate, data))
    # «Помогло» — только свойства самого бизнеса; доля кредита в выручке и нагрузка зависят от суммы, а не от клиента.
    drivers = [f"{f.title}: {f.value}" for f in sorted(ref.factors, key=lambda f: -f.points) if f.points > 0 and f.code in DRIVER_CODES]
    # «Как увеличить» — то, что тянет вниз, и нейтральные факторы, которые можно улучшить.
    tips = []
    for f in sorted(ref.factors, key=lambda f: f.points):
        if f.points < 0 and f.code in TIPS:
            tips.append(TIPS[f.code])
        elif f.points == 0 and f.code in NEUTRAL_TIPS:
            tips.append(NEUTRAL_TIPS[f.code])
    tips = tips[:3]

    base = {
        "revenue_12m": acc["revenue_12m"],
        "revenue_prev_12m": acc["revenue_prev_12m"],
        "drivers": drivers,
        "tips": tips or ["Проводите выручку через счёт в банке — лимит пересчитывается по оборотам"],
    }
    if ref.stopped:
        return {
            **base,
            "status": "none",
            "title": "Сейчас предодобренного предложения нет",
            "text": "; ".join(f.comment for f in ref.stop_factors) + ".",
            "tips": [],
        }
    if not offers:
        return {
            **base,
            "status": "none",
            "title": "Сейчас предодобренного предложения нет",
            "text": "Можно подать заявку — её рассмотрит специалист и предложит подходящие условия.",
        }
    best = max(offers, key=lambda o: o["amount"])
    return {
        **base,
        "status": "ok",
        "title": f"Вам предварительно одобрено до {best['amount']:,} ₽".replace(",", " "),
        "text": "Рассчитано по оборотам на вашем счёте и кредитной истории. Документы не нужны — только подтвердите заявку.",
        "max_amount": best["amount"],
        "offers": offers,
    }
