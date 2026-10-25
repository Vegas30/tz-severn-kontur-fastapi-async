from datetime import timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_action
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.audit_log import EntityType
from app.models.user import User, UserRole
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> Optional[User]:
        statement = select(User).where(User.email == email)
        return (await self.session.exec(statement)).first()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def create_user(self, user_data: UserCreate, created_by: User) -> User:
        if await self.get_by_email(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        new_user = User(
            email=user_data.email,
            password_hash=await get_password_hash(user_data.password),
            role=user_data.role,
        )
        self.session.add(new_user)
        await self.session.commit()
        await self.session.refresh(new_user)

        await log_action(
            session=self.session,
            user_id=created_by.id,
            action="register_user",
            entity_type=EntityType.user,
            entity_id=new_user.id,
            meta={"created_email": new_user.email, "role": new_user.role.value},
        )
        return new_user

    async def authenticate(self, credentials: UserLogin) -> Token:
        user = await self.get_by_email(credentials.email)

        if not user or not await verify_password(credentials.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )

        access_token = create_access_token(
            data={"user_id": user.id, "role": user.role.value},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        await log_action(
            session=self.session,
            user_id=user.id,
            action="login",
            entity_type=EntityType.user,
            entity_id=user.id,
        )
        return Token(access_token=access_token, token_type="bearer")

    async def list_users(
        self, skip: int = 0, limit: int = 20, role: Optional[UserRole] = None
    ) -> list[User]:
        statement = select(User)
        if role:
            statement = statement.where(User.role == role)
        statement = statement.order_by(User.id).offset(skip).limit(limit)
        return list((await self.session.exec(statement)).all())
