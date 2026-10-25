"""Схемы запросов и ответов API (Pydantic v2).

Описания и примеры полей попадают в OpenAPI (Swagger) и в сгенерированные типы фронтенда.
Деньги — целые рубли, ставки — проценты годовых.
"""

from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ActorType, AppStatus, Purpose, Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Авторизация ----------


class LoginIn(BaseModel):
    email: str = Field(description="Email пользователя", examples=["client1@demo.local"])
    password: str = Field(description="Пароль", examples=["demo12345"])


class UserOut(ORM):
    id: int
    email: str = Field(examples=["client1@demo.local"])
    role: Role = Field(description="client — клиент, analyst — специалист банка")
    full_name: str = Field(examples=["Анна Иванова"])


class DemoAccount(BaseModel):
    email: str
    role: Role
    description: str


class MetaOut(BaseModel):
    demo_mode: bool = Field(description="Показывать ли подсказку с тестовыми аккаунтами")
    demo_accounts: list[DemoAccount] = Field(default_factory=list)
    demo_password: str | None = None


# ---------- Продукты ----------


class ProductOut(ORM):
    code: str = Field(examples=["EXPRESS"])
    name: str = Field(examples=["Экспресс-кредит"])
    description: str
    min_amount: int = Field(examples=[100_000])
    max_amount: int = Field(examples=[3_000_000])
    min_term: int = Field(description="Минимальный срок, мес.", examples=[3])
    max_term: int = Field(description="Максимальный срок, мес.", examples=[24])
    needs_collateral: bool = Field(description="Нужен ли залог")
    base_rate: float = Field(description="Базовая ставка, % годовых", examples=[24.0])


class RecommendIn(BaseModel):
    purpose: Purpose = Field(
        description="На что нужны деньги: stock_salary — товар и зарплаты, equipment — оборудование и развитие, "
        "urgent — срочно закрыть кассовый разрыв",
        examples=["urgent"],
    )
    amount: int = Field(gt=0, description="Желаемая сумма, ₽", examples=[2_000_000])
    term_months: int = Field(gt=0, le=120, description="Желаемый срок, мес.", examples=[12])


class ProductOption(BaseModel):
    product: ProductOut
    fits: bool = Field(description="Укладываются ли сумма и срок в условия продукта")
    reason: str = Field(description="Почему этот продукт — простыми словами")
    amount: int = Field(description="Сумма для расчёта (подогнана под лимиты, если fits=false)")
    term_months: int
    rate_from: float = Field(description="Ставка «от», % годовых")
    monthly_payment_from: int = Field(description="Примерный ежемесячный платёж, ₽")


class RecommendOut(BaseModel):
    recommended: ProductOption
    alternatives: list[ProductOption]


# ---------- Компании ----------


class CompanyLookupOut(BaseModel):
    inn: str = Field(examples=["0010000017"])
    ogrn: str
    name: str = Field(examples=["ООО «Ромашка-Тест»"])
    okved: str = Field(description="Основной вид деятельности (код ОКВЭД и название)")
    registered_at: date
    status: str = Field(description="active — действует, liquidating — ликвидируется, bankrupt — банкротство")
    director: str


class CompanyOut(ORM):
    id: int
    inn: str
    name: str
    okved: str
    registered_at: date
    status: str
    director: str


# ---------- Заявки ----------

# Верхние границы чисел в анкете: заведомо больше любых реальных значений, но меньше,
# чем помещается в колонку базы, — иначе опечатка с лишними нулями даёт 500 вместо понятной ошибки.
MAX_MONEY = 10**15  # ₽
MAX_TERM = 600  # мес.


class ApplicationCreate(BaseModel):
    product_code: str = Field(description="Код продукта", examples=["EXPRESS"])
    inn: str = Field(description="ИНН компании (10 цифр) или ИП (12 цифр)", examples=["0010000017"])
    purpose: Purpose = Field(examples=["urgent"])
    amount: int | None = Field(default=None, gt=0, le=MAX_MONEY, examples=[2_000_000])
    term_months: int | None = Field(default=None, gt=0, le=MAX_TERM, examples=[12])


class ApplicationPatch(BaseModel):
    """Частичное обновление черновика: передавайте только изменённые поля."""

    product_code: str | None = Field(default=None, examples=["EXPRESS"])
    purpose: Purpose | None = None
    amount: int | None = Field(default=None, gt=0, le=MAX_MONEY, description="Сумма кредита, ₽", examples=[2_000_000])
    term_months: int | None = Field(default=None, gt=0, le=MAX_TERM, description="Срок, мес.", examples=[12])
    revenue_12m: int | None = Field(
        default=None, ge=0, le=MAX_MONEY, description="Выручка за последние 12 месяцев, ₽", examples=[30_000_000]
    )
    revenue_prev_year: int | None = Field(
        default=None, ge=0, le=MAX_MONEY, description="Выручка за предыдущие 12 месяцев, ₽", examples=[26_000_000]
    )
    monthly_debt_payments: int | None = Field(
        default=None, ge=0, le=MAX_MONEY, description="Сколько компания сейчас платит по другим кредитам в месяц, ₽", examples=[50_000]
    )
    employees: int | None = Field(default=None, ge=0, le=1_000_000, description="Число сотрудников", examples=[12])
    collateral_description: str | None = Field(default=None, description="Что можно оставить в залог (для INVEST)")
    bki_consent: bool | None = Field(default=None, description="Согласие на запрос кредитной истории")


class NextActionOut(BaseModel):
    code: str = Field(
        description="Какой блок показать клиенту: fill_draft, wait, upload_documents, review_offer, sign, done, rejected, cancelled",
        examples=["wait"],
    )
    title: str = Field(description="Что происходит", examples=["Проверяем данные компании"])
    description: str
    wait_text: str | None = Field(description="Сколько ждать", examples=["1–2 минуты"])
    action_required: bool = Field(description="Нужно ли действие клиента")


class DecisionOut(ORM):
    type: str = Field(description="approve — одобрено, counter — контрпредложение, info — нужны документы, reject — отказ")
    amount: int | None = None
    term: int | None = None
    rate: float | None = Field(default=None, description="Ставка, % годовых")
    monthly_payment: int | None = None
    reasons: list[str] = Field(description="2–3 понятные причины решения")
    advice: list[str] = Field(description="Совет, что можно сделать (например, «снизьте сумму до …»)")
    made_by: str = Field(description="auto — система, analyst — специалист")
    created_at: datetime


class DocumentRequestOut(ORM):
    id: int
    doc_type: str = Field(examples=["bank_statement"])
    title: str = Field(description="Название документа для клиента")
    status: str = Field(description="requested — ждём загрузки, uploaded — загружен")
    file_name: str | None = None


class ApplicationOut(ORM):
    """Состояние заявки. Фронт опрашивает этот ответ раз в 3 секунды."""

    id: int
    status: AppStatus
    status_label: str = Field(examples=["Проверяем данные"])
    next_action: NextActionOut
    product: ProductOut
    company: CompanyOut
    purpose: Purpose
    amount: int | None
    term_months: int | None
    revenue_12m: int | None
    revenue_prev_year: int | None
    monthly_debt_payments: int | None
    employees: int | None
    collateral_description: str | None
    bki_consent: bool
    revenue_prefilled: bool = Field(description="Выручка подставлена из оборотов по счёту в банке")
    decision: DecisionOut | None = Field(description="Последнее решение по заявке, если есть")
    documents: list[DocumentRequestOut]
    signing_code: str | None = Field(description="Код подписания (симуляция) — только в статусе SIGNING")
    created_at: datetime
    updated_at: datetime


class ApplicationListItem(BaseModel):
    id: int
    status: AppStatus
    status_label: str
    action_required: bool = Field(description="Нужно действие клиента — показываем плашку")
    product_name: str
    company_name: str
    amount: int | None
    term_months: int | None
    created_at: datetime
    updated_at: datetime


class HistoryItem(ORM):
    from_status: AppStatus | None
    to_status: AppStatus
    to_label: str
    actor_type: ActorType
    comment: str | None
    created_at: datetime


class SignIn(BaseModel):
    code: str = Field(description="Код подтверждения с экрана", examples=["482915"])


# ---------- Уведомления ----------


class NotificationOut(ORM):
    id: int
    application_id: int | None
    text: str = Field(examples=["По заявке №12 готово предложение. Посмотрите условия и примите решение."])
    read_at: datetime | None
    created_at: datetime


class NotificationsOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int = Field(description="Сколько непрочитанных — число на колокольчике")


# ---------- Кабинет специалиста ----------


class QueueItem(BaseModel):
    id: int
    company_name: str
    company_inn: str
    product_code: str
    product_name: str
    amount: int | None
    term_months: int | None
    status: AppStatus
    status_label: str
    risk_class: str | None = Field(description="Класс риска A–D (нет, если скоринг не проводился)")
    total_score: int | None
    waiting_since: datetime = Field(description="Когда заявка попала в текущий статус")


class CheckLine(BaseModel):
    label: str = Field(examples=["Налоговый долг"])
    value: str = Field(examples=["нет"])
    level: str = Field(description="ok — хорошо, warn — обратить внимание, bad — плохо", examples=["ok"])


class CheckOut(BaseModel):
    source: str = Field(examples=["bki"])
    title: str = Field(examples=["Кредитная история (БКИ)"])
    ok: bool = Field(description="Сервис ответил")
    level: str = Field(description="Итог проверки: ok / warn / bad")
    lines: list[CheckLine]
    fetched_at: datetime


class FactorOut(BaseModel):
    code: str
    title: str
    value: str
    points: int
    comment: str


class ScoringOut(BaseModel):
    total_score: int
    risk_class: str
    base_score: int = Field(description="Стартовый балл, от которого считаются факторы")
    factors: list[FactorOut]
    stop_factors: list[FactorOut]
    model_version: str
    created_at: datetime


class RecommendationOut(BaseModel):
    action: str = Field(description="approve | counter | request_docs | reject")
    title: str = Field(examples=["Одобрить на запрошенных условиях"])
    text: str
    amount: int | None = None
    term_months: int | None = None
    rate: float | None = None
    monthly_payment: int | None = None


class AnalystApplicationOut(BaseModel):
    application: ApplicationOut
    checks: list[CheckOut]
    scoring: ScoringOut | None
    recommendation: RecommendationOut
    history: list[HistoryItem]
    decisions: list[DecisionOut] = Field(description="Все решения по заявке, новые сверху")
    available_actions: list[str] = Field(description="Что специалист может сделать сейчас: approve, request_docs, reject")


class AnalystDecisionIn(BaseModel):
    action: Literal["approve", "request_docs", "reject"] = Field(
        description="approve — одобрить (в т.ч. с изменёнными условиями), request_docs — запросить документы, reject — отказать"
    )
    amount: int | None = Field(default=None, gt=0, description="Для approve: сумма", examples=[2_000_000])
    term_months: int | None = Field(default=None, gt=0, description="Для approve: срок, мес.", examples=[12])
    rate: float | None = Field(default=None, gt=0, le=100, description="Для approve: ставка, % годовых", examples=[24.0])
    doc_types: list[str] = Field(default_factory=list, description="Для request_docs: какие документы нужны", examples=[["bank_statement"]])
    client_reason: str | None = Field(default=None, description="Для reject: причина, которую увидит клиент")
    comment: str = Field(min_length=1, description="Комментарий специалиста — обязателен", examples=["Выручка подтверждена выпиской"])


# ---------- Мои компании и предодобренный лимит ----------


class PotentialOffer(BaseModel):
    product_code: str = Field(examples=["EXPRESS"])
    product_name: str
    amount: int = Field(description="Максимальная сумма с автоматическим одобрением, ₽", examples=[3_000_000])
    term_months: int
    rate: float
    monthly_payment: int


class PotentialOut(BaseModel):
    status: str = Field(description="ok — есть предложение, none — нет, no_account — нет счёта в банке, unavailable — сервис не ответил")
    title: str = Field(examples=["Вам предварительно одобрено до 13 750 000 ₽"])
    text: str
    max_amount: int | None = None
    offers: list[PotentialOffer] = Field(default_factory=list)
    revenue_12m: int | None = Field(default=None, description="Поступления на счёт за 12 месяцев")
    revenue_prev_12m: int | None = None
    drivers: list[str] = Field(default_factory=list, description="Что помогло")
    tips: list[str] = Field(default_factory=list, description="Как увеличить лимит")
    calculated_at: datetime | None = None


class MyCompanyOut(BaseModel):
    id: int
    inn: str
    name: str
    status: str
    potential: PotentialOut | None = Field(description="Последний расчёт лимита; null — ещё не считали")


class PotentialRequest(BaseModel):
    consent: bool = Field(description="Согласие на запрос кредитной истории — без него лимит не считаем", examples=[True])


# ---------- Переписка ----------


class MessageOut(ORM):
    id: int
    author_role: str = Field(description="client — клиент, analyst — специалист")
    author_name: str
    text: str
    created_at: datetime


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000, examples=["Выписку загрузил, нужен ли ещё отчёт?"])


# ---------- Аналитика конвейера ----------


class StatItem(BaseModel):
    key: str
    label: str
    count: int


class StatsOut(BaseModel):
    submitted: int = Field(description="Отправлено заявок")
    decided: int = Field(description="Принято окончательных решений (одобрение / контрпредложение / отказ)")
    auto_share: int | None = Field(description="Доля решений без участия специалиста, %")
    auto_count: int
    manual_count: int
    median_first_response_sec: int | None = Field(description="Медиана: от отправки до первого ответа клиенту, сек")
    median_auto_decision_sec: int | None = Field(description="Медиана: от отправки до автоматического решения, сек")
    median_manual_decision_sec: int | None = Field(description="Медиана: от отправки до решения специалиста, сек")
    issued_count: int
    issued_volume: int = Field(description="Выдано всего, ₽")
    average_issued: int | None
    funnel: list[StatItem]
    status_groups: list[StatItem]
    risk_classes: list[StatItem]
    products: list[StatItem]
