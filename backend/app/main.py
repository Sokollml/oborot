"""Точка входа API (FastAPI). Swagger доступен на /docs."""

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import analyst, applications, auth, companies, documents, messages, notifications, products
from app.db import engine
from app.errors import register_error_handlers

app = FastAPI(
    title="Оборот API",
    version="0.1.0",
    description=(
        "API цифрового кредитного конвейера для малого бизнеса. "
        "Кабинет клиента и кабинет аналитика работают с одной базой.\n\n"
        "Как попробовать в Swagger: выполните `POST /api/auth/login` (например, client1@demo.local / demo12345) — "
        "браузер сохранит cookie, и остальные запросы пойдут от этого пользователя."
    ),
)
register_error_handlers(app)

FIELD_LABELS = {
    "amount": "Сумма",
    "term_months": "Срок",
    "revenue_12m": "Выручка за 12 месяцев",
    "revenue_prev_year": "Выручка за предыдущий год",
    "monthly_debt_payments": "Платежи по другим кредитам",
    "employees": "Число сотрудников",
    "purpose": "Цель кредита",
    "inn": "ИНН",
    "email": "Email",
    "password": "Пароль",
    "code": "Код",
    "Idempotency-Key": "Ключ отправки",
}


@app.exception_handler(RequestValidationError)
def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Ошибки формата запроса — тоже по-русски: «Проверьте поля: Сумма, Срок»."""
    fields = []
    for err in exc.errors():
        name = str(err["loc"][-1]) if err.get("loc") else ""
        label = FIELD_LABELS.get(name, name)
        if label and label not in fields:
            fields.append(label)
    detail = "Проверьте поля: " + ", ".join(fields) if fields else "Проверьте введённые данные"
    return JSONResponse(status_code=422, content={"detail": detail, "errors": jsonable_errors(exc)})


def jsonable_errors(exc: RequestValidationError) -> list[dict]:
    return [{"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()]


@app.get("/health", tags=["Сервис"], summary="Проверка, что API и база доступны")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


api = APIRouter(prefix="/api")
# Тот же health под /api — чтобы его было видно через nginx фронтенда (localhost:3000/api/health).
api.add_api_route("/health", health, methods=["GET"], tags=["Сервис"], summary="Проверка через /api")
api.include_router(auth.router)
api.include_router(products.router)
api.include_router(companies.router)
api.include_router(applications.router)
api.include_router(notifications.router)
api.include_router(documents.router)
api.include_router(analyst.router)
api.include_router(messages.router)
app.include_router(api)
