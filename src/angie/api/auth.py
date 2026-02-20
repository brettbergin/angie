"""JWT authentication utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from angie.config import get_settings
from angie.db.session import get_session
from angie.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    payload = dict(data)
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload["exp"] = expire
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict[str, Any]) -> str:
    settings = get_settings()
    return create_access_token(
        data, expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days)
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError as exc:
        raise credentials_exc from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a superuser")
    return current_user
