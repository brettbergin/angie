"""Users router."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from angie.api.auth import get_current_user, hash_password, verify_password
from angie.db.session import get_session
from angie.models.user import User

router = APIRouter()


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    full_name: str | None
    timezone: str
    is_active: bool

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: str | None = None
    timezone: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.timezone is not None:
        current_user.timezone = data.timezone
    session.add(current_user)
    await session.flush()
    return current_user


@router.post("/me/password")
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from fastapi import HTTPException, status

    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.hashed_password = hash_password(data.new_password)
    session.add(current_user)
    await session.flush()
    return {"detail": "Password updated"}
