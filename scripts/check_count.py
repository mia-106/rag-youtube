import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from src.core.config import settings


async def main():
    if not settings.DATABASE_URL:
        print("Error: DATABASE_URL not set")
        return

    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        count = await conn.fetchval("SELECT COUNT(*) FROM subtitle_chunks")
        print(f"Total subtitle chunks: {count}")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
