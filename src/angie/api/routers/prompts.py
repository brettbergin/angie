"""Prompts router — DB-backed user preferences."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from angie.api.auth import get_current_user
from angie.db.session import get_session
from angie.models.prompt import Prompt, PromptType
from angie.models.user import User

router = APIRouter()

PREFERENCE_DEFINITIONS: list[dict[str, str]] = [
    {
        "name": "personality",
        "label": "Personality",
        "description": "How would you like Angie to communicate with you?",
        "placeholder": "formal, casual, friendly, brief, etc.",
    },
    {
        "name": "interests",
        "label": "Interests",
        "description": "What are your main interests and areas Angie should know about?",
        "placeholder": "cybersecurity, woodworking, gaming, gardening...",
    },
    {
        "name": "schedule",
        "label": "Schedule",
        "description": "Describe your typical daily schedule (work hours, time zone, routines).",
        "placeholder": "work mon-fri 8-5, dinner at 7, sleep 11-7...",
    },
    {
        "name": "priorities",
        "label": "Priorities",
        "description": "What are your top priorities that Angie should always keep in mind?",
        "placeholder": "monitoring communications, GitHub alerts, email tracking...",
    },
    {
        "name": "communication",
        "label": "Communication",
        "description": "Which communication channels do you prefer and in what order?",
        "placeholder": "Slack, Discord, iMessage, email...",
    },
    {
        "name": "home",
        "label": "Home",
        "description": "Describe your home setup relevant for Angie (smart home devices, location, etc.).",
        "placeholder": "Hue lights, Home Assistant, Ubiquiti network...",
    },
    {
        "name": "work",
        "label": "Work",
        "description": "Describe your work context (role, tools, projects, workflows).",
        "placeholder": "security engineer, Python, CI/CD pipelines...",
    },
    {
        "name": "style",
        "label": "Style",
        "description": "How detailed should Angie's responses be? Any language or tone preferences?",
        "placeholder": "english, kind and light, detailed and verbose...",
    },
]

PREFERENCE_NAMES = {d["name"] for d in PREFERENCE_DEFINITIONS}


class PromptOut(BaseModel):
    name: str
    content: str


class PromptUpdate(BaseModel):
    content: str = Field(max_length=10000)


class PreferenceDefinition(BaseModel):
    name: str
    label: str
    description: str
    placeholder: str


async def _seed_defaults(user_id: str, session: AsyncSession) -> list[Prompt]:
    """Seed default preferences from filesystem for a new user."""
    import logging

    from angie.core.prompts import get_prompt_manager

    logger = logging.getLogger(__name__)
    pm = get_prompt_manager()
    default_dir = pm.user_prompts_dir / "default"
    created: list[Prompt] = []
    if default_dir.exists():
        for md_file in sorted(default_dir.glob("*.md")):
            name = md_file.stem
            if name not in PREFERENCE_NAMES:
                continue
            # Check if already exists (handles concurrent seed race)
            existing = await session.execute(
                select(Prompt).where(
                    Prompt.user_id == user_id,
                    Prompt.type == PromptType.USER,
                    Prompt.name == name,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("Failed to read default prompt %s: %s", md_file, exc)
                continue
            prompt = Prompt(
                user_id=user_id,
                type=PromptType.USER,
                name=name,
                content=content,
                is_active=True,
            )
            session.add(prompt)
            created.append(prompt)
    if created:
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            return []
        for p in created:
            await session.refresh(p)
    return created


@router.get("/definitions", response_model=list[PreferenceDefinition])
async def get_definitions(current_user: User = Depends(get_current_user)):
    """Return the preference category definitions."""
    return PREFERENCE_DEFINITIONS


@router.get("/", response_model=list[PromptOut])
async def list_prompts(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Prompt)
        .where(
            Prompt.user_id == current_user.id,
            Prompt.type == PromptType.USER,
            Prompt.is_active.is_(True),
        )
        .order_by(Prompt.name)
    )
    prompts = list(result.scalars().all())
    if not prompts:
        prompts = await _seed_defaults(current_user.id, session)
    return [{"name": p.name, "content": p.content} for p in prompts]


def _validate_preference_name(name: str) -> None:
    """Raise 400 if name is not a recognized preference category."""
    if name not in PREFERENCE_NAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid preference name '{name}'. Allowed: {', '.join(sorted(PREFERENCE_NAMES))}",
        )


@router.get("/{name}", response_model=PromptOut)
async def get_prompt(
    name: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _validate_preference_name(name)
    result = await session.execute(
        select(Prompt).where(
            Prompt.user_id == current_user.id,
            Prompt.type == PromptType.USER,
            Prompt.name == name,
            Prompt.is_active.is_(True),
        )
    )
    prompt = result.scalar_one_or_none()
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt '{name}' not found",
        )
    return {"name": prompt.name, "content": prompt.content}


@router.put("/{name}", response_model=PromptOut)
async def update_prompt(
    name: str,
    data: PromptUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _validate_preference_name(name)
    # Normalize: always strip existing header and prepend the correct one
    content = data.content.strip()
    header = f"# {name.replace('_', ' ').title()}"
    lines = content.splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)
    body = "\n".join(lines).strip()
    content = f"{header}\n\n{body}\n" if body else f"{header}\n"

    result = await session.execute(
        select(Prompt).where(
            Prompt.user_id == current_user.id,
            Prompt.type == PromptType.USER,
            Prompt.name == name,
        )
    )
    prompt = result.scalar_one_or_none()
    if prompt:
        prompt.content = content
        prompt.is_active = True
    else:
        prompt = Prompt(
            user_id=current_user.id,
            type=PromptType.USER,
            name=name,
            content=content,
            is_active=True,
        )
        session.add(prompt)
    await session.commit()
    await session.refresh(prompt)
    return {"name": prompt.name, "content": prompt.content}


@router.delete("/{name}")
async def delete_prompt(
    name: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _validate_preference_name(name)
    result = await session.execute(
        select(Prompt).where(
            Prompt.user_id == current_user.id,
            Prompt.type == PromptType.USER,
            Prompt.name == name,
        )
    )
    prompt = result.scalar_one_or_none()
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt '{name}' not found",
        )
    await session.delete(prompt)
    await session.commit()
    return {"detail": f"Prompt '{name}' deleted"}


@router.post("/reset")
async def reset_prompts(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Reset user prompts to defaults by removing and re-seeding."""
    await session.execute(
        delete(Prompt).where(
            Prompt.user_id == current_user.id,
            Prompt.type == PromptType.USER,
        )
    )
    await session.commit()
    await _seed_defaults(current_user.id, session)
    return {"detail": "Prompts reset to defaults"}

