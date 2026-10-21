"""Заявки клиента: черновик, отправка, статус, действия с предложением.

Каждый запрос к конкретной заявке проходит через get_owned_application():
чужая заявка → 403. Статус меняется только через transition().
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.companies import get_or_create_company
from app.services import external
from app.deps import DB, ClientUser, get_owned_application
from app.enums import ActorType, AppStatus, CheckSource, JobStatus, JobType
from app.errors import Conflict, NotFound, ValidationFailed
from app.models import Application, Company, Job, Product, StatusHistory
from app.schemas import (
    ApplicationCreate,
    ApplicationListItem,
    ApplicationOut,
    ApplicationPatch,
    HistoryItem,
    SignIn,
)
from app.services.state_machine import STATUS_LABELS, Actor, transition
from app.views import application_list_item, application_out

router = APIRouter(tags=["Заявки клиента"])


def _product(db: Session, code: str) -> Product:
    product = db.scalar(select(Product).where(Product.code == code))
    if product is None:
        raise NotFound("Такого кредитного продукта нет")
    return product


def _account(inn: str) -> dict | None:
    try:
        data = external.fetch(CheckSource.ACCOUNT, inn, retries=1, timeout=2.0)
    except (external.ExternalServiceError, external.CompanyNotFoundInRegistry):
        return None  # без оборотов клиент просто введёт выручку сам
    return data if data.get("has_account") else None


def _rub(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " ₽"


MIN_REVENUE = 100_000  # меньше — почти наверняка опечатка (ввели тысячи или миллионы вместо рублей)


def _missing_for_submit(app: Application) -> list[str]:
    """Что ещё не заполнено или не подходит под условия продукта — человеческим языком."""
    p = app.product
    problems: list[str] = []
    if app.amount is None:
        problems.append("укажите сумму кредита")
    elif not p.min_amount <= app.amount <= p.max_amount:
        problems.append(f"сумма для «{p.name}» — от {_rub(p.min_amount)} до {_rub(p.max_amount)}")
    if app.term_months is None:
        problems.append("укажите срок кредита")
    elif not p.min_term <= app.term_months <= p.max_term:
        problems.append(f"срок для «{p.name}» — от {p.min_term} до {p.max_term} месяцев")
    if not app.revenue_12m:
        problems.append("укажите выручку за последние 12 месяцев")
    elif app.revenue_12m < MIN_REVENUE:
        problems.append("выручка похожа на опечатку — укажите сумму в рублях, не меньше 100 000 ₽")
    if app.revenue_prev_year is None:
        problems.append("укажите выручку за предыдущий год")
    if app.monthly_debt_payments is None:
        problems.append("укажите ежемесячные платежи по другим кредитам (0, если их нет)")
    if app.employees is None:
        problems.append("укажите число сотрудников")
    if p.needs_collateral and not (app.collateral_description or "").strip():
        problems.append("опишите, что можно оставить в залог")
    if not app.bki_consent:
        problems.append("подтвердите согласие на запрос кредитной истории")
    return problems


@router.get("/applications", response_model=list[ApplicationListItem], summary="Мои заявки")
def list_applications(db: DB, user: ClientUser) -> list[ApplicationListItem]:
    apps = db.scalars(
        select(Application)
        .join(Company)
        .where(Company.owner_user_id == user.id)
        .order_by(Application.updated_at.desc())
    ).all()
    return [application_list_item(a) for a in apps]


@router.post("/applications", response_model=ApplicationOut, status_code=201, summary="Создать черновик заявки")
def create_application(body: ApplicationCreate, db: DB, user: ClientUser) -> ApplicationOut:
    product = _product(db, body.product_code)
    company = get_or_create_company(db, user, body.inn)
    # Начальный статус задаётся при создании; дальше — только через transition().
    app = Application(
        company_id=company.id,
        product_id=product.id,
        purpose=body.purpose,
        amount=body.amount,
        term_months=body.term_months,
        status=AppStatus.DRAFT,
    )
    # Компания обслуживается в банке → выручку берём из оборотов по счёту, клиенту остаётся проверить.
    account = _account(company.inn)
    if account:
        app.revenue_12m = account["revenue_12m"]
        app.revenue_prev_year = account["revenue_prev_12m"]
        app.revenue_prefilled = True
    db.add(app)
    db.flush()
    db.add(StatusHistory(application_id=app.id, from_status=None, to_status=AppStatus.DRAFT, actor_type=ActorType.CLIENT, actor_id=user.id))
    db.commit()
    return application_out(db, app)


@router.get("/applications/{application_id}", response_model=ApplicationOut, summary="Заявка и что делать дальше")
def get_application(application_id: int, db: DB, user: ClientUser) -> ApplicationOut:
    return application_out(db, get_owned_application(db, application_id, user))


@router.patch("/applications/{application_id}", response_model=ApplicationOut, summary="Сохранить черновик")
def patch_application(application_id: int, body: ApplicationPatch, db: DB, user: ClientUser) -> ApplicationOut:
    app = get_owned_application(db, application_id, user, for_update=True)
    if app.status != AppStatus.DRAFT:
        raise Conflict("Отправленную заявку уже нельзя изменить")
    changes = body.model_dump(exclude_unset=True)
    if code := changes.pop("product_code", None):
        app.product_id = _product(db, code).id
    for field, value in changes.items():
        setattr(app, field, value)
    db.commit()
    db.refresh(app)
    return application_out(db, app)


@router.post("/applications/{application_id}/submit", response_model=ApplicationOut, summary="Отправить заявку")
def submit_application(
    application_id: int,
    db: DB,
    user: ClientUser,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=128,
            description="Уникальный ключ отправки. Повторный запрос с тем же ключом не создаёт вторую отправку.",
        ),
    ],
) -> ApplicationOut:
    """Отправка заявки на рассмотрение.

    Идемпотентность: если клиент нажал «Отправить» дважды или пропала сеть и браузер повторил
    запрос — второй запрос с тем же Idempotency-Key просто вернёт текущее состояние заявки.
    Заявка и задача для воркера сохраняются в ОДНОЙ транзакции: либо обе, либо ничего.
    """
    app = get_owned_application(db, application_id, user, for_update=True)

    # Повтор того же запроса — ничего не делаем, отвечаем текущим состоянием.
    if app.idempotency_key == idempotency_key:
        return application_out(db, app)

    if app.status != AppStatus.DRAFT:
        raise Conflict(f"Заявка уже отправлена (статус «{STATUS_LABELS[AppStatus(app.status)]}»)")
    if db.scalar(select(Application.id).where(Application.idempotency_key == idempotency_key)):
        raise Conflict("Этот ключ отправки уже использован для другой заявки")

    problems = _missing_for_submit(app)
    if problems:
        raise ValidationFailed("Чтобы отправить заявку: " + "; ".join(problems))

    app.idempotency_key = idempotency_key
    transition(db, app, AppStatus.SUBMITTED, Actor.of(user))
    db.add(Job(type=JobType.PROCESS_APPLICATION, application_id=app.id, status=JobStatus.PENDING))
    db.commit()
    return application_out(db, app)


@router.post(
    "/applications/{application_id}/clone",
    response_model=ApplicationOut,
    status_code=201,
    summary="Подать заново с этими данными",
)
def clone_application(application_id: int, db: DB, user: ClientUser) -> ApplicationOut:
    """Новый черновик с копией анкеты. Старая заявка остаётся как есть (для истории)."""
    old = get_owned_application(db, application_id, user)
    if old.status not in (AppStatus.REJECTED, AppStatus.CANCELLED):
        raise Conflict("Подать заново можно после отказа или отмены заявки")
    app = Application(
        company_id=old.company_id,
        product_id=old.product_id,
        purpose=old.purpose,
        amount=old.amount,
        term_months=old.term_months,
        revenue_12m=old.revenue_12m,
        revenue_prev_year=old.revenue_prev_year,
        monthly_debt_payments=old.monthly_debt_payments,
        employees=old.employees,
        collateral_description=old.collateral_description,
        bki_consent=False,  # согласие даётся заново на каждую заявку
        status=AppStatus.DRAFT,
    )
    db.add(app)
    db.flush()
    db.add(
        StatusHistory(
            application_id=app.id,
            from_status=None,
            to_status=AppStatus.DRAFT,
            actor_type=ActorType.CLIENT,
            actor_id=user.id,
            comment=f"Создана на основе заявки №{old.id}",
        )
    )
    db.commit()
    return application_out(db, app)


@router.get("/applications/{application_id}/history", response_model=list[HistoryItem], summary="История статусов")
def get_history(application_id: int, db: DB, user: ClientUser) -> list[HistoryItem]:
    get_owned_application(db, application_id, user)
    rows = db.scalars(
        select(StatusHistory).where(StatusHistory.application_id == application_id).order_by(StatusHistory.id)
    ).all()
    return [
        HistoryItem(
            from_status=r.from_status,
            to_status=r.to_status,
            to_label=STATUS_LABELS[AppStatus(r.to_status)],
            actor_type=r.actor_type,
            comment=r.comment,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ---------- Действия клиента ----------


@router.post("/applications/{application_id}/cancel", response_model=ApplicationOut, summary="Отозвать черновик")
def cancel_application(application_id: int, db: DB, user: ClientUser) -> ApplicationOut:
    app = get_owned_application(db, application_id, user, for_update=True)
    if app.status != AppStatus.DRAFT:
        raise Conflict("Отозвать можно только неотправленный черновик")
    transition(db, app, AppStatus.CANCELLED, Actor.of(user), comment="Клиент отозвал заявку")
    db.commit()
    return application_out(db, app)


@router.post("/applications/{application_id}/offer/accept", response_model=ApplicationOut, summary="Принять предложение")
def accept_offer(application_id: int, db: DB, user: ClientUser) -> ApplicationOut:
    app = get_owned_application(db, application_id, user, for_update=True)
    transition(db, app, AppStatus.SIGNING, Actor.of(user), comment="Клиент принял предложение")
    # Симуляция подписи: код генерируется здесь и показывается клиенту на экране (никаких SMS).
    app.signing_code = f"{secrets.randbelow(1_000_000):06d}"
    db.commit()
    return application_out(db, app)


@router.post("/applications/{application_id}/offer/decline", response_model=ApplicationOut, summary="Отказаться от предложения")
def decline_offer(application_id: int, db: DB, user: ClientUser) -> ApplicationOut:
    app = get_owned_application(db, application_id, user, for_update=True)
    if app.status != AppStatus.OFFER:
        raise Conflict("Отказаться можно только от действующего предложения")
    transition(db, app, AppStatus.CANCELLED, Actor.of(user), comment="Клиент отказался от предложения")
    db.commit()
    return application_out(db, app)


@router.post("/applications/{application_id}/sign", response_model=ApplicationOut, summary="Подписать договор кодом")
def sign(application_id: int, body: SignIn, db: DB, user: ClientUser) -> ApplicationOut:
    app = get_owned_application(db, application_id, user, for_update=True)
    if app.status != AppStatus.SIGNING:
        raise Conflict("Подписать можно только принятое предложение")
    if body.code.strip() != app.signing_code:
        raise ValidationFailed("Код не совпадает. Проверьте цифры на экране")
    transition(db, app, AppStatus.ISSUED, Actor.of(user), comment="Договор подписан кодом, деньги зачислены")
    db.commit()
    return application_out(db, app)
