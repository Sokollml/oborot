"""Финансовая арифметика."""


def annuity_payment(amount: int, annual_rate_pct: float, months: int) -> int:
    """Ежемесячный платёж равными частями (аннуитет), в рублях.

    P = S * i / (1 - (1 + i)^-n), где i — месячная ставка (годовая / 12), n — число месяцев.
    """
    i = annual_rate_pct / 100 / 12
    if i == 0:
        return round(amount / months)
    return round(amount * i / (1 - (1 + i) ** -months))
