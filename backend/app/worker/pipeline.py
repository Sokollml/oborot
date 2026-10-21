"""Кредитный конвейер: что воркер делает с заявкой.

    SUBMITTED → CHECKING → SCORING → OFFER | MANUAL_REVIEW | INFO_REQUESTED | REJECTED

Каждый этап — отдельная короткая транзакция: заблокировали заявку, проверили, что статус
тот, что ожидаем, сделали работу, сменили статус через transition(), сохранили.
Поэтому конвейер можно прервать в любой момент (упал воркер, перезапустили контейнер) —
при следующем запуске он продолжит с текущего статуса заявки, ничего не делая дважды.

Между этапами — пауза STAGE_DELAY_SECONDS (по умолчанию 2 с), чтобы на демо было видно,
как статус движется по ленте.
"""

import logging
import time
from collections.abc import Callable

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.enums import AppStatus, CheckSource, DecisionMaker, DocStatus
from app.models import Application, CheckResult, Decision, DocumentRequest, Scoring
from app.services import external
from app.services.decision import decide
from app.services.scoring import ScoringInput, score
from app.services.state_machine import Actor, transition

log = logging.getLogger("worker.pipeline")
SYSTEM = Actor.system()


def _lock(db: Session, application_id: int) -> Application:
    return db.scalar(select(Application).where(Application.id == application_id).with_for_update())


# ---------- Этап 1: отправлена → проверка ----------


def stage_submitted(application_id: int) -> None:
    with SessionLocal() as db, db.begin():
        app = _lock(db, application_id)
        if app.status == AppStatus.SUBMITTED:
            transition(db, app, AppStatus.CHECKING, SYSTEM)


# ---------- Этап 2: проверка во внешних сервисах ----------


def stage_checking(application_id: int) -> None:
    with SessionLocal() as db:
        app = db.get(Application, application_id)
        if app is None or app.status != AppStatus.CHECKING:
            return
        inn = app.company.inn

    # Сетевые запросы делаем ВНЕ транзакции, чтобы не держать блокировку заявки десятки секунд.
    results: dict[CheckSource, dict] = {}
    failures: list[str] = []
    for source in (CheckSource.EGRUL, CheckSource.FNS, CheckSource.BKI):
        try:
            results[source] = external.fetch(source, inn)
        except (external.ExternalServiceError, external.CompanyNotFoundInRegistry) as exc:
            log.warning("заявка %s: %s недоступен: %s", application_id, source, exc)
            failures.append(external.SOURCE_NAMES[source])
            results[source] = {"error": str(exc) or "нет данных"}

    with SessionLocal() as db, db.begin():
        app = _lock(db, application_id)
        if app.status != AppStatus.CHECKING:
            return
        for source, payload in results.items():
            db.add(CheckResult(application_id=app.id, source=source, ok="error" not in payload, payload=payload))
        egrul = results[CheckSource.EGRUL]
        if "error" not in egrul:  # обновляем статус компании по свежим данным реестра
            app.company.status = egrul["status"]

        if failures:
            # Сервис так и не ответил после всех повторов — не «зависаем», а отдаём человеку.
            transition(
                db,
                app,
                AppStatus.MANUAL_REVIEW,
                SYSTEM,
                comment="Не удалось получить данные: " + ", ".join(failures) + ". Заявку проверит специалист.",
            )
        else:
            transition(db, app, AppStatus.SCORING, SYSTEM)


# ---------- Этап 3: скоринг и решение ----------


def _latest_check(db: Session, application_id: int, source: CheckSource) -> dict:
    row = db.scalar(
        select(CheckResult)
        .where(CheckResult.application_id == application_id, CheckResult.source == source)
        .order_by(CheckResult.id.desc())
        .limit(1)
    )
    return row.payload


def scoring_input(db: Session, app: Application) -> ScoringInput:
    egrul = _latest_check(db, app.id, CheckSource.EGRUL)
    fns = _latest_check(db, app.id, CheckSource.FNS)
    bki = _latest_check(db, app.id, CheckSource.BKI)
    return ScoringInput(
        amount=app.amount,
        term_months=app.term_months,
        base_rate=app.product.base_rate,
        revenue_12m=app.revenue_12m,
        revenue_prev_year=app.revenue_prev_year,
        monthly_debt_payments=app.monthly_debt_payments,
        registered_at=app.company.registered_at,
        company_status=egrul["status"],
        tax_debt=fns["tax_debt"],
        mass_address=fns["mass_address"],
        active_loans=bki["active_loans"],
        max_overdue_days_2y=bki["max_overdue_days_2y"],
        closed_loans_without_overdue=bki["closed_loans_without_overdue"],
    )


def stage_scoring(application_id: int) -> None:
    with SessionLocal() as db, db.begin():
        app = _lock(db, application_id)
        if app.status != AppStatus.SCORING:
            return

        data = scoring_input(db, app)
        result = score(data)
        db.add(
            Scoring(
                application_id=app.id,
                total_score=result.total_score,
                risk_class=result.risk_class,
                factors=[f.as_dict() for f in result.stop_factors + result.factors],
                model_version=result.model_version,
            )
        )

        docs_requested = db.scalar(select(exists().where(DocumentRequest.application_id == app.id)))
        outcome = decide(app.product.code, app.product.name, app.product.min_amount, data, result, docs_requested)

        if outcome.decision_type is not None:
            db.add(
                Decision(
                    application_id=app.id,
                    type=outcome.decision_type,
                    amount=outcome.amount,
                    term=outcome.term,
                    rate=outcome.rate,
                    monthly_payment=outcome.monthly_payment,
                    reasons=outcome.reasons,
                    advice=outcome.advice,
                    made_by=DecisionMaker.AUTO,
                )
            )
        for doc_type in outcome.request_docs:
            db.add(DocumentRequest(application_id=app.id, doc_type=doc_type, status=DocStatus.REQUESTED))

        transition(db, app, outcome.target_status, SYSTEM, comment=outcome.history_comment)
        log.info("заявка %s: класс %s (%s баллов) → %s", app.id, result.risk_class, result.total_score, outcome.target_status)


# ---------- Весь конвейер ----------

STAGES: dict[AppStatus, Callable[[int], None]] = {
    AppStatus.SUBMITTED: stage_submitted,
    AppStatus.CHECKING: stage_checking,
    AppStatus.SCORING: stage_scoring,
}


def process_application(application_id: int, should_stop: Callable[[], bool] = lambda: False) -> bool:
    """Ведёт заявку по этапам, пока она в статусах конвейера.

    Возвращает False, если остановились досрочно по should_stop (задачу нужно вернуть в очередь).
    """
    first = True
    while True:
        with SessionLocal() as db:
            status = db.scalar(select(Application.status).where(Application.id == application_id))
        stage = STAGES.get(AppStatus(status)) if status else None
        if stage is None:
            return True  # заявка вышла из конвейера: предложение, отказ, ручное рассмотрение…
        if should_stop():
            return False
        if not first:
            time.sleep(settings.stage_delay_seconds)  # пауза для демо: видно, как статус движется
        first = False
        stage(application_id)
