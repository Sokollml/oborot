"""Общие зависимости FastAPI: текущий пользователь, проверка роли и владельца заявки."""

from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.enums import Role
from app.errors import Forbidden, NotAuthenticated, NotFound
from app.models import Application, Company, RevokedToken, User
from app.security import COOKIE_NAME, decode_token

DB = Annotated[Session, Depends(get_db)]


def get_current_user(db: DB, access_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None) -> User:
    token = decode_token(access_token) if access_token else None
    # Токен после выхода отозван — даже если кто-то сохранил cookie, войти по нему нельзя.
    if token is not None and db.get(RevokedToken, token.jti) is not None:
        token = None
    user = db.get(User, token.user_id) if token else None
    if user is None:
        raise NotAuthenticated("Войдите в кабинет, чтобы продолжить")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_client(user: CurrentUser) -> User:
    if user.role != Role.CLIENT:
        raise Forbidden("Этот раздел доступен только клиентам")
    return user


def require_analyst(user: CurrentUser) -> User:
    if user.role != Role.ANALYST:
        raise Forbidden("Этот раздел доступен только сотрудникам банка")
    return user


ClientUser = Annotated[User, Depends(require_client)]
AnalystUser = Annotated[User, Depends(require_analyst)]


def get_owned_application(db: Session, application_id: int, user: User, *, for_update: bool = False) -> Application:
    """Заявка, к которой у клиента есть доступ.

    Проверка владельца выполняется на КАЖДОМ запросе клиента к заявке:
    чужая заявка → 403, несуществующая → 404.
    for_update=True блокирует строку до конца транзакции (защита от гонок с воркером).
    """
    stmt = select(Application).where(Application.id == application_id)
    if for_update:
        stmt = stmt.with_for_update()
    app = db.scalar(stmt)
    if app is None:
        raise NotFound("Заявка не найдена")
    owner_id = db.scalar(select(Company.owner_user_id).where(Company.id == app.company_id))
    if owner_id != user.id:
        raise Forbidden("Это чужая заявка — у вас нет к ней доступа")
    return app
