"""Пароли (bcrypt) и токены входа (JWT)."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings

COOKIE_NAME = "access_token"
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:  # bcrypt 5 не принимает пароли длиннее 72 байт — такой пароль заведомо неверный
        return False


def create_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> int | None:
    """Возвращает id пользователя или None, если токен неверный или просрочен."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
