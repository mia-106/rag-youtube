import asyncio
import asyncpg
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.core.config import settings


async def list_tables():
    print(f"Connecting to {settings.DATABASE_URL}...")
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)

        # List all tables in public schema
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)

        print("\n--- Tables Found ---")
        if not tables:
            print("No tables found in public schema.")

        for table in tables:
            t_name = table["table_name"]
            try:
                count = await conn.fetchval(f"SELECT count(*) FROM {t_name}")
                print(f"Table: {t_name:<25} Rows: {count}")
            except Exception as e:
                print(f"Table: {t_name:<25} Error counting rows: {e}")

        await conn.close()

    except Exception as e:
        print(f"Error connecting to database: {e}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(list_tables())
