import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # PostgreSQL
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "tbb_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "tbb_secure_pass_123")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "tbb")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5433"))

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ClickHouse
    CLICKHOUSE_HOST: str = os.getenv("CLICKHOUSE_HOST", "localhost")
    CLICKHOUSE_PORT: int = int(os.getenv("CLICKHOUSE_PORT", "9001"))
    CLICKHOUSE_HTTP_PORT: int = int(os.getenv("CLICKHOUSE_HTTP_PORT", "8124"))
    CLICKHOUSE_DB: str = os.getenv("CLICKHOUSE_DB", "tbb")
    CLICKHOUSE_USER: str = os.getenv("CLICKHOUSE_USER", "default")
    CLICKHOUSE_PASSWORD: str = os.getenv("CLICKHOUSE_PASSWORD", "")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6380"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # FastAPI
    FASTAPI_HOST: str = os.getenv("FASTAPI_HOST", "0.0.0.0")
    FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", "8001"))
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3001,http://localhost:5174"
    ).split(",")

    # TBB Scraping
    TBB_BASE_URL: str = os.getenv(
        "TBB_BASE_URL", "https://verisistemi.tbb.org.tr"
    )
    TBB_RATE_LIMIT_SECONDS: float = float(
        os.getenv("TBB_RATE_LIMIT_SECONDS", "2")
    )
    SELENIUM_HEADLESS: bool = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"
    CHROME_BINARY_PATH: str = os.getenv("CHROME_BINARY_PATH", "")


settings = Settings()
