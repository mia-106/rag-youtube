"""
检查 Neon 数据库数据
"""
import asyncio
import asyncpg
import os
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

NEON_DB_URL = os.environ.get("DATABASE_URL", "")

async def check_data():
    conn = await asyncpg.connect(NEON_DB_URL)

    # 检查频道
    channels = await conn.fetch("SELECT * FROM channels")
    print(f"Channels: {len(channels)}")
    for c in channels:
        print(f"  - {c['channel_name']} ({c['channel_id']})")

    # 检查视频
    videos = await conn.fetch("SELECT * FROM videos")
    print(f"\nVideos: {len(videos)}")
    for v in videos[:5]:
        print(f"  - {v['title']}")

    # 检查字幕块
    chunks = await conn.fetch("SELECT COUNT(*) as cnt FROM subtitle_chunks")
    print(f"\nSubtitle chunks: {chunks[0]['cnt']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_data())
