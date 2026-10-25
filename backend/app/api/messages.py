"""Переписка по заявке между клиентом и специалистом. Новое сообщение — уведомление собеседнику в кабинете."""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import DB, AnalystUser, ClientUser, get_owned_application
from app.enums import AppStatus, Role
from app.errors import Conflict, NotFound, ValidationFailed
from app.models import Application, ApplicationMessage, Company, Notification, User
from app.schemas import MessageIn, MessageOut

router = APIRouter(tags=["Переписка"])


def _list(db: Session, app_id: int) -> list[MessageOut]:
    rows = db.execute(
        select(ApplicationMessage, User.full_name)
        .join(User, User.id == ApplicationMessage.author_id)
        .where(ApplicationMessage.application_id == app_id)
        .order_by(ApplicationMessage.id)
    ).all()
    return [
        MessageOut(id=m.id, author_role=m.author_role, author_name=name, text=m.text, created_at=m.created_at)
        for m, name in rows
    ]


def _post(db: Session, app: Application, user: User, text: str) -> list[MessageOut]:
    if app.status == AppStatus.DRAFT:
        raise Conflict("Задать вопрос можно после отправки заявки")
    text = text.strip()
    if not text:
        raise ValidationFailed("Напишите текст сообщения")
    db.add(ApplicationMessage(application_id=app.id, author_id=user.id, author_role=user.role, text=text))
    if user.role == Role.CLIENT:
        recipients = db.scalars(select(User.id).where(User.role == Role.ANALYST)).all()
        note = f"Клиент написал по заявке №{app.id}"
    else:
        recipients = [db.scalar(select(Company.owner_user_id).where(Company.id == app.company_id))]
        note = f"Специалист ответил по заявке №{app.id}"
    for uid in recipients:
        db.add(Notification(user_id=uid, application_id=app.id, text=note))
    db.commit()
    return _list(db, app.id)


@router.get("/applications/{application_id}/messages", response_model=list[MessageOut], summary="Переписка по заявке")
def client_messages(application_id: int, db: DB, user: ClientUser) -> list[MessageOut]:
    get_owned_application(db, application_id, user)
    return _list(db, application_id)


@router.post("/applications/{application_id}/messages", response_model=list[MessageOut], summary="Написать специалисту")
def client_post(application_id: int, body: MessageIn, db: DB, user: ClientUser) -> list[MessageOut]:
    return _post(db, get_owned_application(db, application_id, user), user, body.text)


def _analyst_app(db: Session, application_id: int) -> Application:
    app = db.get(Application, application_id)
    if app is None or app.status == AppStatus.DRAFT:
        raise NotFound("Заявка не найдена")
    return app


@router.get("/analyst/applications/{application_id}/messages", response_model=list[MessageOut], tags=["Кабинет специалиста"], summary="Переписка с клиентом")
def analyst_messages(application_id: int, db: DB, _user: AnalystUser) -> list[MessageOut]:
    return _list(db, _analyst_app(db, application_id).id)


@router.post("/analyst/applications/{application_id}/messages", response_model=list[MessageOut], tags=["Кабинет специалиста"], summary="Написать клиенту")
def analyst_post(application_id: int, body: MessageIn, db: DB, user: AnalystUser) -> list[MessageOut]:
    return _post(db, _analyst_app(db, application_id), user, body.text)
