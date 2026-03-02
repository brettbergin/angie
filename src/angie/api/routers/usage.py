"""Usage router — token usage tracking endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from angie.api.auth import get_current_user
from angie.db.session import get_session
from angie.models.token_usage import TokenUsage
from angie.models.user import User

router = APIRouter()


class UsageRecordOut(BaseModel):
    id: str
    user_id: str | None
    agent_slug: str | None
    provider: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int
    tool_call_count: int
    estimated_cost_usd: float
    source: str
    task_id: str | None
    conversation_id: str | None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class UsageSummaryRow(BaseModel):
    agent_slug: str | None
    provider: str | None
    model: str | None
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float
    request_count: int


class DailyUsageRow(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    total_cost_usd: float
    request_count: int


class UsageTotals(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float
    total_requests: int


@router.get("/", response_model=list[UsageRecordOut])
async def list_usage(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    agent_slug: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Paginated list of usage records for the current user."""
    stmt = select(TokenUsage).where(TokenUsage.user_id == current_user.id)

    if agent_slug:
        stmt = stmt.where(TokenUsage.agent_slug == agent_slug)
    if start_date:
        stmt = stmt.where(TokenUsage.created_at >= start_date)
    if end_date:
        stmt = stmt.where(TokenUsage.created_at <= end_date)

    stmt = stmt.order_by(TokenUsage.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/summary", response_model=list[UsageSummaryRow])
async def usage_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
):
    """Aggregated usage grouped by agent/provider/model."""
    stmt = (
        select(
            TokenUsage.agent_slug,
            TokenUsage.provider,
            TokenUsage.model,
            func.sum(TokenUsage.input_tokens).label("total_input_tokens"),
            func.sum(TokenUsage.output_tokens).label("total_output_tokens"),
            func.sum(TokenUsage.total_tokens).label("total_tokens"),
            func.sum(TokenUsage.estimated_cost_usd).label("total_cost_usd"),
            func.sum(TokenUsage.request_count).label("request_count"),
        )
        .where(TokenUsage.user_id == current_user.id)
        .group_by(TokenUsage.agent_slug, TokenUsage.provider, TokenUsage.model)
    )

    if start_date:
        stmt = stmt.where(TokenUsage.created_at >= start_date)
    if end_date:
        stmt = stmt.where(TokenUsage.created_at <= end_date)

    result = await session.execute(stmt)
    rows = result.all()
    return [
        UsageSummaryRow(
            agent_slug=r.agent_slug,
            provider=r.provider,
            model=r.model,
            total_input_tokens=int(r.total_input_tokens or 0),
            total_output_tokens=int(r.total_output_tokens or 0),
            total_tokens=int(r.total_tokens or 0),
            total_cost_usd=float(r.total_cost_usd or 0),
            request_count=int(r.request_count or 0),
        )
        for r in rows
    ]


Granularity = Literal["15min", "30min", "1h", "1d"]

_TIME_BUCKETS: dict[str, str] = {
    "1d": "DATE(created_at)",
    "1h": "DATE_FORMAT(created_at, '%Y-%m-%d %H:00:00')",
    "30min": (
        "CONCAT(DATE_FORMAT(created_at, '%Y-%m-%d %H:'),"
        " LPAD(FLOOR(MINUTE(created_at)/30)*30, 2, '0'), ':00')"
    ),
    "15min": (
        "CONCAT(DATE_FORMAT(created_at, '%Y-%m-%d %H:'),"
        " LPAD(FLOOR(MINUTE(created_at)/15)*15, 2, '0'), ':00')"
    ),
}


@router.get("/daily", response_model=list[DailyUsageRow])
async def daily_usage(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    granularity: Granularity = Query("1d"),
):
    """Token usage breakdown for charting. Supports sub-day granularity."""
    bucket_sql = _TIME_BUCKETS[granularity]
    bucket_col = literal_column(bucket_sql)
    stmt = (
        select(
            bucket_col.label("date"),
            func.sum(TokenUsage.input_tokens).label("input_tokens"),
            func.sum(TokenUsage.output_tokens).label("output_tokens"),
            func.sum(TokenUsage.total_tokens).label("total_tokens"),
            func.sum(TokenUsage.estimated_cost_usd).label("total_cost_usd"),
            func.sum(TokenUsage.request_count).label("request_count"),
        )
        .where(TokenUsage.user_id == current_user.id)
        .group_by(bucket_col)
        .order_by(bucket_col)
    )

    if start_date:
        stmt = stmt.where(TokenUsage.created_at >= start_date)
    if end_date:
        stmt = stmt.where(TokenUsage.created_at <= end_date)

    result = await session.execute(stmt)
    rows = result.all()
    return [
        DailyUsageRow(
            date=str(r.date),
            input_tokens=int(r.input_tokens or 0),
            output_tokens=int(r.output_tokens or 0),
            total_tokens=int(r.total_tokens or 0),
            total_cost_usd=float(r.total_cost_usd or 0),
            request_count=int(r.request_count or 0),
        )
        for r in rows
    ]


@router.get("/totals", response_model=UsageTotals)
async def usage_totals(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
):
    """Single-row totals for the current user."""
    stmt = select(
        func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("total_input_tokens"),
        func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("total_output_tokens"),
        func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
        func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0).label("total_cost_usd"),
        func.coalesce(func.sum(TokenUsage.request_count), 0).label("total_requests"),
    ).where(TokenUsage.user_id == current_user.id)

    if start_date:
        stmt = stmt.where(TokenUsage.created_at >= start_date)
    if end_date:
        stmt = stmt.where(TokenUsage.created_at <= end_date)

    result = await session.execute(stmt)
    row = result.one()
    return UsageTotals(
        total_input_tokens=int(row.total_input_tokens),
        total_output_tokens=int(row.total_output_tokens),
        total_tokens=int(row.total_tokens),
        total_cost_usd=float(row.total_cost_usd),
        total_requests=int(row.total_requests),
    )
