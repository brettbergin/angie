"""Tests for angie.db.session and angie.db.repository."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


# ── Settings properties ────────────────────────────────────────────────────────


def test_database_url():
    from angie.config import Settings

    s = Settings(
        secret_key="k",
        db_password="pass",
        db_host="db",
        db_port=3307,
        db_name="mydb",
        db_user="user",
    )  # type: ignore[call-arg]
    assert s.database_url == "mysql+aiomysql://user:pass@db:3307/mydb"


def test_database_url_sync():
    from angie.config import Settings

    s = Settings(secret_key="k", db_password="pass")  # type: ignore[call-arg]
    assert "pymysql" in s.database_url_sync


def test_redis_url_no_password():
    from angie.config import Settings

    s = Settings(
        secret_key="k", db_password="pass", redis_host="redis", redis_port=6380, redis_db=1
    )  # type: ignore[call-arg]
    assert s.redis_url == "redis://redis:6380/1"


def test_redis_url_with_password():
    from angie.config import Settings

    s = Settings(secret_key="k", db_password="pass", redis_password="secret")  # type: ignore[call-arg]
    assert "secret@" in s.redis_url


def test_celery_broker_uses_redis_fallback():
    from angie.config import Settings

    s = Settings(secret_key="k", db_password="pass")  # type: ignore[call-arg]
    assert s.effective_celery_broker == s.redis_url


def test_celery_broker_custom():
    from angie.config import Settings

    s = Settings(secret_key="k", db_password="pass", celery_broker_url="redis://custom:6379/0")  # type: ignore[call-arg]
    assert s.effective_celery_broker == "redis://custom:6379/0"


def test_celery_backend_custom():
    from angie.config import Settings

    s = Settings(secret_key="k", db_password="pass", celery_result_backend="redis://custom:6379/1")  # type: ignore[call-arg]
    assert s.effective_celery_backend == "redis://custom:6379/1"


# ── DB session ─────────────────────────────────────────────────────────────────


def test_get_session_factory_returns_callable():
    from angie.db import session as db_session

    # Mock the engine creation to avoid needing actual DB
    with (
        patch("angie.config.get_settings") as mock_gs,
        patch("angie.db.session.create_async_engine"),
        patch("angie.db.session.async_sessionmaker") as mock_sm,
    ):
        s = MagicMock()
        s.database_url = "mysql+aiomysql://user:pass@localhost/db"
        mock_gs.return_value = s
        mock_sm.return_value = lambda: None

        db_session._engine = None
        db_session._session_factory = None
        factory = db_session.get_session_factory()
        assert factory is not None
        db_session._session_factory = None
        db_session._engine = None


def test_get_session_factory_caches():
    from angie.db import session as db_session

    with (
        patch("angie.config.get_settings") as mock_gs,
        patch("angie.db.session.create_async_engine"),
        patch("angie.db.session.async_sessionmaker") as mock_sm,
    ):
        s = MagicMock()
        s.database_url = "mysql+aiomysql://user:pass@localhost/db"
        mock_gs.return_value = s
        mock_sm.return_value = lambda: None

        db_session._engine = None
        db_session._session_factory = None
        f1 = db_session.get_session_factory()
        f2 = db_session.get_session_factory()
        assert f1 is f2
        db_session._session_factory = None
        db_session._engine = None


# ── DB repository ──────────────────────────────────────────────────────────────


async def test_repository_get():
    from angie.db.repository import Repository

    mock_session = AsyncMock()
    mock_obj = MagicMock()
    mock_session.get.return_value = mock_obj

    repo = Repository(MagicMock, mock_session)
    result = await repo.get("some-id")
    assert result is mock_obj


async def test_repository_get_not_found():
    from angie.db.repository import Repository

    mock_session = AsyncMock()
    mock_session.get.return_value = None

    repo = Repository(MagicMock, mock_session)
    result = await repo.get("missing-id")
    assert result is None


async def test_repository_list():
    from angie.db.repository import Repository

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_session.execute.return_value = mock_result

    class FakeModel:
        pass

    mock_stmt = MagicMock()
    mock_stmt.limit.return_value.offset.return_value = mock_stmt

    with patch("angie.db.repository.select", return_value=mock_stmt):
        repo = Repository(FakeModel, mock_session)
        result = await repo.list(limit=50, offset=0)

    assert len(result) == 2


async def test_repository_create():
    from angie.db.repository import Repository

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    class FakeModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    repo = Repository(FakeModel, mock_session)
    result = await repo.create(name="test", value=42)

    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once()
    assert result.name == "test"
    assert result.value == 42


async def test_repository_update():
    from angie.db.repository import Repository

    mock_session = AsyncMock()
    mock_obj = MagicMock()

    repo = Repository(MagicMock, mock_session)
    await repo.update(mock_obj, status="done")

    assert mock_obj.status == "done"
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once()


async def test_repository_delete():
    from angie.db.repository import Repository

    mock_session = AsyncMock()
    mock_obj = MagicMock()

    repo = Repository(MagicMock, mock_session)
    await repo.delete(mock_obj)

    mock_session.delete.assert_called_once_with(mock_obj)
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_get_session_rollback_on_exception():
    """Cover the rollback path in get_session (session.py lines 56-57)."""
    from angie.db.session import get_session

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async_ctx = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    async_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_callable = MagicMock(return_value=async_ctx)
    mock_get_factory = MagicMock(return_value=mock_callable)

    with patch("angie.db.session.get_session_factory", mock_get_factory):
        gen = get_session()
        session = await gen.__anext__()  # Reaches the yield
        assert session is mock_session

        # Throw exception into the generator to trigger rollback
        try:
            await gen.athrow(RuntimeError("db error"))
        except RuntimeError:
            pass

    mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_get_session_commit_on_success():
    """Cover commit path in get_session (session.py line 54)."""
    from angie.db.session import get_session

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async_ctx = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    async_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_callable = MagicMock(return_value=async_ctx)
    mock_get_factory = MagicMock(return_value=mock_callable)

    with patch("angie.db.session.get_session_factory", mock_get_factory):
        gen = get_session()
        session = await gen.__anext__()
        assert session is mock_session

        # No exception — generator completes normally → commit is called
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

    mock_session.commit.assert_called_once()
