from fastapi import APIRouter, Depends, Query

from api.dependencies import get_ch, get_redis_client
from api.services import panel_regression_service

router = APIRouter()


@router.get("/results")
async def panel_regression_results(
    accounting_system: str | None = Query(None),
    redis=Depends(get_redis_client),
):
    ch = get_ch()
    try:
        return await panel_regression_service.run_panel_regressions(
            ch, redis, accounting_system=accounting_system,
        )
    finally:
        ch.disconnect()
