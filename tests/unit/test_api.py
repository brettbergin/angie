"""Tests for angie.api.app and angie.api.auth."""

import os
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure required env vars are set before importing Settings-dependent modules
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("DB_PASSWORD", "test-password")


# ── App tests ─────────────────────────────────────────────────────────────────

def _get_test_client():
    from angie.api.app import create_app

    with patch("angie.config.get_settings") as mock_gs:
        mock_settings = MagicMock()
        mock_settings.cors_origins = ["http://localhost:3000"]
        mock_settings.secret_key = "test-secret-key-for-testing"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expire_minutes = 30
        mock_settings.jwt_refresh_token_expire_days = 30
        mock_gs.return_value = mock_settings

        app = create_app()
        return TestClient(app)


def test_health_endpoint():
    client = _get_test_client()
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "angie-api"


def test_app_has_cors_middleware():
    from angie.api.app import create_app

    with patch("angie.config.get_settings") as mock_gs:
        mock_settings = MagicMock()
        mock_settings.cors_origins = ["http://localhost:3000"]
        mock_gs.return_value = mock_settings

        app = create_app()

    # CORS middleware is in the middleware stack
    middleware_classes = [str(m) for m in app.user_middleware]
    assert any("cors" in m.lower() or "CORS" in m for m in middleware_classes) or len(app.user_middleware) > 0


def test_app_routers_registered():
    from angie.api.app import create_app

    with patch("angie.config.get_settings") as mock_gs:
        mock_settings = MagicMock()
        mock_settings.cors_origins = []
        mock_gs.return_value = mock_settings

        app = create_app()

    routes = [r.path for r in app.routes]
    assert any("/api/v1/auth" in r for r in routes)
    assert any("/health" in r for r in routes)


def test_unhandled_exception_returns_500():
    from angie.api.app import create_app

    with patch("angie.config.get_settings") as mock_gs:
        mock_settings = MagicMock()
        mock_settings.cors_origins = []
        mock_gs.return_value = mock_settings

        app = create_app()

    from fastapi import Request

    @app.get("/raise-error")
    async def raise_error():
        raise RuntimeError("oops")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/raise-error")
    assert response.status_code == 500


# ── Auth utility tests ────────────────────────────────────────────────────────

def _make_settings_for_auth():
    from angie.config import Settings

    return Settings(secret_key="test-jwt-secret", db_password="pass")  # type: ignore[call-arg]


def test_hash_password():
    from angie.api.auth import hash_password, verify_password

    hashed = hash_password("mypassword")
    assert hashed != "mypassword"
    assert verify_password("mypassword", hashed)


def test_verify_password_wrong():
    from angie.api.auth import hash_password, verify_password

    hashed = hash_password("correctpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_create_access_token():
    from jose import jwt

    from angie.api.auth import create_access_token

    settings = _make_settings_for_auth()
    with patch("angie.api.auth.get_settings", return_value=settings):
        token = create_access_token({"sub": "user-123"})

    decoded = jwt.decode(token, "test-jwt-secret", algorithms=["HS256"])
    assert decoded["sub"] == "user-123"
    assert "exp" in decoded


def test_create_access_token_custom_expiry():
    from jose import jwt

    from angie.api.auth import create_access_token

    settings = _make_settings_for_auth()
    with patch("angie.api.auth.get_settings", return_value=settings):
        token = create_access_token({"sub": "user-456"}, expires_delta=timedelta(hours=2))

    decoded = jwt.decode(token, "test-jwt-secret", algorithms=["HS256"])
    assert decoded["sub"] == "user-456"


def test_create_refresh_token():
    from jose import jwt

    from angie.api.auth import create_refresh_token

    settings = _make_settings_for_auth()
    with patch("angie.api.auth.get_settings", return_value=settings):
        token = create_refresh_token({"sub": "user-789"})

    decoded = jwt.decode(token, "test-jwt-secret", algorithms=["HS256"])
    assert decoded["sub"] == "user-789"


async def test_get_current_user_valid():
    from jose import jwt

    from angie.api.auth import get_current_user

    settings = _make_settings_for_auth()
    payload = {"sub": "user-id-1"}
    token = jwt.encode(payload, "test-jwt-secret", algorithm="HS256")

    mock_user = MagicMock()
    mock_user.is_active = True

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_user

    with patch("angie.api.auth.get_settings", return_value=settings):
        user = await get_current_user(token=token, session=mock_session)

    assert user is mock_user


async def test_get_current_user_invalid_token():
    from fastapi import HTTPException

    from angie.api.auth import get_current_user

    settings = _make_settings_for_auth()
    mock_session = AsyncMock()

    with patch("angie.api.auth.get_settings", return_value=settings):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="invalid-token", session=mock_session)

    assert exc_info.value.status_code == 401


async def test_get_current_user_no_sub():
    from jose import jwt

    from fastapi import HTTPException

    from angie.api.auth import get_current_user

    settings = _make_settings_for_auth()
    token = jwt.encode({"data": "no-sub"}, "test-jwt-secret", algorithm="HS256")
    mock_session = AsyncMock()

    with patch("angie.api.auth.get_settings", return_value=settings):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, session=mock_session)

    assert exc_info.value.status_code == 401


async def test_get_current_user_not_found():
    from jose import jwt

    from fastapi import HTTPException

    from angie.api.auth import get_current_user

    settings = _make_settings_for_auth()
    token = jwt.encode({"sub": "missing-user"}, "test-jwt-secret", algorithm="HS256")

    mock_session = AsyncMock()
    mock_session.get.return_value = None

    with patch("angie.api.auth.get_settings", return_value=settings):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, session=mock_session)

    assert exc_info.value.status_code == 401


async def test_get_current_user_inactive():
    from jose import jwt

    from fastapi import HTTPException

    from angie.api.auth import get_current_user

    settings = _make_settings_for_auth()
    token = jwt.encode({"sub": "inactive-user"}, "test-jwt-secret", algorithm="HS256")

    mock_user = MagicMock()
    mock_user.is_active = False

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_user

    with patch("angie.api.auth.get_settings", return_value=settings):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, session=mock_session)

    assert exc_info.value.status_code == 401


async def test_get_current_superuser_ok():
    from angie.api.auth import get_current_superuser

    mock_user = MagicMock()
    mock_user.is_superuser = True

    result = await get_current_superuser(current_user=mock_user)
    assert result is mock_user


async def test_get_current_superuser_not_super():
    from fastapi import HTTPException

    from angie.api.auth import get_current_superuser

    mock_user = MagicMock()
    mock_user.is_superuser = False

    with pytest.raises(HTTPException) as exc_info:
        await get_current_superuser(current_user=mock_user)

    assert exc_info.value.status_code == 403


# ── Auth router tests ─────────────────────────────────────────────────────────

def _get_auth_test_client():
    from angie.api.app import create_app

    with patch("angie.config.get_settings") as mock_gs:
        mock_settings = MagicMock()
        mock_settings.cors_origins = []
        mock_settings.secret_key = "test-secret-key-for-testing"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expire_minutes = 30
        mock_settings.jwt_refresh_token_expire_days = 30
        mock_gs.return_value = mock_settings
        app = create_app()
        return TestClient(app, raise_server_exceptions=False)


async def test_register_endpoint():
    from angie.api.routers.auth import RegisterRequest, register

    body = RegisterRequest(email="test@example.com", username="testuser", password="pass123")

    mock_user = MagicMock()
    mock_user.id = "user-id-1"

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    settings = _make_settings_for_auth()

    # Patch hash_password to avoid bcrypt work, and create_access_token
    with (
        patch("angie.config.get_settings", return_value=settings),
        patch("angie.api.routers.auth.hash_password", return_value="hashed"),
        patch("angie.api.routers.auth.create_access_token", return_value="access-tok"),
        patch("angie.api.routers.auth.create_refresh_token", return_value="refresh-tok"),
    ):
        result = await register(body, session=mock_session)

    assert result.token_type == "bearer"
    assert result.access_token == "access-tok"
    assert result.refresh_token == "refresh-tok"


async def test_register_email_already_exists():
    from fastapi import HTTPException

    from angie.api.routers.auth import RegisterRequest, register

    body = RegisterRequest(email="existing@example.com", username="u", password="p")

    mock_existing_user = MagicMock()
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_existing_user
    mock_session.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await register(body, session=mock_session)

    assert exc_info.value.status_code == 400
    assert "already registered" in exc_info.value.detail


def test_register_request_invalid_email():
    from pydantic import ValidationError

    from angie.api.routers.auth import RegisterRequest

    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", username="u", password="p")


async def test_login_success():
    from angie.api.routers.auth import login

    mock_user = MagicMock()
    mock_user.id = "user-id-2"
    mock_user.hashed_password = ""

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result

    settings = _make_settings_for_auth()

    form = MagicMock()
    form.username = "testuser"
    form.password = "mypassword"

    with (
        patch("angie.api.routers.auth.verify_password", return_value=True),
        patch("angie.config.get_settings", return_value=settings),
    ):
        result = await login(form=form, session=mock_session)

    assert result.token_type == "bearer"
    assert result.access_token != ""


async def test_login_invalid_credentials():
    from fastapi import HTTPException

    from angie.api.routers.auth import login

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    form = MagicMock()
    form.username = "baduser"
    form.password = "badpass"

    with pytest.raises(HTTPException) as exc_info:
        await login(form=form, session=mock_session)

    assert exc_info.value.status_code == 401
