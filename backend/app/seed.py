"""Начальные данные. Запуск: python -m app.seed (выполняется автоматически при старте api).

Скрипт идемпотентный: повторный запуск ничего не дублирует.
Цифры условные, все данные синтетические.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.enums import Role
from app.models import Product, User
from app.security import hash_password

log = logging.getLogger("seed")

PRODUCTS = [
    dict(
        code="EXPRESS",
        name="Экспресс-кредит",
        description="Быстрые деньги на любые цели бизнеса. Без залога, решение за несколько минут.",
        min_amount=100_000,
        max_amount=3_000_000,
        min_term=3,
        max_term=24,
        needs_collateral=False,
        base_rate=24.0,
    ),
    dict(
        code="WORKING",
        name="Оборотный кредит",
        description="На закупку товара, зарплаты и текущие расходы. Без залога.",
        min_amount=500_000,
        max_amount=15_000_000,
        min_term=6,
        max_term=36,
        needs_collateral=False,
        base_rate=20.0,
    ),
    dict(
        code="INVEST",
        name="Инвестиционный кредит",
        description="На оборудование, ремонт и развитие. Крупная сумма и долгий срок, нужен залог.",
        min_amount=1_000_000,
        max_amount=50_000_000,
        min_term=12,
        max_term=60,
        needs_collateral=True,
        base_rate=18.0,
    ),
]

USERS = [
    dict(email="client1@demo.local", role=Role.CLIENT, full_name="Анна Иванова"),
    dict(email="client2@demo.local", role=Role.CLIENT, full_name="Тест Тестов"),
    dict(email="analyst@demo.local", role=Role.ANALYST, full_name="Мария Петрова"),
]


def seed(db: Session) -> None:
    for data in PRODUCTS:
        product = db.scalar(select(Product).where(Product.code == data["code"]))
        if product is None:
            db.add(Product(**data))
        else:  # условия продуктов обновляем из кода, чтобы правки применялись без пересоздания базы
            for key, value in data.items():
                setattr(product, key, value)

    for data in USERS:
        if db.scalar(select(User).where(User.email == data["email"])) is None:
            db.add(User(**data, password_hash=hash_password(settings.demo_password)))

    db.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        seed(session)
    log.info("seed: готово")
