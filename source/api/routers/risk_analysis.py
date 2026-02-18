from fastapi import APIRouter, Depends, Query

from api.dependencies import get_ch, get_redis_client
from api.services import risk_analysis_service

router = APIRouter()


@router.get("/zscore")
async def zscore_ranking(
    year: int = Query(...),
    month: int = Query(...),
    accounting_system: str | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await risk_analysis_service.get_zscore_ranking(
            ch, redis, year=year, month=month,
            accounting_system=accounting_system,
        )
    finally:
        ch.disconnect()


@router.get("/zscore-time-series")
async def zscore_time_series(
    bank_name: str | None = Query(None),
    accounting_system: str | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await risk_analysis_service.get_zscore_time_series(
            ch, redis, bank_name=bank_name,
            accounting_system=accounting_system,
        )
    finally:
        ch.disconnect()


@router.get("/lc-risk")
async def lc_risk_relationship(
    year: int = Query(...),
    month: int = Query(...),
    accounting_system: str | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await risk_analysis_service.get_lc_risk_relationship(
            ch, redis, year=year, month=month,
            accounting_system=accounting_system,
        )
    finally:
        ch.disconnect()
