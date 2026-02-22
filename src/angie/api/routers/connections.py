"""Connections router — credential management CRUD + test."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from angie.api.auth import get_current_user
from angie.core.connections import get_service_registry, test_connection_validity
from angie.core.crypto import decrypt_json, encrypt_json, mask_credential
from angie.db.session import get_session
from angie.models.connection import Connection, ConnectionStatus
from angie.models.user import User

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────


class FieldDef(BaseModel):
    key: str
    label: str
    type: str


class ServiceOut(BaseModel):
    key: str
    name: str
    description: str
    auth_type: str
    color: str
    fields: list[FieldDef]
    agent_slug: str | None


class ConnectionOut(BaseModel):
    id: str
    service_type: str
    display_name: str | None
    auth_type: str
    status: str
    masked_credentials: dict[str, str]
    scopes: str | None
    token_expires_at: datetime | None
    last_used_at: datetime | None
    last_tested_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class ConnectionCreate(BaseModel):
    service_type: str
    credentials: dict[str, str]
    display_name: str | None = None


class ConnectionUpdate(BaseModel):
    credentials: dict[str, str] | None = None
    display_name: str | None = None


class TestResult(BaseModel):
    success: bool
    message: str
    status: str


# ── Helpers ────────────────────────────────────────────────────────────────────


def _to_connection_out(conn: Connection) -> ConnectionOut:
    """Convert a Connection model to a ConnectionOut with masked credentials."""
    try:
        creds = decrypt_json(conn.credentials_encrypted)
        masked = {k: mask_credential(v) if v else "" for k, v in creds.items()}
    except (ValueError, Exception):
        masked = {}

    return ConnectionOut(
        id=conn.id,
        service_type=conn.service_type,
        display_name=conn.display_name,
        auth_type=conn.auth_type,
        status=conn.status,
        masked_credentials=masked,
        scopes=conn.scopes,
        token_expires_at=conn.token_expires_at,
        last_used_at=conn.last_used_at,
        last_tested_at=conn.last_tested_at,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/services", response_model=list[ServiceOut])
async def list_services(_: User = Depends(get_current_user)):
    """List all available service definitions."""
    registry = get_service_registry()
    return [
        ServiceOut(
            key=key,
            name=svc["name"],
            description=svc["description"],
            auth_type=svc["auth_type"],
            color=svc["color"],
            fields=[FieldDef(**f) for f in svc["fields"]],
            agent_slug=svc.get("agent_slug"),
        )
        for key, svc in registry.items()
    ]


@router.get("/", response_model=list[ConnectionOut])
async def list_connections(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all connections for the current user."""
    result = await session.execute(
        select(Connection).where(Connection.user_id == user.id).order_by(Connection.service_type)
    )
    connections = result.scalars().all()
    return [_to_connection_out(c) for c in connections]


@router.get("/{connection_id}", response_model=ConnectionOut)
async def get_connection(
    connection_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific connection (credentials masked)."""
    conn = await session.get(Connection, connection_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _to_connection_out(conn)


@router.post("/", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
async def create_connection(
    body: ConnectionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new service connection."""
    registry = get_service_registry()
    if body.service_type not in registry:
        raise HTTPException(status_code=400, detail=f"Unknown service type: {body.service_type}")

    # Check for existing connection
    existing = await session.execute(
        select(Connection).where(
            Connection.user_id == user.id,
            Connection.service_type == body.service_type,
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=409,
            detail=f"Connection for {body.service_type} already exists. Update or delete it first.",
        )

    service = registry[body.service_type]
    conn = Connection(
        user_id=user.id,
        service_type=body.service_type,
        display_name=body.display_name or service["name"],
        auth_type=service["auth_type"],
        credentials_encrypted=encrypt_json(body.credentials),
        status=ConnectionStatus.CONNECTED,
    )
    session.add(conn)
    await session.flush()
    await session.refresh(conn)
    return _to_connection_out(conn)


@router.patch("/{connection_id}", response_model=ConnectionOut)
async def update_connection(
    connection_id: str,
    body: ConnectionUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update connection credentials or display name."""
    conn = await session.get(Connection, connection_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Connection not found")

    if body.display_name is not None:
        conn.display_name = body.display_name
    if body.credentials is not None:
        # Merge provided credentials into existing ones to avoid wiping secrets
        try:
            existing_credentials = (
                decrypt_json(conn.credentials_encrypted) if conn.credentials_encrypted else {}
            )
        except ValueError:
            # If decryption fails, fall back to treating existing credentials as empty
            existing_credentials = {}

        updated_credentials = dict(existing_credentials)
        for key, value in body.credentials.items():
            # Ignore empty-string values so they don't overwrite existing secrets
            if value == "":
                continue
            updated_credentials[key] = value

        conn.credentials_encrypted = encrypt_json(updated_credentials)
        conn.status = ConnectionStatus.CONNECTED

    await session.flush()
    await session.refresh(conn)
    return _to_connection_out(conn)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Disconnect and delete a connection."""
    conn = await session.get(Connection, connection_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Connection not found")
    await session.delete(conn)


@router.post("/{connection_id}/test", response_model=TestResult)
async def test_connection(
    connection_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Test connection validity by calling the service's test endpoint."""
    conn = await session.get(Connection, connection_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        credentials = decrypt_json(conn.credentials_encrypted)
    except ValueError:
        conn.status = ConnectionStatus.ERROR
        await session.flush()
        return TestResult(success=False, message="Corrupted credentials", status="error")

    from sqlalchemy import func

    success, message = await test_connection_validity(credentials, conn.service_type)
    conn.last_tested_at = func.now()
    conn.status = ConnectionStatus.CONNECTED if success else ConnectionStatus.ERROR
    await session.flush()

    return TestResult(success=success, message=message, status=conn.status)
