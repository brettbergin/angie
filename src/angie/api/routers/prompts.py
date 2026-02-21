"""Prompts router."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from angie.api.auth import get_current_user
from angie.models.user import User

router = APIRouter()


class PromptOut(BaseModel):
    name: str
    content: str


class PromptUpdate(BaseModel):
    content: str


@router.get("/", response_model=list[PromptOut])
async def list_prompts(current_user: User = Depends(get_current_user)):
    from angie.core.prompts import get_prompt_manager

    pm = get_prompt_manager()
    prompts = pm.get_user_prompts(current_user.id)
    if not prompts:
        prompts = pm.get_user_prompts("default")
    user_dir = pm.user_prompts_dir / current_user.id
    if user_dir.exists():
        files = sorted(user_dir.glob("*.md"))
        return [{"name": f.stem, "content": f.read_text(encoding="utf-8")} for f in files]
    default_dir = pm.user_prompts_dir / "default"
    if default_dir.exists():
        files = sorted(default_dir.glob("*.md"))
        return [{"name": f.stem, "content": f.read_text(encoding="utf-8")} for f in files]
    return []


@router.get("/{name}", response_model=PromptOut)
async def get_prompt(name: str, current_user: User = Depends(get_current_user)):
    from angie.core.prompts import get_prompt_manager

    pm = get_prompt_manager()
    user_dir = pm.user_prompts_dir / current_user.id
    path = user_dir / f"{name}.md"
    if not path.exists():
        path = pm.user_prompts_dir / "default" / f"{name}.md"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Prompt '{name}' not found"
        )
    return {"name": name, "content": path.read_text(encoding="utf-8")}


@router.put("/{name}", response_model=PromptOut)
async def update_prompt(
    name: str, data: PromptUpdate, current_user: User = Depends(get_current_user)
):
    from angie.core.prompts import get_prompt_manager

    pm = get_prompt_manager()
    pm.save_user_prompt(current_user.id, name, data.content)
    return {"name": name, "content": data.content}


@router.delete("/{name}")
async def delete_prompt(name: str, current_user: User = Depends(get_current_user)):
    from angie.core.prompts import get_prompt_manager

    pm = get_prompt_manager()
    path = pm.user_prompts_dir / current_user.id / f"{name}.md"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Prompt '{name}' not found"
        )
    path.unlink(missing_ok=True)
    pm.invalidate_cache()
    return {"detail": f"Prompt '{name}' deleted"}


@router.post("/reset")
async def reset_prompts(current_user: User = Depends(get_current_user)):
    """Reset user prompts to defaults by removing user-specific prompt files."""
    import shutil

    from angie.core.prompts import get_prompt_manager

    pm = get_prompt_manager()
    user_dir = pm.user_prompts_dir / current_user.id
    if user_dir.exists():
        shutil.rmtree(user_dir)
    pm.invalidate_cache()
    return {"detail": "Prompts reset to defaults"}
