from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import AttemptRecord, AttemptStatus, utcnow


def claim_next_attempt(
    session: Session,
    *,
    owner: str,
    lease_seconds: int,
) -> AttemptRecord | None:
    now = utcnow()
    statement = (
        select(AttemptRecord)
        .where(
            AttemptRecord.status == AttemptStatus.PREPARING,
            or_(
                AttemptRecord.lease_owner.is_(None),
                AttemptRecord.lease_expires_at.is_(None),
                AttemptRecord.lease_expires_at <= now,
            ),
        )
        .order_by(AttemptRecord.created_at, AttemptRecord.number)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    attempt = session.scalar(statement)
    if attempt is None:
        session.rollback()
        return None

    attempt.lease_owner = owner
    attempt.heartbeat_at = now
    attempt.lease_expires_at = now + timedelta(seconds=lease_seconds)
    session.commit()
    session.refresh(attempt)
    return attempt


def renew_attempt_lease(
    session: Session,
    attempt_id: UUID,
    *,
    owner: str,
    lease_seconds: int,
) -> bool:
    attempt = session.get(AttemptRecord, attempt_id)
    if attempt is None or attempt.lease_owner != owner:
        return False
    if attempt.status not in {AttemptStatus.PREPARING, AttemptStatus.RUNNING}:
        return False

    now = utcnow()
    attempt.heartbeat_at = now
    attempt.lease_expires_at = now + timedelta(seconds=lease_seconds)
    session.commit()
    return True


def release_attempt_lease(session: Session, attempt_id: UUID, *, owner: str) -> None:
    attempt = session.get(AttemptRecord, attempt_id)
    if attempt is None or attempt.lease_owner != owner:
        return
    attempt.lease_owner = None
    attempt.lease_expires_at = None
    session.commit()


def list_stale_running_attempts(session: Session) -> list[AttemptRecord]:
    now = utcnow()
    statement = select(AttemptRecord).where(
        AttemptRecord.status == AttemptStatus.RUNNING,
        AttemptRecord.lease_expires_at.is_not(None),
        AttemptRecord.lease_expires_at <= now,
    )
    return list(session.scalars(statement).all())
