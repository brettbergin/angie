"""Users router."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from angie.api.auth import get_current_user
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


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
