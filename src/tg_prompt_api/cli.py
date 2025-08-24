import asyncio
import os
import typer
import uvicorn
import psycopg

from .config import settings
from .telegram_bot import dp, bot
from .db import get_conn
from .models import clean_on_boot
from .security import setup_secure_logging

app = typer.Typer(add_completion=False)


@app.command()
def run_api(host: str = "0.0.0.0", port: int = 8100):
    """Run FastAPI server."""
    # Fix Windows event loop policy for psycopg
    if os.name == 'nt':  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    uvicorn.run("tg_prompt_api.api:app", host=host, port=port, reload=False)


@app.command()
def run_bot():
    """Run Telegram long-polling bot."""
    
    # Fix Windows event loop policy for psycopg
    if os.name == 'nt':  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    async def _main():
        # Setup secure logging with token redaction
        setup_secure_logging()

        # ensure webhook mode is disabled and avoid processing stale backlog
        await bot.delete_webhook(drop_pending_updates=True)
        # optional: clean DB on boot
        if settings.CLEAN_ON_BOOT:
            async for aconn in get_conn():
                await clean_on_boot(aconn)
        # start polling and only request the updates we handle
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

    asyncio.run(_main())


@app.command()
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


@app.command()
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


@app.command()
def run_all():
    """Run API and Bot together (simple dev mode)."""
    import multiprocessing as mp

    p1 = mp.Process(target=run_api)
    p1.start()
    try:
        run_bot()
    finally:
        p1.terminate()


if __name__ == "__main__":
    app()
