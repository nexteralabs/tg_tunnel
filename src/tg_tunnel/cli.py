import asyncio
import os
import typer
import uvicorn
import psycopg

from .core.config import settings
from .core.event_loop import set_event_loop_policy

# Removed old bot polling imports - now handled by channel system
from .core.db import get_conn

app = typer.Typer(add_completion=False)


# REMOVED: _run_api_wrapper (no longer needed)


@app.command("run_api")
def run_api(host: str = "127.0.0.1", port: int = 8100):
    """Run FastAPI server."""
    set_event_loop_policy()
    uvicorn.run("tg_tunnel.api.app:app", host=host, port=port, reload=False)


# REMOVED: run_bot command
# The default bot is now handled by the channel system (__system_prompt__ channel)
# All polling is managed by the API process via channel poller


@app.command("init_db")
def init_db():
    """Create DB schema (runs scripts/init_db.sql)."""
    sql_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "init_db.sql")
    sql_path = os.path.abspath(sql_path)
    dsn = str(settings.DATABASE_URL)
    if dsn.startswith("postgresql+psycopg"):
        dsn = dsn.replace("postgresql+psycopg", "postgresql")
    with open(sql_path, "r", encoding="utf-8") as f:
        ddl = f.read()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
            conn.commit()
            typer.echo("DB initialized.")


@app.command("fresh_start")
def fresh_start():
    """Drop & recreate tables, clearing failed test data."""
    from pathlib import Path

    sql_path = Path(__file__).parent.parent.parent / "scripts" / "init_db.sql"
    dsn = str(settings.DATABASE_URL)
    if dsn.startswith("postgresql+psycopg"):
        dsn = dsn.replace("postgresql+psycopg", "postgresql")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS prompt_options CASCADE;")
            cur.execute("DROP TABLE IF EXISTS prompts CASCADE;")
            conn.commit()
            cur.execute(sql_path.read_text(encoding="utf-8"))
            conn.commit()
            typer.echo("Fresh start complete.")


@app.command("init_channels")
def init_channels():
    """Create channels table for Telegram Channel Gateway"""
    sql_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "add_channels.sql")
    sql_path = os.path.abspath(sql_path)
    dsn = str(settings.DATABASE_URL)
    if dsn.startswith("postgresql+psycopg"):
        dsn = dsn.replace("postgresql+psycopg", "postgresql")
    with open(sql_path, "r", encoding="utf-8") as f:
        ddl = f.read()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
            conn.commit()
            typer.echo("Channels table created.")


@app.command("list_channels")
def list_channels_cmd():
    """List registered channels"""
    set_event_loop_policy()

    async def _list():
        from .services.channels.models import list_active_channels

        channels: list[dict] = []
        async for conn in get_conn():
            channels = await list_active_channels(conn)

        if not channels:
            typer.echo("No active channels.")
        else:
            for ch in channels:
                typer.echo(f"- {ch['channel_id']} -> {ch['telegram_chat_id']}")

    asyncio.run(_list())


# REMOVED: run_all command
# No longer needed - just use `run_api` which now handles all polling
# (including the default bot via __system_prompt__ channel)


if __name__ == "__main__":
    app()
