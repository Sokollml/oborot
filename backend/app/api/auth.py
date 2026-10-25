"""Вход и выход. Токен хранится в httpOnly-cookie — JavaScript страницы его не видит."""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.config import settings
from app.deps import DB, CurrentUser
from app.enums import Role
from app.errors import NotAuthenticated, TooManyRequests
from app.models import User
from app.schemas import DemoAccount, LoginIn, MetaOut, UserOut
from app.security import COOKIE_NAME, create_token, verify_password

router = APIRouter(tags=["Авторизация"])

DEMO_ACCOUNTS = [
    DemoAccount(email="client1@demo.local", role=Role.CLIENT, description="Клиент: Анна Иванова (несколько компаний)"),
    DemoAccount(email="client2@demo.local", role=Role.CLIENT, description="Клиент: Тест Тестов"),
    DemoAccount(email="analyst@demo.local", role=Role.ANALYST, description="Специалист банка"),
]


# Защита от подбора пароля: после LOGIN_MAX_FAILURES неудачных попыток за LOGIN_WINDOW_SECONDS
# вход для этого email временно закрыт. Счётчик в памяти процесса — для одного экземпляра API этого
# достаточно; при нескольких экземплярах его нужно вынести в общую базу.
LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW_SECONDS = 300
_failures: dict[str, deque[float]] = defaultdict(deque)


def _recent_failures(email: str) -> deque[float]:
    attempts = _failures[email]
    while attempts and attempts[0] < time.monotonic() - LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    return attempts


@router.post("/auth/login", response_model=UserOut, summary="Войти по email и паролю")
def login(body: LoginIn, response: Response, db: DB) -> User:
    email = body.email.strip().lower()
    failures = _recent_failures(email)
    if len(failures) >= LOGIN_MAX_FAILURES:
        raise TooManyRequests("Слишком много неудачных попыток входа. Подождите 5 минут и попробуйте снова")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        failures.append(time.monotonic())
        raise NotAuthenticated("Неверный email или пароль")
    _failures.pop(email, None)
    response.set_cookie(
        COOKIE_NAME,
        create_token(user.id, user.role),
        httponly=True,
        samesite="lax",  # cookie не уходит с запросами с чужих сайтов — защита от CSRF
        max_age=settings.jwt_ttl_minutes * 60,
        path="/",
    )
    return user


@router.post("/auth/logout", status_code=204, summary="Выйти")
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/auth/me", response_model=UserOut, summary="Текущий пользователь")
def me(user: CurrentUser) -> User:
    return user


@router.get("/meta", response_model=MetaOut, tags=["Сервис"], summary="Настройки для фронтенда (демо-режим)")
def meta() -> MetaOut:
    if not settings.demo_mode:
        return MetaOut(demo_mode=False)
    return MetaOut(demo_mode=True, demo_accounts=DEMO_ACCOUNTS, demo_password=settings.demo_password)
