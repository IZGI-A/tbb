from fastapi import APIRouter, Depends, Query

from api.dependencies import get_ch, get_redis_client, get_pg
from api.services import liquidity_service

router = APIRouter()


@router.get("/creation")
async def liquidity_creation(
    year: int = Query(...),
    month: int = Query(...),
    accounting_system: str | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await liquidity_service.get_liquidity_creation(
            ch, redis, year=year, month=month,
            accounting_system=accounting_system,
        )
    finally:
        ch.disconnect()


@router.get("/time-series")
async def liquidity_time_series(
    bank_name: str | None = Query(None),
    from_year: int | None = Query(None),
    to_year: int | None = Query(None),
    accounting_system: str | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await liquidity_service.get_liquidity_time_series(
            ch, redis, bank_name=bank_name,
            from_year=from_year, to_year=to_year,
            accounting_system=accounting_system,
        )
    finally:
        ch.disconnect()


@router.get("/groups")
async def liquidity_groups(
    year: int = Query(...),
    month: int = Query(...),
    accounting_system: str | None = Query(None),
    redis=Depends(get_redis_client),
    pg=Depends(get_pg),
):
    ch = get_ch()
    try:
        return await liquidity_service.get_liquidity_by_group(
            ch, redis, pg, year=year, month=month,
            accounting_system=accounting_system,
        )
    finally:
        ch.disconnect()


@router.get("/group-time-series")
async def liquidity_group_time_series(
    accounting_system: str | None = Query(None),
    col: str = Query("amount_total"),
    redis=Depends(get_redis_client),
    pg=Depends(get_pg),
):
    ch = get_ch()
    try:
        return await liquidity_service.get_liquidity_group_time_series(
            ch, redis, pg,
            accounting_system=accounting_system,
            col=col,
        )
    finally:
        ch.disconnect()


@router.get("/group-time-series-article")
async def liquidity_group_time_series_article(
    accounting_system: str | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await liquidity_service.get_liquidity_group_time_series_article(
            ch, redis,
            accounting_system=accounting_system,
        )
    finally:
        ch.disconnect()


@router.get("/decomposition")
async def liquidity_decomposition(
    bank_name: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    accounting_system: str | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await liquidity_service.get_liquidity_decomposition(
            ch, redis, bank_name=bank_name,
            year=year, month=month,
            accounting_system=accounting_system,
        )
    finally:
        ch.disconnect()
