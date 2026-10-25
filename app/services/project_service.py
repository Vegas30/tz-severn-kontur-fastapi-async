from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_action
from app.core.permissions import can_manage_project, can_view_project
from app.models.audit_log import EntityType
from app.models.project import Project
from app.models.project_access import ProjectAccess
from app.models.user import User, UserRole
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, project_id: int) -> Optional[Project]:
        return await self.session.get(Project, project_id)

    async def _get_or_404(self, project_id: int) -> Project:
        project = await self.get_by_id(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        return project

    async def create_project(self, project_data: ProjectCreate, owner: User) -> Project:
        project = Project(
            title=project_data.title,
            description=project_data.description,
            owner_id=owner.id,
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)

        await log_action(
            session=self.session,
            user_id=owner.id,
            action="create_project",
            entity_type=EntityType.project,
            entity_id=project.id,
            meta={"title": project.title},
        )
        return project

    async def list_projects(self, user: User, skip: int = 0, limit: int = 20) -> list[Project]:
        if user.role == UserRole.admin:
            statement = select(Project).order_by(Project.id).offset(skip).limit(limit)
            return list((await self.session.exec(statement)).all())

        # Один запрос вместо трёх: проекты, которыми владеет пользователь,
        # либо те, на которые ему выдан доступ.
        accessible_ids = select(ProjectAccess.project_id).where(
            ProjectAccess.user_id == user.id
        )
        statement = (
            select(Project)
            .where(or_(Project.owner_id == user.id, Project.id.in_(accessible_ids)))
            .order_by(Project.id)
            .offset(skip)
            .limit(limit)
        )
        return list((await self.session.exec(statement)).all())

    async def get_project(self, project_id: int, user: User) -> Project:
        project = await self._get_or_404(project_id)

        if not await can_view_project(self.session, user, project_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this project",
            )
        return project

    async def update_project(
        self, project_id: int, project_data: ProjectUpdate, user: User
    ) -> Project:
        project = await self._get_or_404(project_id)

        if not await can_manage_project(self.session, user, project_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin or project owner can update",
            )

        update_data = project_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(project, key, value)

        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)

        await log_action(
            session=self.session,
            user_id=user.id,
            action="update_project",
            entity_type=EntityType.project,
            entity_id=project.id,
            meta={"updated_fields": list(update_data.keys())},
        )
        return project

    async def delete_project(self, project_id: int, user: User) -> None:
        project = await self._get_or_404(project_id)

        if not await can_manage_project(self.session, user, project_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin or project owner can delete",
            )

        project_title = project.title
        await self.session.delete(project)
        await self.session.commit()

        await log_action(
            session=self.session,
            user_id=user.id,
            action="delete_project",
            entity_type=EntityType.project,
            entity_id=project_id,
            meta={"title": project_title},
        )
