"""Уведомления в кабинете (колокольчик). Никаких email/SMS — только здесь."""

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select, update

from app.deps import DB, CurrentUser
from app.errors import NotFound
from app.models import Notification
from app.schemas import NotificationsOut

router = APIRouter(tags=["Уведомления"])


@router.get("/notifications", response_model=NotificationsOut, summary="Мои уведомления (последние 30)")
def list_notifications(db: DB, user: CurrentUser) -> NotificationsOut:
    items = db.scalars(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(30)
    ).all()
    unread = db.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    return NotificationsOut(items=list(items), unread_count=unread)


@router.post("/notifications/{notification_id}/read", status_code=204, summary="Отметить прочитанным")
def mark_read(notification_id: int, db: DB, user: CurrentUser) -> None:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise NotFound("Уведомление не найдено")
    if n.read_at is None:
        n.read_at = datetime.now(UTC)
        db.commit()


@router.post("/notifications/read-all", status_code=204, summary="Отметить все прочитанными")
def mark_all_read(db: DB, user: CurrentUser) -> None:
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()
