"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from angie.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Angie API",
        description="Angie — personal AI assistant REST API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from angie.api.routers import (
        agents,
        auth,
        channels,
        chat,
        conversations,
        events,
        prompts,
        tasks,
        teams,
        users,
        workflows,
    )

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
    app.include_router(teams.router, prefix="/api/v1/teams", tags=["teams"])
    app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
    app.include_router(events.router, prefix="/api/v1/events", tags=["events"])
    app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])
    app.include_router(channels.router, prefix="/api/v1/channels", tags=["channels"])
    app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["conversations"])
    app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "angie-api"}

    return app


app = create_app()
