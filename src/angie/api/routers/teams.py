"""Teams router — CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
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


class TeamOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    goal: str | None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[TeamOut])
async def list_teams(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Team).order_by(Team.name))
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
