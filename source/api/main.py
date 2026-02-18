from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.postgres import get_pg_pool, close_pg_pool
from db.redis import get_redis, close_redis
from api.routers import financial, regions, risk_center, banks, liquidity, risk_analysis


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await get_pg_pool()
    await get_redis()
    yield
    # Shutdown
    await close_pg_pool()
    await close_redis()


app = FastAPI(
    title="TBB Data Platform API",
    description="Türkiye Bankalar Birliği financial data API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(financial.router, prefix="/api/financial", tags=["Financial"])
app.include_router(regions.router, prefix="/api/regions", tags=["Regions"])
app.include_router(risk_center.router, prefix="/api/risk-center", tags=["Risk Center"])
app.include_router(banks.router, prefix="/api/banks", tags=["Banks"])
app.include_router(liquidity.router, prefix="/api/liquidity", tags=["Liquidity"])
app.include_router(risk_analysis.router, prefix="/api/risk-analysis", tags=["Risk Analysis"])


@app.get("/health")
async def health():
    return {"status": "ok"}
