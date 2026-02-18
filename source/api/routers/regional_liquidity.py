from fastapi import APIRouter, Depends, Query

from api.dependencies import get_ch, get_redis_client, get_pg
from api.services import regional_liquidity_service

router = APIRouter()


@router.get("/distribution")
async def regional_liquidity_distribution(
    year: int = Query(...),
    month: int = Query(...),
    accounting_system: str | None = Query(None),
    redis=Depends(get_redis_client),
    pg=Depends(get_pg),
):
    ch = get_ch()
    try:
        return await regional_liquidity_service.get_regional_liquidity(
            ch, redis, pg,
            year=year, month=month,
            accounting_system=accounting_system,
        )
    finally:
        ch.disconnect()
