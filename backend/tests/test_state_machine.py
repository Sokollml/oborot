"""State machine: разрешённые и запрещённые переходы, роли, история, уведомления."""

import pytest
from sqlalchemy import select

from app.enums import ActorType, AppStatus
from app.errors import Conflict, Forbidden, ValidationFailed
from app.models import Application, Notification, StatusHistory
from app.services.state_machine import ALLOWED_TRANSITIONS, Actor, transition
from tests.helpers import create_draft

S = AppStatus


def _app_in(db, client1, status: AppStatus) -> Application:
    app_id = create_draft(client1)
    app = db.get(Application, app_id)
    app.status = status  # только для подготовки теста: ставим нужный исходный статус
    db.commit()
    return app


ANALYST = Actor(ActorType.ANALYST, 3)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (S.DRAFT, S.OFFER),  # нельзя перепрыгнуть проверку
        (S.DRAFT, S.ISSUED),
        (S.SUBMITTED, S.OFFER),
        (S.ISSUED, S.CANCELLED),  # выданный кредит не отменить
        (S.CANCELLED, S.DRAFT),
        (S.SIGNING, S.CANCELLED),
        (S.INFO_REQUESTED, S.OFFER),
    ],
)
def test_forbidden_transition_raises_conflict(db, client1, from_status, to_status):
    app = _app_in(db, client1, from_status)
    with pytest.raises(Conflict):
        transition(db, app, to_status, Actor.system())


def test_wrong_actor_is_forbidden(db, client1):
    app = _app_in(db, client1, S.MANUAL_REVIEW)
    # Решение по ручной заявке может принять только аналитик, не система и не клиент.
    with pytest.raises(Forbidden):
        transition(db, app, S.OFFER, Actor.system())
    with pytest.raises(Forbidden):
        transition(db, app, S.OFFER, Actor(ActorType.CLIENT, 1))


def test_analyst_must_comment(db, client1):
    app = _app_in(db, client1, S.MANUAL_REVIEW)
    with pytest.raises(ValidationFailed):
        transition(db, app, S.REJECTED, ANALYST, comment="  ")
    transition(db, app, S.REJECTED, ANALYST, comment="Выручка не подтверждена выпиской")
    assert app.status == S.REJECTED


def test_transition_writes_history_and_notification(db, client1):
    app = _app_in(db, client1, S.SCORING)
    transition(db, app, S.OFFER, Actor.system(), comment="Автоодобрение")
    db.commit()

    last = db.scalars(select(StatusHistory).where(StatusHistory.application_id == app.id).order_by(StatusHistory.id.desc())).first()
    assert (last.from_status, last.to_status, last.actor_type) == (S.SCORING, S.OFFER, ActorType.SYSTEM)

    note = db.scalar(select(Notification).where(Notification.application_id == app.id))
    assert note is not None and "предложение" in note.text
    assert note.user_id == 1  # владелец — client1


def test_every_status_has_a_way_in():
    """Защита от опечаток в таблице: в каждый статус, кроме DRAFT, можно попасть."""
    targets = {to for (_, to) in ALLOWED_TRANSITIONS}
    assert targets == set(AppStatus) - {S.DRAFT}
