from fastapi import APIRouter, Depends, Query

from api.dependencies import get_pg, get_redis_client
from api.services import bank_service

router = APIRouter()


@router.get("/")
async def list_banks(
    pool=Depends(get_pg),
    redis=Depends(get_redis_client),
):
    return await bank_service.get_banks(pool, redis)


@router.get("/dashboard-stats")
async def dashboard_stats(
    pool=Depends(get_pg),
    redis=Depends(get_redis_client),
):
    """Aggregated statistics for the main dashboard."""
    return await bank_service.get_dashboard_stats(pool, redis)


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    pool=Depends(get_pg),
    redis=Depends(get_redis_client),
):
    return await bank_service.search_banks(pool, redis, query=q)


@router.get("/{bank_name}/branches")
async def branches(
    bank_name: str,
    city: str | None = Query(None),
    pool=Depends(get_pg),
    redis=Depends(get_redis_client),
):
    return await bank_service.get_branches(pool, redis, bank_name=bank_name, city=city)


@router.get("/{bank_name}/atms")
async def atms(
    bank_name: str,
    city: str | None = Query(None),
    pool=Depends(get_pg),
    redis=Depends(get_redis_client),
):
    return await bank_service.get_atms(pool, redis, bank_name=bank_name, city=city)


@router.get("/{bank_name}/history")
async def history(
    bank_name: str,
    pool=Depends(get_pg),
    redis=Depends(get_redis_client),
):
    return await bank_service.get_history(pool, redis, bank_name=bank_name)
