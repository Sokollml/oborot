"""Точка входа API (FastAPI). Swagger доступен на /docs."""

from fastapi import APIRouter, FastAPI
from sqlalchemy import text

from app.db import engine

app = FastAPI(
    title="Ступени API",
    version="0.1.0",
    description=(
        "API цифрового кредитного конвейера для малого бизнеса. "
        "Кабинет клиента и кабинет аналитика работают с одной базой."
    ),
)


@app.get("/health", tags=["service"], summary="Проверка, что API и база доступны")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


api = APIRouter(prefix="/api")
# Тот же health под /api — чтобы его было видно через nginx фронтенда (localhost:3000/api/health).
api.add_api_route("/health", health, methods=["GET"], tags=["service"], summary="Проверка через /api")
app.include_router(api)
