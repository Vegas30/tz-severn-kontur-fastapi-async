from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.user import UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)


@router.get("/", response_model=list[UserRead])
async def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=500),
    _: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
):
    return await service.list_users(skip=skip, limit=limit)
