"""Tasks router."""

from fastapi import APIRouter, Depends

from angie.api.auth import get_current_user
from angie.models.user import User

router = APIRouter()


@router.get("/")
async def list_tasks(_: User = Depends(get_current_user)):
    return []
