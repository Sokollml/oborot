"""Таблицы базы данных (SQLAlchemy 2).

Деньги хранятся в целых рублях (BigInteger), ставки — в процентах годовых (Float).
Статусы и прочие перечисления — строками (значения из app/enums.py).
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)


class Company(Base):
    __tablename__ = "companies"
    # Одну и ту же компанию могут завести разные пользователи — у каждого своя запись.
    __table_args__ = (UniqueConstraint("owner_user_id", "inn"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    inn: Mapped[str] = mapped_column(String(12), nullable=False)
    ogrn: Mapped[str] = mapped_column(String(15), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    okved: Mapped[str] = mapped_column(String(255), nullable=False)
    registered_at: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    director: Mapped[str] = mapped_column(String(255), nullable=False)
    # Предодобренный лимит («кредитный потенциал»): результат последнего расчёта и когда он сделан.
    potential: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    potential_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    min_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_term: Mapped[int] = mapped_column(Integer, nullable=False)
    max_term: Mapped[int] = mapped_column(Integer, nullable=False)
    needs_collateral: Mapped[bool] = mapped_column(Boolean, nullable=False)
    base_rate: Mapped[float] = mapped_column(Float, nullable=False)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int | None] = mapped_column(BigInteger)
    term_months: Mapped[int | None] = mapped_column(Integer)
    revenue_12m: Mapped[int | None] = mapped_column(BigInteger)
    revenue_prev_year: Mapped[int | None] = mapped_column(BigInteger)
    monthly_debt_payments: Mapped[int | None] = mapped_column(BigInteger)
    employees: Mapped[int | None] = mapped_column(Integer)
    collateral_description: Mapped[str | None] = mapped_column(Text)
    bki_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Выручка подставлена из оборотов по счёту в банке (клиент мог её поправить).
    revenue_prefilled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Меняется ТОЛЬКО через services.state_machine.transition().
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Код подписания (симуляция): генерируется при переходе в SIGNING и показывается клиенту.
    signing_code: Mapped[str | None] = mapped_column(String(6))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company: Mapped[Company] = relationship()
    product: Mapped[Product] = relationship()


class StatusHistory(Base):
    __tablename__ = "status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class CheckResult(Base):
    __tablename__ = "check_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = _created_at()


class Scoring(Base):
    __tablename__ = "scorings"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_class: Mapped[str] = mapped_column(String(1), nullable=False)
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[int | None] = mapped_column(BigInteger)
    term: Mapped[int | None] = mapped_column(Integer)
    rate: Mapped[float | None] = mapped_column(Float)
    monthly_payment: Mapped[int | None] = mapped_column(BigInteger)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    advice: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    made_by: Mapped[str] = mapped_column(String(16), nullable=False)
    analyst_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _created_at()


class DocumentRequest(Base):
    __tablename__ = "document_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512))
    file_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = _created_at()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class ApplicationMessage(Base):
    """Переписка по заявке между клиентом и специалистом."""

    __tablename__ = "application_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    author_role: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Job(Base):
    """Задача для воркера. Очередь живёт прямо в Postgres.

    run_after: для pending — «не раньше чем»; для running — срок «аренды».
    Если воркер упал посреди задачи, аренда истекает и задачу подхватывает следующий запуск.
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
