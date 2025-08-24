import os
import psycopg

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:postAdmin@localhost:5432/tg_prompt_api"
)
if DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg", "postgresql")

DDL = open(os.path.join(os.path.dirname(__file__), "init_db.sql"), "r", encoding="utf-8").read()

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS prompt_options CASCADE;")
        cur.execute("DROP TABLE IF EXISTS prompts CASCADE;")
        conn.commit()
        cur.execute(DDL)
        conn.commit()
        print("Database wiped and recreated.")
