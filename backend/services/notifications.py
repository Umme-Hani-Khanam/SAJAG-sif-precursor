from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from models import Notification, NotificationRead
from services.roles import Actor, scoped_sites


def create_notification(
    db: Session, *, notification_type: str, title: str, message: str,
    entity_type: str | None, entity_id: str | None, dedupe_key: str,
    recipient_user_id: str | None = None, recipient_role: str | None = None,
    recipient_site: str | None = None,
) -> Notification:
    existing = db.query(Notification).filter(Notification.dedupe_key == dedupe_key).first()
    if existing:
        return existing
    item = Notification(
        notification_id=f"NTF-{uuid4().hex[:16].upper()}", recipient_user_id=recipient_user_id,
        recipient_role=recipient_role, recipient_site=recipient_site,
        notification_type=notification_type.upper(), title=title, message=message,
        entity_type=entity_type, entity_id=entity_id, dedupe_key=dedupe_key,
    )
    db.add(item)
    db.flush()
    return item


def notification_query(db: Session, actor: Actor):
    if actor.role == "ADMIN":
        return db.query(Notification)
    sites = scoped_sites(actor)
    site_clause = sa_true() if sites is None else or_(Notification.recipient_site.is_(None), Notification.recipient_site.in_(sites))
    targets = [and_(Notification.recipient_role == actor.role, site_clause)]
    if actor.user_id:
        targets.append(Notification.recipient_user_id == actor.user_id)
    if sites:
        targets.append(and_(Notification.recipient_user_id.is_(None), Notification.recipient_role.is_(None), Notification.recipient_site.in_(sites)))
    return db.query(Notification).filter(or_(*targets))


def sa_true():
    from sqlalchemy import true
    return true()


def reader_key(actor: Actor) -> str:
    if actor.user_id:
        return f"user:{actor.user_id}"
    sites = ",".join(sorted(site.casefold() for site in actor.site_scope))
    return f"demo:{actor.role}:{actor.name.strip().casefold()}:{sites}"


def unread_notification_query(db: Session, actor: Actor):
    read_ids = select(NotificationRead.notification_id).where(NotificationRead.reader_key == reader_key(actor))
    return notification_query(db, actor).filter(Notification.notification_id.not_in(read_ids))


def notification_read_at(db: Session, actor: Actor, notification_id: str):
    receipt = db.query(NotificationRead).filter_by(
        notification_id=notification_id, reader_key=reader_key(actor),
    ).first()
    return receipt.read_at if receipt else None


def notification_to_dict(item: Notification, db: Session | None = None, actor: Actor | None = None) -> dict:
    result = {column.name: getattr(item, column.name) for column in item.__table__.columns}
    if db is not None and actor is not None:
        result["read_at"] = notification_read_at(db, actor, item.notification_id)
    return result


def mark_read(db: Session, actor: Actor, notification_id: str) -> Notification | None:
    item = notification_query(db, actor).filter(Notification.notification_id == notification_id).first()
    if item:
        key = reader_key(actor)
        if not db.query(NotificationRead).filter_by(notification_id=notification_id, reader_key=key).first():
            db.add(NotificationRead(
                receipt_id=f"NTR-{uuid4().hex[:16].upper()}", notification_id=notification_id,
                reader_key=key, read_at=datetime.now(timezone.utc),
            ))
        db.flush()
    return item


def mark_all_read(db: Session, actor: Actor) -> int:
    rows = unread_notification_query(db, actor).all()
    now = datetime.now(timezone.utc)
    key = reader_key(actor)
    for item in rows:
        db.add(NotificationRead(
            receipt_id=f"NTR-{uuid4().hex[:16].upper()}", notification_id=item.notification_id,
            reader_key=key, read_at=now,
        ))
    db.flush()
    return len(rows)
