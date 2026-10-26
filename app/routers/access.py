from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.project_access import ProjectAccessCreate, ProjectAccessReadWithUser
from app.services.access_service import AccessService

router = APIRouter(tags=["Access"])


@router.post(
    "/projects/{project_id}/access/grant",
    response_model=ProjectAccessReadWithUser,
    status_code=status.HTTP_201_CREATED,
)
async def grant_access(
    project_id: int,
    access_data: ProjectAccessCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await AccessService(session).grant_access(project_id, access_data, current_user)


@router.delete(
    "/projects/{project_id}/access/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_access(
    project_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await AccessService(session).revoke_access(project_id, user_id, current_user)


@router.get(
    "/projects/{project_id}/access", response_model=list[ProjectAccessReadWithUser]
)
async def list_project_access(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await AccessService(session).list_project_access(project_id, current_user)
