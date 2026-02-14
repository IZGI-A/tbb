from fastapi import APIRouter, Depends, Query

from api.dependencies import get_ch, get_redis_client
from api.services import region_service

router = APIRouter()


@router.get("/stats")
async def stats(
    region: str | None = Query(None),
    metric: str | None = Query(None),
    year: int | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await region_service.get_stats(ch, redis, region=region, metric=metric, year=year)
    finally:
        ch.disconnect()


@router.get("/periods")
async def periods(redis=Depends(get_redis_client)):
    ch = get_ch()
    try:
        return await region_service.get_periods(ch, redis)
    finally:
        ch.disconnect()


@router.get("/list")
async def region_list(redis=Depends(get_redis_client)):
    ch = get_ch()
    try:
        return await region_service.get_regions(ch, redis)
    finally:
        ch.disconnect()


@router.get("/metrics")
async def metrics(redis=Depends(get_redis_client)):
    ch = get_ch()
    try:
        return await region_service.get_metrics(ch, redis)
    finally:
        ch.disconnect()


@router.get("/comparison")
async def comparison(
    metric: str = Query(...),
    year: int = Query(...),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await region_service.get_comparison(ch, redis, metric=metric, year=year)
    finally:
        ch.disconnect()
