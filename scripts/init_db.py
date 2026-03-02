import asyncio
import asyncpg
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings


async def init_db():
    print(f"🔌 Connecting to database: {settings.DATABASE_URL}")
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        print("✅ Connected to database")

        # Read init.sql
        init_sql_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "init.sql")
        print(f"jq Reading init.sql from: {init_sql_path}")

        with open(init_sql_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        print("🚀 Executing initialization SQL...")
        await conn.execute(sql_content)
        print("✅ Database initialized successfully")

        await conn.close()

    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(init_db())
