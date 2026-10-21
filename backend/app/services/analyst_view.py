"""Что видит специалист: проверки человеческим языком, скоринг по факторам и рекомендация системы."""

import math
from datetime import date

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.enums import AppStatus, CheckSource, DocStatus
from app.models import Application, CheckResult, DocumentRequest, Scoring
from app.schemas import CheckLine, CheckOut, FactorOut, RecommendationOut, ScoringOut
from app.services.finance import annuity_payment
from app.services.scoring import months_between
from app.services.scoring_config import config

CHECK_TITLES = {
    CheckSource.EGRUL: "Реестр компаний (ЕГРЮЛ)",
    CheckSource.FNS: "Налоговая (ФНС)",
    CheckSource.BKI: "Кредитная история (БКИ)",
    CheckSource.ACCOUNT: "Счёт в банке",
}
STOP_CODES = {"company_status", "overdue_90", "young_business"}
STATUS_TEXT = {"active": "действует", "liquidating": "ликвидируется", "bankrupt": "банкротство"}


def _worst(lines: list[CheckLine]) -> str:
    levels = {line.level for line in lines}
    return "bad" if "bad" in levels else "warn" if "warn" in levels else "ok"


def _rub(v: int) -> str:
    return f"{v / 1_000_000:.1f} млн ₽".replace(".", ",")


def _account_lines(p: dict, declared: int | None) -> list[CheckLine]:
    """Сверка: заявленная в анкете выручка против поступлений на счёт в нашем банке."""
    if not p.get("has_account"):
        return [CheckLine(label="Счёт в банке", value="нет — выручку подтверждает выписка", level="warn")]
    turnover = p["revenue_12m"]
    lines = [
        CheckLine(label="Поступления за 12 мес.", value=_rub(turnover), level="ok"),
        CheckLine(label="Годом ранее", value=_rub(p["revenue_prev_12m"]), level="ok"),
    ]
    if declared:
        gap = (declared - turnover) / turnover * 100 if turnover else 100.0
        level = "ok" if gap <= 20 else "warn" if gap <= 50 else "bad"
        value = "совпадает с оборотами" if abs(gap) < 1 else f"{_rub(declared)} ({'+' if gap > 0 else ''}{gap:.0f}%)"
        lines.append(CheckLine(label="Заявлено в анкете", value=value, level=level))
    return lines


def _check_lines(source: str, p: dict, declared_revenue: int | None = None) -> list[CheckLine]:
    if source == CheckSource.ACCOUNT and "error" not in p:
        return _account_lines(p, declared_revenue)
    if "error" in p:
        return [CheckLine(label="Ответ сервиса", value="не получен после всех попыток", level="bad")]
    if source == CheckSource.EGRUL:
        age = months_between(date.fromisoformat(p["registered_at"]), date.today())
        return [
            CheckLine(label="Статус", value=STATUS_TEXT.get(p["status"], p["status"]), level="ok" if p["status"] == "active" else "bad"),
            CheckLine(label="Работает", value=f"{age // 12} г. {age % 12} мес.", level="ok" if age >= 12 else "warn" if age >= 6 else "bad"),
        ]
    if source == CheckSource.FNS:
        return [
            CheckLine(label="Налоговый долг", value="есть" if p["tax_debt"] else "нет", level="bad" if p["tax_debt"] else "ok"),
            CheckLine(label="Массовый адрес", value="да" if p["mass_address"] else "нет", level="warn" if p["mass_address"] else "ok"),
        ]
    overdue = p["max_overdue_days_2y"]
    return [
        CheckLine(
            label="Просрочки за 2 года",
            value="нет" if overdue == 0 else f"до {overdue} дн.",
            level="ok" if overdue == 0 else "warn" if overdue <= 30 else "bad",
        ),
        CheckLine(label="Действующих кредитов", value=str(p["active_loans"]), level="ok"),
        CheckLine(label="Закрыто без просрочек", value=str(p["closed_loans_without_overdue"]), level="ok"),
    ]


def checks(db: Session, app_id: int, declared_revenue: int | None = None) -> list[CheckOut]:
    out = []
    for source in CheckSource:
        row = db.scalar(
            select(CheckResult)
            .where(CheckResult.application_id == app_id, CheckResult.source == source)
            .order_by(CheckResult.id.desc())
            .limit(1)
        )
        if row is None:
            continue
        lines = _check_lines(source, row.payload, declared_revenue)
        out.append(CheckOut(source=source, title=CHECK_TITLES[source], ok=row.ok, level=_worst(lines), lines=lines, fetched_at=row.fetched_at))
    return out


def latest_scoring(db: Session, app_id: int) -> Scoring | None:
    return db.scalar(select(Scoring).where(Scoring.application_id == app_id).order_by(Scoring.id.desc()).limit(1))


def scoring_out(s: Scoring | None) -> ScoringOut | None:
    if s is None:
        return None
    factors = [FactorOut(**f) for f in s.factors]
    return ScoringOut(
        total_score=s.total_score,
        risk_class=s.risk_class,
        base_score=config()["base_score"],
        factors=[f for f in factors if f.code not in STOP_CODES],
        stop_factors=[f for f in factors if f.code in STOP_CODES],
        model_version=s.model_version,
        created_at=s.created_at,
    )


def recommendation(db: Session, app: Application, s: Scoring | None) -> RecommendationOut:
    """Подсказка специалисту. Решение всё равно за человеком."""
    cfg = config()
    p = app.product
    amount, term = app.amount or 0, app.term_months or 1

    def offer(action: str, title: str, text: str, cls: str, new_amount: int) -> RecommendationOut:
        rate = p.base_rate + cfg["rate_surcharge"][cls]
        return RecommendationOut(
            action=action, title=title, text=text, amount=new_amount, term_months=term, rate=rate,
            monthly_payment=annuity_payment(new_amount, rate, term),
        )

    if s is None:
        return RecommendationOut(
            action="request_docs",
            title="Запросить выписку",
            text="Автоматическая оценка не проводилась: внешний сервис не ответил. Проверьте выручку по выписке или примите решение по данным анкеты.",
        )
    if any(f["code"] in STOP_CODES for f in s.factors):
        return RecommendationOut(action="reject", title="Отказать", text="Сработал стоп-фактор — кредит выдать нельзя.")

    cls = s.risk_class
    if cls == "A":
        return offer("approve", "Одобрить на запрошенных условиях", f"Низкий риск: {s.total_score} баллов.", cls, amount)
    if cls == "B":
        return offer("approve", "Одобрить с надбавкой к ставке", f"Умеренный риск: {s.total_score} баллов. Ставка +{cfg['rate_surcharge']['B']} п.п.", cls, amount)
    if cls == "C":
        docs_uploaded = db.scalar(
            select(exists().where(DocumentRequest.application_id == app.id, DocumentRequest.status == DocStatus.UPLOADED))
        )
        if not docs_uploaded:
            return RecommendationOut(action="request_docs", title="Запросить выписку", text=f"Повышенный риск: {s.total_score} баллов. Нужно подтвердить выручку.")
        co = cfg["counter_offer"]
        reduced = max(p.min_amount, int(math.floor(amount * co["ratio"] / co["round_to"]) * co["round_to"]))
        return offer(
            "counter",
            "Одобрить меньшую сумму",
            f"Повышенный риск: {s.total_score} баллов, выписка получена. Безопаснее снизить сумму до {int(co['ratio'] * 100)}%.",
            cls,
            reduced,
        )
    return RecommendationOut(action="reject", title="Отказать", text=f"Высокий риск: {s.total_score} баллов.")


ACTIONS_BY_STATUS: dict[AppStatus, list[str]] = {
    AppStatus.MANUAL_REVIEW: ["approve", "request_docs", "reject"],
    AppStatus.OFFER: ["approve", "reject"],  # изменить условия или отозвать, пока клиент не принял
    AppStatus.REJECTED: ["approve"],  # отменить отказ
}
