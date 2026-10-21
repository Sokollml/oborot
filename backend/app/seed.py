"""Начальные данные. Запуск: python -m app.seed (выполняется автоматически при старте api).

Скрипт идемпотентный: повторный запуск ничего не дублирует.
Цифры условные, все данные синтетические.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.enums import ActorType, AppStatus, JobStatus, JobType, Role
from app.models import Application, Job, Product, StatusHistory, User
from app.security import hash_password
from app.errors import AppError
from app.services.state_machine import Actor, transition

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


# Готовые заявки, чтобы очередь специалиста не была пустой с первой минуты,
# а у client2 была своя заявка (для проверки «чужая заявка → 403»).
# Они создаются как ОТПРАВЛЕННЫЕ — воркер сам проведёт их по конвейеру при первом запуске.
DEMO_APPLICATIONS = [
    dict(
        owner="client1@demo.local",
        inn="0010000088",  # ООО «Сфера-Тест» → инвестиционный кредит → к специалисту
        product="INVEST",
        purpose="equipment",
        amount=12_000_000,
        term_months=36,
        revenue_12m=90_000_000,
        revenue_prev_year=80_000_000,
        monthly_debt_payments=150_000,
        employees=40,
        collateral_description="Производственное оборудование (линия литья), оценочная стоимость 18 млн ₽",
    ),
    dict(
        owner="client2@demo.local",
        inn="0010000063",  # ООО «Новичок-Тест» → бизнесу 4 месяца → отказ по стоп-фактору
        product="EXPRESS",
        purpose="urgent",
        amount=500_000,
        term_months=12,
        revenue_12m=3_000_000,
        revenue_prev_year=0,
        monthly_debt_payments=0,
        employees=3,
        collateral_description=None,
    ),
]


def seed_demo_applications(db: Session) -> None:
    from app.api.companies import get_or_create_company  # локальный импорт: избегаем цикла

    if db.scalar(select(Application.id).limit(1)) is not None:
        return  # не первый запуск
    for item in DEMO_APPLICATIONS:
        data = dict(item)
        user = db.scalar(select(User).where(User.email == data.pop("owner")))
        company = get_or_create_company(db, user, data.pop("inn"))
        product = db.scalar(select(Product).where(Product.code == data.pop("product")))
        app = Application(company_id=company.id, product_id=product.id, bki_consent=True, status=AppStatus.DRAFT, **data)
        db.add(app)
        db.flush()
        db.add(StatusHistory(application_id=app.id, to_status=AppStatus.DRAFT, actor_type=ActorType.CLIENT, actor_id=user.id))
        app.idempotency_key = f"seed-{app.id}"
        transition(db, app, AppStatus.SUBMITTED, Actor.of(user))
        db.add(Job(type=JobType.PROCESS_APPLICATION, application_id=app.id, status=JobStatus.PENDING))
    db.commit()
    log.info("seed: созданы демо-заявки")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        seed(session)
        try:
            seed_demo_applications(session)
        except AppError as exc:
            # Без мок-сервиса демо-заявки не создать, но API должен запуститься всё равно.
            session.rollback()
            log.warning("seed: демо-заявки не созданы (%s), попробую при следующем запуске", exc)
    log.info("seed: готово")
