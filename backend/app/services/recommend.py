"""Подбор кредитного продукта по цели, сумме и сроку.

Логика простая и объяснимая:
1. по цели определяем порядок предпочтения продуктов;
2. рекомендуем первый, в лимиты которого укладываются сумма и срок;
3. если не подходит ни один — берём первый по цели и подсказываем, как поменять сумму или срок.
Платёж считаем по базовой ставке продукта («от»), точная ставка будет после рассмотрения.
"""

from dataclasses import dataclass

from app.enums import Purpose
from app.models import Product
from app.services.finance import annuity_payment

PREFERENCE: dict[Purpose, list[str]] = {
    Purpose.URGENT: ["EXPRESS", "WORKING", "INVEST"],
    Purpose.STOCK_SALARY: ["WORKING", "EXPRESS", "INVEST"],
    Purpose.EQUIPMENT: ["WORKING", "INVEST", "EXPRESS"],  # крупные суммы/сроки — см. ниже
}

WHY: dict[str, str] = {
    "EXPRESS": "Решение за несколько минут, без залога и визита в банк. Подходит, когда деньги нужны быстро.",
    "WORKING": "Для текущих расходов бизнеса: закупка товара, зарплаты, аренда. Без залога, до 15 млн ₽.",
    "INVEST": (
        "Для крупных вложений в развитие: оборудование, ремонт, транспорт. Большая сумма и долгий срок, "
        "но понадобится залог, а заявку посмотрит специалист."
    ),
}


@dataclass
class Option:
    product: Product
    fits: bool
    reason: str
    amount: int
    term_months: int
    monthly_payment: int


def _rub(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " ₽"


def _fits(p: Product, amount: int, term: int) -> bool:
    return p.min_amount <= amount <= p.max_amount and p.min_term <= term <= p.max_term


def _adjust_hint(p: Product, amount: int, term: int) -> tuple[int, int, str]:
    """Ближайшие сумма и срок, которые подходят продукту, и подсказка, что поменять."""
    new_amount = min(max(amount, p.min_amount), p.max_amount)
    new_term = min(max(term, p.min_term), p.max_term)
    hints = []
    if new_amount != amount:
        hints.append(f"сумма — от {_rub(p.min_amount)} до {_rub(p.max_amount)}")
    if new_term != term:
        hints.append(f"срок — от {p.min_term} до {p.max_term} мес.")
    return new_amount, new_term, "Чтобы подойти под условия, измените параметры: " + ", ".join(hints) + "."


def recommend(products: list[Product], purpose: Purpose, amount: int, term: int) -> tuple[Option, list[Option]]:
    by_code = {p.code: p for p in products}
    order = list(PREFERENCE[purpose])
    # На оборудование крупную сумму или длинный срок даёт только инвестиционный кредит.
    if purpose == Purpose.EQUIPMENT and not _fits(by_code["WORKING"], amount, term):
        order = ["INVEST", "WORKING", "EXPRESS"]

    options: list[Option] = []
    for code in order:
        p = by_code[code]
        if _fits(p, amount, term):
            options.append(Option(p, True, WHY[code], amount, term, annuity_payment(amount, p.base_rate, term)))
        else:
            a, t, hint = _adjust_hint(p, amount, term)
            options.append(Option(p, False, f"{WHY[code]} {hint}", a, t, annuity_payment(a, p.base_rate, t)))

    fitting = [o for o in options if o.fits]
    best = fitting[0] if fitting else options[0]
    return best, [o for o in options if o is not best]
