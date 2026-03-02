import asyncio
import asyncpg
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings


async def reset_db():
    if not settings.DATABASE_URL:
        print("❌ DATABASE_URL 未配置")
        return

    conn = await asyncpg.connect(settings.DATABASE_URL)
    await conn.execute("TRUNCATE TABLE subtitle_chunks, videos, channels, retrieval_logs CASCADE;")

    sequences = await conn.fetch(
        """
        SELECT sequence_schema, sequence_name
        FROM information_schema.sequences
        WHERE sequence_schema = 'public';
        """
    )
    for seq in sequences:
        schema = seq["sequence_schema"]
        name = seq["sequence_name"]
        await conn.execute(f'ALTER SEQUENCE "{schema}"."{name}" RESTART WITH 1;')

    await conn.close()
    print("✅ 数据库已清空并重置序列")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(reset_db())
