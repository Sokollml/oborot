"""Кабинет специалиста: очередь заявок, карточка заявки, решение.

Специалист может изменить любое решение (в рамках state machine), комментарий обязателен.
"""

from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import DB, AnalystUser
from app.enums import AppStatus, DecisionMaker, DecisionType, DocStatus
from app.errors import Conflict, NotFound, ValidationFailed
from app.models import Application, Company, Decision, DocumentRequest, Product, Scoring, StatusHistory
from app.schemas import AnalystApplicationOut, AnalystDecisionIn, DecisionOut, HistoryItem, QueueItem, StatsOut
from app.services import analyst_view, stats
from app.services.finance import annuity_payment
from app.services.state_machine import STATUS_LABELS, Actor, transition
from app.views import DOC_TITLES, application_out

router = APIRouter(prefix="/analyst", tags=["Кабинет специалиста"])

# «Ждут меня» — заявки, по которым решение за специалистом.
VIEWS: dict[str, list[AppStatus]] = {
    "mine": [AppStatus.MANUAL_REVIEW],
    "active": [
        AppStatus.SUBMITTED, AppStatus.CHECKING, AppStatus.SCORING, AppStatus.MANUAL_REVIEW,
        AppStatus.INFO_REQUESTED, AppStatus.OFFER, AppStatus.SIGNING,
    ],
    "all": [s for s in AppStatus if s != AppStatus.DRAFT],
}


@router.get("/queue", response_model=list[QueueItem], summary="Очередь заявок")
def queue(
    db: DB,
    _user: AnalystUser,
    view: Literal["mine", "active", "all"] = Query("mine", description="mine — ждут меня, active — в работе, all — все"),
    status: AppStatus | None = Query(None, description="Фильтр по статусу (важнее, чем view)"),
    product: str | None = Query(None, description="Фильтр по коду продукта", examples=["EXPRESS"]),
) -> list[QueueItem]:
    # Когда заявка попала в текущий статус = время последней записи в истории.
    entered = (
        select(StatusHistory.application_id, func.max(StatusHistory.created_at).label("at"))
        .group_by(StatusHistory.application_id)
        .subquery()
    )
    last_scoring = (
        select(Scoring.application_id, func.max(Scoring.id).label("id")).group_by(Scoring.application_id).subquery()
    )
    stmt = (
        select(Application, Company, Product, entered.c.at, Scoring)
        .join(Company, Company.id == Application.company_id)
        .join(Product, Product.id == Application.product_id)
        .join(entered, entered.c.application_id == Application.id)
        .outerjoin(last_scoring, last_scoring.c.application_id == Application.id)
        .outerjoin(Scoring, Scoring.id == last_scoring.c.id)
        .where(Application.status.in_([status] if status else VIEWS[view]))
        .order_by(entered.c.at.asc())  # дольше всех ждёт — сверху
    )
    if product:
        stmt = stmt.where(Product.code == product)
    return [
        QueueItem(
            id=a.id,
            company_name=c.name,
            company_inn=c.inn,
            product_code=p.code,
            product_name=p.name,
            amount=a.amount,
            term_months=a.term_months,
            status=a.status,
            status_label=STATUS_LABELS[AppStatus(a.status)],
            risk_class=s.risk_class if s else None,
            total_score=s.total_score if s else None,
            waiting_since=at,
        )
        for a, c, p, at, s in db.execute(stmt).all()
    ]


def _card(db: Session, app: Application) -> AnalystApplicationOut:
    s = analyst_view.latest_scoring(db, app.id)
    history = db.scalars(select(StatusHistory).where(StatusHistory.application_id == app.id).order_by(StatusHistory.id)).all()
    decisions = db.scalars(select(Decision).where(Decision.application_id == app.id).order_by(Decision.id.desc())).all()
    return AnalystApplicationOut(
        application=application_out(db, app),
        checks=analyst_view.checks(db, app.id, app.revenue_12m),
        scoring=analyst_view.scoring_out(s),
        recommendation=analyst_view.recommendation(db, app, s),
        history=[
            HistoryItem(
                from_status=h.from_status, to_status=h.to_status, to_label=STATUS_LABELS[AppStatus(h.to_status)],
                actor_type=h.actor_type, comment=h.comment, created_at=h.created_at,
            )
            for h in history
        ],
        decisions=[DecisionOut.model_validate(d) for d in decisions],
        available_actions=analyst_view.ACTIONS_BY_STATUS.get(AppStatus(app.status), []),
    )


def _get(db: Session, application_id: int, for_update: bool = False) -> Application:
    stmt = select(Application).where(Application.id == application_id)
    if for_update:
        stmt = stmt.with_for_update()
    app = db.scalar(stmt)
    if app is None or app.status == AppStatus.DRAFT:
        raise NotFound("Заявка не найдена")
    return app


@router.get("/applications/{application_id}", response_model=AnalystApplicationOut, summary="Карточка заявки")
def get_card(application_id: int, db: DB, _user: AnalystUser) -> AnalystApplicationOut:
    return _card(db, _get(db, application_id))


@router.post("/applications/{application_id}/decision", response_model=AnalystApplicationOut, summary="Решение специалиста")
def decide(application_id: int, body: AnalystDecisionIn, db: DB, user: AnalystUser) -> AnalystApplicationOut:
    app = _get(db, application_id, for_update=True)
    if body.action not in analyst_view.ACTIONS_BY_STATUS.get(AppStatus(app.status), []):
        raise Conflict(f"В статусе «{STATUS_LABELS[AppStatus(app.status)]}» это действие недоступно")
    comment = body.comment.strip()
    if not comment:
        raise ValidationFailed("Добавьте комментарий к решению")
    actor = Actor.of(user)
    p = app.product

    if body.action == "approve":
        if body.amount is None or body.term_months is None or body.rate is None:
            raise ValidationFailed("Укажите сумму, срок и ставку")
        if not p.min_amount <= body.amount <= p.max_amount:
            raise ValidationFailed(f"Сумма для «{p.name}» — от {p.min_amount:,} до {p.max_amount:,} ₽".replace(",", " "))
        if not p.min_term <= body.term_months <= p.max_term:
            raise ValidationFailed(f"Срок для «{p.name}» — от {p.min_term} до {p.max_term} месяцев")
        same = body.amount >= (app.amount or 0) and body.term_months == app.term_months
        payment = annuity_payment(body.amount, body.rate, body.term_months)
        db.add(
            Decision(
                application_id=app.id,
                type=DecisionType.APPROVE if same else DecisionType.COUNTER,
                amount=body.amount, term=body.term_months, rate=body.rate, monthly_payment=payment,
                reasons=[comment], advice=[], made_by=DecisionMaker.ANALYST, analyst_id=user.id,
            )
        )
        transition(db, app, AppStatus.OFFER, actor, comment=comment)

    elif body.action == "request_docs":
        doc_types = [d for d in dict.fromkeys(body.doc_types) if d in DOC_TITLES]
        if not doc_types:
            raise ValidationFailed("Выберите, какие документы нужны")
        for doc_type in doc_types:
            db.add(DocumentRequest(application_id=app.id, doc_type=doc_type, status=DocStatus.REQUESTED))
        db.add(
            Decision(
                application_id=app.id, type=DecisionType.INFO, reasons=[comment], advice=[],
                made_by=DecisionMaker.ANALYST, analyst_id=user.id,
            )
        )
        transition(db, app, AppStatus.INFO_REQUESTED, actor, comment=comment)

    else:  # reject
        reason = (body.client_reason or "").strip() or comment
        db.add(
            Decision(
                application_id=app.id, type=DecisionType.REJECT, reasons=[reason], advice=[],
                made_by=DecisionMaker.ANALYST, analyst_id=user.id,
            )
        )
        transition(db, app, AppStatus.REJECTED, actor, comment=comment)

    db.commit()
    return _card(db, app)


@router.get("/stats", response_model=StatsOut, summary="Аналитика конвейера: скорость, доля автоматических решений, воронка")
def get_stats(db: DB, _user: AnalystUser) -> StatsOut:
    return StatsOut(**stats.collect(db))
