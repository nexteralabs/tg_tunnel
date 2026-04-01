from typing import Any, AsyncIterator
import psycopg
from psycopg.rows import dict_row
from .config import settings


async def connect() -> psycopg.AsyncConnection:
    dsn = str(settings.DATABASE_URL)
    if dsn.startswith("postgresql+psycopg"):
        dsn = dsn.replace("postgresql+psycopg", "postgresql")
    return await psycopg.AsyncConnection.connect(dsn, row_factory=dict_row)


async def get_conn() -> AsyncIterator[psycopg.AsyncConnection]:
    async with await connect() as aconn:
        yield aconn


async def fetchone(aconn: psycopg.AsyncConnection, sql: str, *params: Any) -> dict | None:
    async with aconn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def fetchall(aconn: psycopg.AsyncConnection, sql: str, *params: Any) -> list[dict]:
    async with aconn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall() or []


async def execute(aconn: psycopg.AsyncConnection, sql: str, *params: Any) -> None:
    async with aconn.cursor() as cur:
        await cur.execute(sql, params)
        await aconn.commit()
