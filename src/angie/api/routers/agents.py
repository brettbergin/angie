"""Agents router — CRUD + registry listing."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from angie.api.auth import get_current_user
from angie.models.user import User

router = APIRouter()


class AgentOut(BaseModel):
    slug: str
    name: str
    description: str
    capabilities: list[str]


@router.get("/", response_model=list[AgentOut])
async def list_agents(_: User = Depends(get_current_user)):
    from angie.agents.registry import get_registry

    registry = get_registry()
    return [
        AgentOut(
            slug=a.slug,
            name=a.name,
            description=a.description,
            capabilities=a.capabilities,
        )
        for a in registry.list_all()
    ]
