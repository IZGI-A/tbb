import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # PostgreSQL
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "tbb_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "tbb_secure_pass_123")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "tbb")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ClickHouse
    CLICKHOUSE_HOST: str = os.getenv("CLICKHOUSE_HOST", "localhost")
    CLICKHOUSE_PORT: int = int(os.getenv("CLICKHOUSE_PORT", "9000"))
    CLICKHOUSE_HTTP_PORT: int = int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123"))
    CLICKHOUSE_DB: str = os.getenv("CLICKHOUSE_DB", "tbb")
    CLICKHOUSE_USER: str = os.getenv("CLICKHOUSE_USER", "default")
    CLICKHOUSE_PASSWORD: str = os.getenv("CLICKHOUSE_PASSWORD", "")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # FastAPI
    FASTAPI_HOST: str = os.getenv("FASTAPI_HOST", "0.0.0.0")
    FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")

    # TBB API
    TBB_API_URL: str = os.getenv(
        "TBB_API_URL", "https://verisistemi.tbb.org.tr/api/router"
    )
    TBB_API_TOKEN: str = os.getenv("TBB_API_TOKEN", "asd")
    TBB_API_ROLE: str = os.getenv("TBB_API_ROLE", "1")
    TBB_API_LANG: str = os.getenv("TBB_API_LANG", "tr")
    TBB_RATE_LIMIT_SECONDS: float = float(
        os.getenv("TBB_RATE_LIMIT_SECONDS", "1")
    )


settings = Settings()
