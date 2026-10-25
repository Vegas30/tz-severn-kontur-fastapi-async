from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_current_user, require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin, UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    return await UserService(session).create_user(user_data, current_user)


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, session: AsyncSession = Depends(get_session)):
    return await UserService(session).authenticate(credentials)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
