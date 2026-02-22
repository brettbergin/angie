"""Media file serving — screenshots and other agent-generated files."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from angie.config import get_settings
from angie.db.session import get_session
from angie.models.user import User

router = APIRouter()


async def _authenticate_via_query(
    token: str = Query(..., alias="token"),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Authenticate via query parameter (for img src URLs)."""
    settings = get_settings()
    credentials_exc = HTTPException(status_code=401, detail="Invalid token")
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


@router.get("/{filename}")
async def get_media(filename: str, _: User = Depends(_authenticate_via_query)):
    """Serve a media file from the screenshots directory."""
    settings = get_settings()
    media_dir = Path(settings.web_screenshots_dir)

    # Prevent path traversal
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = media_dir / safe_name
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(filepath, media_type="image/png")
