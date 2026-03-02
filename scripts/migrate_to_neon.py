"""
数据迁移脚本：将本地 Docker PostgreSQL 的数据迁移到 Neon
"""
import asyncio
import asyncpg
import os
import sys
from pathlib import Path

# Fix Unicode for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 本地 Docker 数据库配置
LOCAL_DB_URL = "postgresql://postgres:postgres@localhost:5432/youtube_rag"

# Neon 数据库配置（从环境变量）
NEON_DB_URL = os.environ.get("DATABASE_URL", "")

# 字幕文件目录
TRANSCRIPTS_DIR = Path("data/transcripts")

async def migrate_data():
    if not NEON_DB_URL:
        print("错误: 请设置 DATABASE_URL 环境变量")
        print("例如: export DATABASE_URL='postgresql://...neon.tech...'")
        return

    print("=" * 50)
    print("开始数据迁移: 本地文件 -> Neon")
    print("=" * 50)

    # 连接 Neon 数据库
    print("\n[1/3] 连接 Neon 数据库...")
    neon_conn = await asyncpg.connect(NEON_DB_URL, timeout=30)
    print("[OK] Neon 数据库连接成功")

    # 直接从字幕文件导入
    print("\n[2/3] 从字幕文件导入数据...")
    await import_transcripts_from_files(neon_conn)

    # 关闭连接
    await neon_conn.close()

    print("\n" + "=" * 50)
    print("数据迁移完成！")
    print("=" * 50)


async def import_transcripts_from_files(conn):
    """从本地字幕文件导入数据到 Neon"""
    import hashlib
    from datetime import datetime

    transcripts_dir = Path(TRANSCRIPTS_DIR)
    if not transcripts_dir.exists():
        print(f"错误: 字幕目录不存在: {transcripts_dir}")
        return

    files = list(transcripts_dir.glob("*.txt"))
    print(f"找到 {len(files)} 个字幕文件")

    # 插入频道（Dan Koe）
    channel_id = "UCJKix6EhgR-Z3sMt-aKk3qA"
    await conn.execute("""
        INSERT INTO channels (channel_id, channel_name, description, subscriber_count)
        VALUES ($1, 'Dan Koe', 'Dan Koe - Modern Wisdom', 500000)
        ON CONFLICT (channel_id) DO NOTHING
    """, channel_id)

    for i, file in enumerate(files):
        # 从文件名提取视频标题（去掉 .txt）
        title = file.stem

        # 生成 video_id
        video_id = f"video_{i+1:03d}"

        # 读取字幕内容
        content = file.read_text(encoding='utf-8')

        # 生成 content_hash
        content_hash = hashlib.md5(content.encode()).hexdigest()

        # 插入视频
        await conn.execute("""
            INSERT INTO videos (video_id, channel_id, title, content_hash)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (video_id) DO NOTHING
        """, video_id, channel_id, title, content_hash)

        # 将字幕内容分成小块
        chunk_size = 1000  # 每个块约 1000 字符
        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]

        for idx, chunk_text in enumerate(chunks):
            chunk_hash = hashlib.md5(f"{content_hash}_{idx}".encode()).hexdigest()

            await conn.execute("""
                INSERT INTO subtitle_chunks (video_id, chunk_index, content, content_hash)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (content_hash) DO NOTHING
            """, video_id, idx, chunk_text, chunk_hash)

        print(f"  [OK] {title}: {len(chunks)} 个块")

    print(f"\n[OK] 从 {len(files)} 个文件导入完成")


if __name__ == "__main__":
    asyncio.run(migrate_data())
