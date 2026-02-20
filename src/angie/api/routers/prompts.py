"""Prompts router."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from angie.api.auth import get_current_user
from angie.models.user import User

router = APIRouter()

class PromptOut(BaseModel):
    name: str
    content: str

@router.get("/", response_model=list[PromptOut])
async def list_prompts(current_user: User = Depends(get_current_user)):
    from angie.core.prompts import get_prompt_manager
    pm = get_prompt_manager()
    prompts = pm.get_user_prompts(current_user.id)
    return [{"name": f"prompt_{i}", "content": p} for i, p in enumerate(prompts)]
