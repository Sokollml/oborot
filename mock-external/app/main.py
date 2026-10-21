"""Мок внешних сервисов: ЕГРЮЛ, ФНС, БКИ.

Отдаёт заранее заготовленные синтетические данные. Настоящих систем банка здесь нет.
Эндпоинты /egrul, /fns, /bki появятся в фазе 2.
"""

from fastapi import FastAPI

app = FastAPI(title="Мок внешних сервисов", version="0.1.0")


@app.get("/health", tags=["service"])
def health() -> dict[str, str]:
    return {"status": "ok"}
