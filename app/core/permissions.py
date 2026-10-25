from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.project import Project
from app.models.project_access import Permission, ProjectAccess
from app.models.user import User, UserRole


async def get_user_project_permission(
    session: AsyncSession, user: User, project_id: int
) -> Optional[Permission]:
    if user.role == UserRole.admin:
        return Permission.editor

    project = await session.get(Project, project_id)
    if project and project.owner_id == user.id:
        return Permission.editor

    statement = select(ProjectAccess).where(
        ProjectAccess.project_id == project_id,
        ProjectAccess.user_id == user.id,
    )
    access = (await session.exec(statement)).first()

    return access.permission if access else None


async def can_view_project(session: AsyncSession, user: User, project_id: int) -> bool:
    return await get_user_project_permission(session, user, project_id) is not None


async def is_project_owner_or_admin(
    session: AsyncSession, user: User, project_id: int
) -> bool:
    if user.role == UserRole.admin:
        return True

    project = await session.get(Project, project_id)
    return project is not None and project.owner_id == user.id


async def can_manage_project(session: AsyncSession, user: User, project_id: int) -> bool:
    return await is_project_owner_or_admin(session, user, project_id)


async def can_edit_project(session: AsyncSession, user: User, project_id: int) -> bool:
    return await get_user_project_permission(session, user, project_id) == Permission.editor
