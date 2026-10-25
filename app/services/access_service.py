from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import aliased
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_action
from app.core.permissions import can_manage_project
from app.models.audit_log import EntityType
from app.models.project import Project
from app.models.project_access import ProjectAccess
from app.models.user import User
from app.schemas.project_access import ProjectAccessCreate, ProjectAccessReadWithUser


class AccessService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _check_project_exists(self, project_id: int) -> Project:
        project = await self.session.get(Project, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        return project

    async def _check_user_exists(self, user_id: int) -> User:
        user = await self.session.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found"
            )
        return user

    async def _check_manage_permission(self, user: User, project_id: int) -> None:
        if not await can_manage_project(self.session, user, project_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin or project owner can manage access",
            )

    async def get_access(self, project_id: int, user_id: int) -> Optional[ProjectAccess]:
        statement = select(ProjectAccess).where(
            ProjectAccess.project_id == project_id,
            ProjectAccess.user_id == user_id,
        )
        return (await self.session.exec(statement)).first()

    async def grant_access(
        self, project_id: int, access_data: ProjectAccessCreate, granted_by: User
    ) -> ProjectAccessReadWithUser:
        await self._check_project_exists(project_id)
        await self._check_manage_permission(granted_by, project_id)
        target_user = await self._check_user_exists(access_data.user_id)

        access = await self.get_access(project_id, access_data.user_id)

        if access:
            access.permission = access_data.permission
            access.granted_by = granted_by.id
            action = "update_access"
        else:
            access = ProjectAccess(
                project_id=project_id,
                user_id=access_data.user_id,
                permission=access_data.permission,
                granted_by=granted_by.id,
            )
            action = "grant_access"

        self.session.add(access)
        await self.session.commit()
        await self.session.refresh(access)

        await log_action(
            session=self.session,
            user_id=granted_by.id,
            action=action,
            entity_type=EntityType.access,
            entity_id=access.id,
            meta={
                "project_id": project_id,
                "target_user_id": access_data.user_id,
                "permission": access_data.permission.value,
            },
        )

        return ProjectAccessReadWithUser(
            id=access.id,
            project_id=access.project_id,
            user_id=access.user_id,
            permission=access.permission,
            granted_by=access.granted_by,
            created_at=access.created_at,
            user_email=target_user.email,
            granter_email=granted_by.email,
        )

    async def revoke_access(self, project_id: int, user_id: int, revoked_by: User) -> None:
        await self._check_project_exists(project_id)
        await self._check_manage_permission(revoked_by, project_id)

        access = await self.get_access(project_id, user_id)
        if not access:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Access not found"
            )

        access_id = access.id
        await self.session.delete(access)
        await self.session.commit()

        await log_action(
            session=self.session,
            user_id=revoked_by.id,
            action="revoke_access",
            entity_type=EntityType.access,
            entity_id=access_id,
            meta={"project_id": project_id, "target_user_id": user_id},
        )

    async def list_project_access(
        self, project_id: int, user: User
    ) -> list[ProjectAccessReadWithUser]:
        await self._check_project_exists(project_id)
        await self._check_manage_permission(user, project_id)

        target = aliased(User)
        granter = aliased(User)
        statement = (
            select(ProjectAccess, target.email, granter.email)
            .join(target, target.id == ProjectAccess.user_id, isouter=True)
            .join(granter, granter.id == ProjectAccess.granted_by, isouter=True)
            .where(ProjectAccess.project_id == project_id)
            .order_by(ProjectAccess.id)
        )
        rows = (await self.session.exec(statement)).all()

        return [
            ProjectAccessReadWithUser(
                **access.model_dump(),
                user_email=target_email,
                granter_email=granter_email,
            )
            for access, target_email, granter_email in rows
        ]
