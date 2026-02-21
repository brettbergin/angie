"""Teams router — CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from angie.api.auth import get_current_user
from angie.db.session import get_session
from angie.models.team import Team
from angie.models.user import User

router = APIRouter()


class TeamCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    goal: str | None = None
    agent_slugs: list[str] = []
    is_enabled: bool = True


class TeamOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    goal: str | None
    agent_slugs: list[str]
    is_enabled: bool

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[TeamOut])
async def list_teams(
    enabled_only: bool = Query(False),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Team).order_by(Team.name)
    if enabled_only:
        stmt = stmt.where(Team.is_enabled.is_(True))
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    team = Team(**body.model_dump())
    session.add(team)
    await session.flush()
    await session.refresh(team)
    return team


@router.get("/{team_id}", response_model=TeamOut)
async def get_team(
    team_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


class TeamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    goal: str | None = None
    agent_slugs: list[str] | None = None
    is_enabled: bool | None = None


@router.patch("/{team_id}", response_model=TeamOut)
async def update_team(
    team_id: str,
    body: TeamUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    await session.flush()
    await session.refresh(team)
    return team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    await session.delete(team)
