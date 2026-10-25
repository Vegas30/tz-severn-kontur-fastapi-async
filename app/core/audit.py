import json
from typing import Any, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.audit_log import AuditLog, EntityType


async def log_action(
    session: AsyncSession,
    user_id: int,
    action: str,
    entity_type: EntityType,
    entity_id: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> AuditLog:
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        meta=json.dumps(meta, ensure_ascii=False) if meta else None,
    )
    session.add(audit_log)
    await session.commit()
    await session.refresh(audit_log)
    return audit_log
