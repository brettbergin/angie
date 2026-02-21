"""Agents router — CRUD + registry listing."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from angie.api.auth import get_current_user
from angie.models.user import User

router = APIRouter()


class AgentOut(BaseModel):
    slug: str
    name: str
    description: str
    capabilities: list[str]


class AgentDetailOut(AgentOut):
    system_prompt: str
    module_path: str


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


@router.get("/{slug}", response_model=AgentDetailOut)
async def get_agent(slug: str, _: User = Depends(get_current_user)):
    from angie.agents.registry import get_registry

    registry = get_registry()
    agent = registry.get(slug)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{slug}' not found")
    module_path = type(agent).__module__
    return AgentDetailOut(
        slug=agent.slug,
        name=agent.name,
        description=agent.description,
        capabilities=agent.capabilities,
        system_prompt=agent.get_system_prompt(),
        module_path=module_path,
    )
