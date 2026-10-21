"""Перечисления предметной области. В базе хранятся как строки."""

from enum import StrEnum


class Role(StrEnum):
    CLIENT = "client"
    ANALYST = "analyst"


class AppStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    CHECKING = "CHECKING"
    SCORING = "SCORING"
    OFFER = "OFFER"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    INFO_REQUESTED = "INFO_REQUESTED"
    REJECTED = "REJECTED"
    SIGNING = "SIGNING"
    ISSUED = "ISSUED"
    CANCELLED = "CANCELLED"


class ActorType(StrEnum):
    CLIENT = "client"
    ANALYST = "analyst"
    SYSTEM = "system"


class Purpose(StrEnum):
    STOCK_SALARY = "stock_salary"  # товар, зарплаты, текущие расходы
    EQUIPMENT = "equipment"  # оборудование, ремонт, развитие
    URGENT = "urgent"  # срочно закрыть кассовый разрыв


class CheckSource(StrEnum):
    EGRUL = "egrul"
    FNS = "fns"
    BKI = "bki"


class DecisionType(StrEnum):
    APPROVE = "approve"
    COUNTER = "counter"
    INFO = "info"
    REJECT = "reject"


class DecisionMaker(StrEnum):
    AUTO = "auto"
    ANALYST = "analyst"


class DocStatus(StrEnum):
    REQUESTED = "requested"
    UPLOADED = "uploaded"


class JobType(StrEnum):
    PROCESS_APPLICATION = "process_application"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
