import asyncio
import os
import typer
import uvicorn
import psycopg

from .config import settings
from .telegram_bot import get_bot, manual_polling
from .db import get_conn
from .models import clean_on_boot
from .security import setup_secure_logging

app = typer.Typer(add_completion=False)


def _run_api_wrapper():
    """Wrapper to ensure proper event loop policy in subprocess."""
    if os.name == 'nt':  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    run_api()


@app.command("run_api")
def run_api(host: str = "0.0.0.0", port: int = 8100):
    """Run FastAPI server."""
    # Fix Windows event loop policy for psycopg
    if os.name == 'nt':  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    uvicorn.run("tg_prompt_api.api:app", host=host, port=port, reload=False)


@app.command("run_bot")
def run_bot():
    """Run Telegram long-polling bot."""
    
    # Fix Windows event loop policy for psycopg
    if os.name == 'nt':  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    async def _main():
        # Setup secure logging with token redaction
        setup_secure_logging()

        # Get bot and dispatcher instances
        bot, dp = get_bot()
        
        # ensure webhook mode is disabled and avoid processing stale backlog
        await bot.delete_webhook(drop_pending_updates=True)
        # optional: clean DB on boot
        if settings.CLEAN_ON_BOOT:
            async for aconn in get_conn():
                await clean_on_boot(aconn)
        # start manual polling to avoid aiogram's internal conflicts on Windows
        await manual_polling(bot, dp)

    asyncio.run(_main())


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


@app.command("run_all")
def run_all():
    """Run API and Bot together (simple dev mode)."""
    import multiprocessing as mp
    
    # Fix Windows event loop policy for psycopg in main process
    if os.name == 'nt':  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # Set multiprocessing start method for Windows compatibility
        mp.set_start_method('spawn', force=True)

    p1 = mp.Process(target=_run_api_wrapper)
    p1.start()
    try:
        run_bot()
    except KeyboardInterrupt:
        typer.echo("\nShutting down services...")
    finally:
        p1.terminate()
        p1.join(timeout=5)  # Wait up to 5 seconds for clean shutdown
        if p1.is_alive():
            typer.echo("Force killing API process...")
            p1.kill()


if __name__ == "__main__":
    app()
