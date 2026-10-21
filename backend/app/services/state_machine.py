"""Конечный автомат статусов заявки (state machine).

ГЛАВНОЕ ПРАВИЛО ПРОЕКТА: статус заявки меняется только функцией transition() из этого файла.
Она делает четыре вещи за один раз:
  1. проверяет, что переход из текущего статуса в новый вообще разрешён (иначе HTTP 409);
  2. проверяет, что его выполняет тот, кому можно: клиент, аналитик или система (иначе HTTP 403);
  3. записывает переход в status_history — из неё строится лента этапов и аудит;
  4. создаёт клиенту уведомление в кабинете, если статус для него важен.

transition() НЕ делает commit: вызывающий код сохраняет изменения вместе со своими
(например, отправка заявки и задача для воркера попадают в базу одной транзакцией).
Перед вызовом заявку нужно заблокировать (SELECT ... FOR UPDATE), чтобы клиент, аналитик
и воркер не поменяли статус одновременно.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import ActorType, AppStatus, Role
from app.errors import Conflict, Forbidden, ValidationFailed
from app.models import Application, Company, Notification, StatusHistory, User

S = AppStatus
A = ActorType

# Таблица разрешённых переходов: (из какого статуса, в какой) → кто может его выполнить.
# Всё, чего здесь нет, запрещено.
ALLOWED_TRANSITIONS: dict[tuple[AppStatus, AppStatus], set[ActorType]] = {
    # Клиент работает с черновиком
    (S.DRAFT, S.SUBMITTED): {A.CLIENT},
    (S.DRAFT, S.CANCELLED): {A.CLIENT},
    # Конвейер (воркер)
    (S.SUBMITTED, S.CHECKING): {A.SYSTEM},
    (S.CHECKING, S.SCORING): {A.SYSTEM},
    (S.CHECKING, S.MANUAL_REVIEW): {A.SYSTEM},  # внешний сервис не ответил после всех попыток
    (S.SCORING, S.OFFER): {A.SYSTEM},
    (S.SCORING, S.MANUAL_REVIEW): {A.SYSTEM},
    (S.SCORING, S.INFO_REQUESTED): {A.SYSTEM},  # WORKING + класс C: нужна выписка
    (S.SCORING, S.REJECTED): {A.SYSTEM},
    # Ручное рассмотрение
    (S.MANUAL_REVIEW, S.OFFER): {A.ANALYST},
    (S.MANUAL_REVIEW, S.INFO_REQUESTED): {A.ANALYST},
    (S.MANUAL_REVIEW, S.REJECTED): {A.ANALYST},
    # Клиент загрузил документы — заявка снова идёт на проверку
    (S.INFO_REQUESTED, S.CHECKING): {A.CLIENT},
    # Предложение
    (S.OFFER, S.SIGNING): {A.CLIENT},
    (S.OFFER, S.CANCELLED): {A.CLIENT},
    (S.OFFER, S.OFFER): {A.ANALYST},  # аналитик меняет условия, пока клиент не принял
    (S.OFFER, S.REJECTED): {A.ANALYST},
    (S.REJECTED, S.OFFER): {A.ANALYST},  # аналитик отменяет автоматический отказ
    # Подписание (симуляция: код показывается на экране)
    (S.SIGNING, S.ISSUED): {A.CLIENT},
}

# Уведомления клиенту в кабинете. Для промежуточных статусов не шлём, чтобы не шуметь.
NOTIFICATION_TEXTS: dict[AppStatus, str] = {
    S.SUBMITTED: "Заявка №{id} отправлена. Мы начали её проверять — это займёт пару минут.",
    S.MANUAL_REVIEW: "Заявку №{id} смотрит специалист. Обычно это занимает до одного рабочего дня.",
    S.INFO_REQUESTED: "По заявке №{id} нужны документы. Загрузите их на странице заявки.",
    S.OFFER: "По заявке №{id} готово предложение. Посмотрите условия и примите решение.",
    S.REJECTED: "По заявке №{id} пока отказ. На странице заявки — причины и что можно сделать.",
    S.ISSUED: "Деньги по заявке №{id} зачислены на счёт компании.",
}

ACTOR_NAMES = {A.CLIENT: "клиент", A.ANALYST: "специалист банка", A.SYSTEM: "система"}


@dataclass(frozen=True)
class Actor:
    """Кто выполняет переход."""

    type: ActorType
    user_id: int | None = None

    @classmethod
    def system(cls) -> "Actor":
        return cls(A.SYSTEM)

    @classmethod
    def of(cls, user: User) -> "Actor":
        return cls(ActorType(user.role), user.id)


def can_transition(from_status: str, to_status: str, actor_type: ActorType) -> bool:
    return actor_type in ALLOWED_TRANSITIONS.get((AppStatus(from_status), AppStatus(to_status)), set())


def transition(
    db: Session,
    application: Application,
    to_status: AppStatus,
    actor: Actor,
    comment: str | None = None,
) -> StatusHistory:
    from_status = AppStatus(application.status)
    allowed_actors = ALLOWED_TRANSITIONS.get((from_status, to_status))

    # 1. Такой переход вообще существует?
    if allowed_actors is None:
        raise Conflict(f"Сейчас это действие недоступно: заявка в статусе «{STATUS_LABELS[from_status]}»")

    # 2. Тот ли, кто его делает?
    if actor.type not in allowed_actors:
        who = " или ".join(ACTOR_NAMES[a] for a in allowed_actors)
        raise Forbidden(f"Это действие может выполнить только {who}")

    # Решения аналитика всегда с объяснением — его увидят клиент и коллеги.
    if actor.type == A.ANALYST and not (comment and comment.strip()):
        raise ValidationFailed("Добавьте комментарий к решению")

    # 3. Меняем статус и пишем историю.
    application.status = to_status
    entry = StatusHistory(
        application_id=application.id,
        from_status=from_status,
        to_status=to_status,
        actor_type=actor.type,
        actor_id=actor.user_id,
        comment=comment,
    )
    db.add(entry)

    # 4. Уведомление владельцу заявки (и специалистам, если решение теперь за ними).
    text = NOTIFICATION_TEXTS.get(to_status)
    if text:
        owner_id = db.scalar(select(Company.owner_user_id).where(Company.id == application.company_id))
        db.add(Notification(user_id=owner_id, application_id=application.id, text=text.format(id=application.id)))
    if to_status == S.MANUAL_REVIEW:
        company = db.scalar(select(Company.name).where(Company.id == application.company_id))
        for analyst_id in db.scalars(select(User.id).where(User.role == Role.ANALYST)):
            db.add(Notification(user_id=analyst_id, application_id=application.id, text=f"Заявка №{application.id} ({company}) ждёт вашего решения"))

    db.flush()
    return entry


# Названия статусов для людей (используются в текстах ошибок и на фронте).
STATUS_LABELS: dict[AppStatus, str] = {
    S.DRAFT: "Черновик",
    S.SUBMITTED: "Отправлена",
    S.CHECKING: "Проверяем данные",
    S.SCORING: "Оцениваем заявку",
    S.OFFER: "Есть предложение",
    S.MANUAL_REVIEW: "Смотрит специалист",
    S.INFO_REQUESTED: "Нужны документы",
    S.REJECTED: "Отказ",
    S.SIGNING: "Подписание",
    S.ISSUED: "Деньги зачислены",
    S.CANCELLED: "Отменена",
}
