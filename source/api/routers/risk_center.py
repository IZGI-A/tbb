from fastapi import APIRouter, Depends, Query

from api.dependencies import get_ch, get_redis_client
from api.services import risk_service

router = APIRouter()


@router.get("/data")
async def data(
    report_name: str | None = Query(None),
    year: int | None = Query(None),
    month: int | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await risk_service.get_data(ch, redis, report_name=report_name, year=year, month=month)
    finally:
        ch.disconnect()


@router.get("/reports")
async def reports(redis=Depends(get_redis_client)):
    ch = get_ch()
    try:
        return await risk_service.get_reports(ch, redis)
    finally:
        ch.disconnect()


@router.get("/categories")
async def categories(
    report_name: str = Query(...),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await risk_service.get_categories(ch, redis, report_name=report_name)
    finally:
        ch.disconnect()
