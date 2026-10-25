"""Ошибки API с понятными человеку текстами.

Любая AppError превращается в ответ {"detail": "<текст>"} с нужным HTTP-кодом.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError


class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str, status_code: int | None = None):
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code


class NotAuthenticated(AppError):
    status_code = 401


class Forbidden(AppError):
    status_code = 403


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    """Действие невозможно в текущем состоянии (например, недопустимый переход статуса)."""

    status_code = 409


class ValidationFailed(AppError):
    status_code = 422


class ExternalUnavailable(AppError):
    status_code = 503


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def _handle(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # База отвергла значение (например, номер заявки или число больше, чем помещается в колонку) —
    # это ошибка во входных данных, а не сбой сервера: отвечаем 422, текст ошибки базы наружу не отдаём.
    @app.exception_handler(DataError)
    def _handle_data_error(_request: Request, _exc: DataError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": "Проверьте введённые данные: значение вне допустимых границ"})
