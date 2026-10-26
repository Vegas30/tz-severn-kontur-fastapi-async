from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import require_admin
from app.db.session import get_session
from app.models.audit_log import AuditLog, EntityType
from app.models.user import User
from app.schemas.audit_log import AuditLogReadWithUser

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=list[AuditLogReadWithUser])
async def list_audit_logs(
    date_from: Optional[date] = Query(default=None, description="Filter from date"),
    date_to: Optional[date] = Query(default=None, description="Filter to date"),
    user_id: Optional[int] = Query(default=None, description="Filter by user ID"),
    action: Optional[str] = Query(default=None, description="Filter by action"),
    entity_type: Optional[EntityType] = Query(default=None, description="Filter by entity type"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    # Один запрос с JOIN вместо N+1 запросов session.get(User, ...)
    statement = select(AuditLog, User.email).join(
        User, User.id == AuditLog.user_id, isouter=True
    )

    if date_from:
        statement = statement.where(
            AuditLog.created_at >= datetime.combine(date_from, datetime.min.time())
        )
    if date_to:
        statement = statement.where(
            AuditLog.created_at <= datetime.combine(date_to, datetime.max.time())
        )
    if user_id:
        statement = statement.where(AuditLog.user_id == user_id)
    if action:
        statement = statement.where(AuditLog.action == action)
    if entity_type:
        statement = statement.where(AuditLog.entity_type == entity_type)

    statement = statement.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)

    rows = (await session.exec(statement)).all()
    return [AuditLogReadWithUser(**log.model_dump(), user_email=email) for log, email in rows]
