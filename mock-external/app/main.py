"""Мок внешних сервисов: ЕГРЮЛ, ФНС, БКИ.

Отдаёт заранее заготовленные синтетические данные из data/companies.json.
Настоящих систем банка и государства здесь нет.

Особенности для демо:
- MOCK_DELAY_SECONDS — искусственная задержка каждого ответа;
- у компании с "bki_timeout": true сервис БКИ «зависает» и не отвечает дольше таймаута клиента.
"""

import asyncio
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Мок внешних сервисов",
    version="0.1.0",
    description="Имитация ЕГРЮЛ, ФНС и БКИ на синтетических данных.",
)

DELAY = float(os.getenv("MOCK_DELAY_SECONDS", "0.3"))
HANG_SECONDS = 30  # заведомо дольше таймаута клиента (3 с)

_DATA = json.loads((Path(__file__).parent / "data" / "companies.json").read_text(encoding="utf-8"))
COMPANIES: dict[str, dict[str, Any]] = {c["inn"]: c for c in _DATA["companies"]}


def _months_ago(months: int) -> date:
    """Дата регистрации считается от сегодняшнего дня — возраст бизнеса в сценариях не «стареет»."""
    today = date.today()
    total = today.year * 12 + (today.month - 1) - months
    return date(total // 12, total % 12 + 1, min(today.day, 28))


async def _company(inn: str) -> dict[str, Any]:
    await asyncio.sleep(DELAY)
    company = COMPANIES.get(inn)
    if company is None:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return company


@app.get("/health", tags=["service"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/egrul/{inn}", tags=["ЕГРЮЛ"], summary="Сведения о компании из реестра")
async def egrul(inn: str) -> dict[str, Any]:
    c = await _company(inn)
    return {
        "inn": c["inn"],
        "name": c["name"],
        "ogrn": c["ogrn"],
        "registered_at": _months_ago(c["registered_months_ago"]).isoformat(),
        "status": c["status"],
        "director": c["director"],
        "okved": c["okved"],
    }


@app.get("/fns/{inn}", tags=["ФНС"], summary="Налоговая: долги и массовый адрес")
async def fns(inn: str) -> dict[str, Any]:
    c = await _company(inn)
    return {"inn": inn, **c["fns"]}


def _month_label(months_ago: int) -> str:
    d = _months_ago(months_ago)
    return f"{d.year}-{d.month:02d}"


@app.get("/abs/accounts/{inn}", tags=["АБС банка"], summary="Расчётный счёт клиента в банке: обороты за 24 месяца")
async def account(inn: str) -> dict[str, Any]:
    """Данные «своего» банка (автоматизированной банковской системы): есть ли у компании счёт и сколько на него
    поступало. Так банк знает выручку клиента без справок и выписок. Компании без счёта — has_account: false."""
    c = await _company(inn)
    acc = c.get("account")
    if not acc:
        return {"inn": inn, "has_account": False}
    monthly = acc["monthly_incoming"]  # 24 месяца, от старых к новым
    return {
        "inn": inn,
        "has_account": True,
        "opened_at": _months_ago(acc["opened_months_ago"]).isoformat(),
        "months": [{"month": _month_label(24 - i), "incoming": v} for i, v in enumerate(monthly)],
        "revenue_12m": sum(monthly[12:]),
        "revenue_prev_12m": sum(monthly[:12]),
    }


@app.get("/bki/{inn}", tags=["БКИ"], summary="Кредитная история")
async def bki(inn: str) -> dict[str, Any]:
    c = await _company(inn)
    if c.get("bki_timeout"):
        await asyncio.sleep(HANG_SECONDS)
    return {"inn": inn, **(c["bki"] or {})}
