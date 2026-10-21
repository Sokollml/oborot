"""Схемы запросов и ответов API (Pydantic v2).

Описания и примеры полей попадают в OpenAPI (Swagger) и в сгенерированные типы фронтенда.
Деньги — целые рубли, ставки — проценты годовых.
"""

from datetime import date, datetime

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


class ApplicationCreate(BaseModel):
    product_code: str = Field(description="Код продукта", examples=["EXPRESS"])
    inn: str = Field(description="ИНН компании (10 цифр) или ИП (12 цифр)", examples=["0010000017"])
    purpose: Purpose = Field(examples=["urgent"])
    amount: int | None = Field(default=None, gt=0, examples=[2_000_000])
    term_months: int | None = Field(default=None, gt=0, examples=[12])


class ApplicationPatch(BaseModel):
    """Частичное обновление черновика: передавайте только изменённые поля."""

    product_code: str | None = Field(default=None, examples=["EXPRESS"])
    purpose: Purpose | None = None
    amount: int | None = Field(default=None, gt=0, description="Сумма кредита, ₽", examples=[2_000_000])
    term_months: int | None = Field(default=None, gt=0, description="Срок, мес.", examples=[12])
    revenue_12m: int | None = Field(default=None, ge=0, description="Выручка за последние 12 месяцев, ₽", examples=[30_000_000])
    revenue_prev_year: int | None = Field(default=None, ge=0, description="Выручка за предыдущие 12 месяцев, ₽", examples=[26_000_000])
    monthly_debt_payments: int | None = Field(
        default=None, ge=0, description="Сколько компания сейчас платит по другим кредитам в месяц, ₽", examples=[50_000]
    )
    employees: int | None = Field(default=None, ge=0, description="Число сотрудников", examples=[12])
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
    reasons: list[str] = Field(description="Понятные причины и советы")
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
