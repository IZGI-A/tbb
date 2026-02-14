from clickhouse_driver import Client
from config import settings


def get_clickhouse_client() -> Client:
    return Client(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        database=settings.CLICKHOUSE_DB,
        user=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
    )
