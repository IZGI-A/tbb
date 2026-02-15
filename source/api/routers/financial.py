from fastapi import APIRouter, Depends, Query

from api.dependencies import get_ch, get_redis_client, get_pg
from api.services import financial_service

router = APIRouter()


@router.get("/statements")
async def list_statements(
    year: int | None = Query(None),
    month: int | None = Query(None),
    bank_name: str | None = Query(None),
    accounting_system: str | None = Query(None),
    main_statement: str | None = Query(None),
    child_statement: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await financial_service.get_statements(
            ch, redis, year=year, month=month,
            bank_name=bank_name, accounting_system=accounting_system,
            main_statement=main_statement, child_statement=child_statement,
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


@router.get("/bank-names")
async def bank_names(redis=Depends(get_redis_client)):
    ch = get_ch()
    try:
        return await financial_service.get_bank_names(ch, redis)
    finally:
        ch.disconnect()


@router.get("/main-statements")
async def main_statements(redis=Depends(get_redis_client)):
    ch = get_ch()
    try:
        return await financial_service.get_main_statements(ch, redis)
    finally:
        ch.disconnect()


@router.get("/child-statements")
async def child_statements(
    main_statement: str | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await financial_service.get_child_statements(ch, redis, main_statement=main_statement)
    finally:
        ch.disconnect()


@router.get("/ratio-types")
async def ratio_types():
    return await financial_service.get_ratio_types()


@router.get("/ratios")
async def ratios(
    year: int = Query(...),
    month: int = Query(...),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await financial_service.get_financial_ratios(ch, redis, year=year, month=month)
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
