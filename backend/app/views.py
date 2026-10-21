"""Сборка ответов API из моделей (чтобы роуты клиента и аналитика отдавали одно и то же)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AppStatus
from app.models import Application, Decision, DocumentRequest
from app.schemas import ApplicationListItem, ApplicationOut, DecisionOut, DocumentRequestOut, NextActionOut
from app.services.next_action import next_action
from app.services.state_machine import STATUS_LABELS

DOC_TITLES = {
    "bank_statement": "Выписка по расчётному счёту за последние 12 месяцев",
    "financial_report": "Бухгалтерская отчётность за последний год",
    "collateral_docs": "Документы на имущество, которое будет в залоге",
    "other": "Дополнительный документ",
}


def latest_decision(db: Session, application_id: int) -> Decision | None:
    return db.scalar(
        select(Decision).where(Decision.application_id == application_id).order_by(Decision.id.desc()).limit(1)
    )


def application_out(db: Session, app: Application) -> ApplicationOut:
    decision = latest_decision(db, app.id)
    docs = db.scalars(
        select(DocumentRequest).where(DocumentRequest.application_id == app.id).order_by(DocumentRequest.id)
    ).all()
    status = AppStatus(app.status)
    return ApplicationOut(
        id=app.id,
        status=status,
        status_label=STATUS_LABELS[status],
        next_action=NextActionOut(**vars(next_action(status, decision.type if decision else None))),
        product=app.product,
        company=app.company,
        purpose=app.purpose,
        amount=app.amount,
        term_months=app.term_months,
        revenue_12m=app.revenue_12m,
        revenue_prev_year=app.revenue_prev_year,
        monthly_debt_payments=app.monthly_debt_payments,
        employees=app.employees,
        collateral_description=app.collateral_description,
        bki_consent=app.bki_consent,
        decision=DecisionOut.model_validate(decision) if decision else None,
        documents=[
            DocumentRequestOut(
                id=d.id, doc_type=d.doc_type, title=DOC_TITLES.get(d.doc_type, d.doc_type), status=d.status, file_name=d.file_name
            )
            for d in docs
        ],
        signing_code=app.signing_code if status == AppStatus.SIGNING else None,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


def application_list_item(app: Application) -> ApplicationListItem:
    status = AppStatus(app.status)
    return ApplicationListItem(
        id=app.id,
        status=status,
        status_label=STATUS_LABELS[status],
        action_required=next_action(status).action_required,
        product_name=app.product.name,
        company_name=app.company.name,
        amount=app.amount,
        term_months=app.term_months,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )
