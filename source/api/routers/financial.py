from fastapi import APIRouter, Depends, Query

from source.api.dependencies import get_ch, get_redis_client, get_pg
from source.api.services import financial_service

router = APIRouter()


@router.get("/statements")
async def list_statements(
    year: int | None = Query(None),
    month: int | None = Query(None),
    bank_name: str | None = Query(None),
    accounting_system: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await financial_service.get_statements(
            ch, redis, year=year, month=month,
            bank_name=bank_name, accounting_system=accounting_system,
            limit=limit, offset=offset,
        )
    finally:
        ch.disconnect()


@router.get("/summary")
async def summary(
    year: int | None = Query(None),
    metric: str | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await financial_service.get_summary(ch, redis, year=year, metric=metric)
    finally:
        ch.disconnect()


@router.get("/periods")
async def periods(redis=Depends(get_redis_client)):
    ch = get_ch()
    try:
        return await financial_service.get_periods(ch, redis)
    finally:
        ch.disconnect()


@router.get("/time-series")
async def time_series(
    bank_name: str = Query(...),
    statement: str | None = Query(None),
    from_year: int | None = Query(None),
    to_year: int | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await financial_service.get_time_series(
            ch, redis, bank_name=bank_name, statement=statement,
            from_year=from_year, to_year=to_year,
        )
    finally:
        ch.disconnect()
