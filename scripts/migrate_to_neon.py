"""
数据迁移脚本：将本地 Docker PostgreSQL 的数据迁移到 Neon
"""
import asyncio
import asyncpg
import os
from pathlib import Path

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
    print("开始数据迁移: 本地 Docker -> Neon")
    print("=" * 50)

    # 连接两个数据库
    print("\n[1/4] 连接本地数据库...")
    local_conn = await asyncpg.connect(LOCAL_DB_URL)
    print("✓ 本地数据库连接成功")

    print("\n[2/4] 连接 Neon 数据库...")
    neon_conn = await asyncpg.connect(NEON_DB_URL)
    print("✓ Neon 数据库连接成功")

    # 1. 迁移 channels 表
    print("\n[3/4] 迁移 channels 表...")
    channels = await local_conn.fetch("SELECT * FROM channels")
    if channels:
        for channel in channels:
            await neon_conn.execute("""
                INSERT INTO channels (id, channel_id, channel_name, description, subscriber_count, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (channel_id) DO NOTHING
            """, channel['id'], channel['channel_id'], channel['channel_name'],
                channel['description'], channel['subscriber_count'],
                channel['created_at'], channel['updated_at'])
        print(f"✓ 已迁移 {len(channels)} 个频道")
    else:
        print("  - channels 表为空，跳过")

    # 2. 迁移 videos 表
    print("\n迁移 videos 表...")
    videos = await local_conn.fetch("SELECT * FROM videos")
    if videos:
        for video in videos:
            await neon_conn.execute("""
                INSERT INTO videos (id, video_id, channel_id, title, description, duration,
                    view_count, like_count, published_at, content_hash, thumbnail_url, tags, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (video_id) DO NOTHING
            """, video['id'], video['video_id'], video['channel_id'], video['title'],
                video['description'], video['duration'], video['view_count'], video['like_count'],
                video['published_at'], video['content_hash'], video['thumbnail_url'],
                video['tags'], video['created_at'], video['updated_at'])
        print(f"✓ 已迁移 {len(videos)} 个视频")
    else:
        print("  - videos 表为空，跳过")

    # 3. 迁移 subtitle_chunks 表（核心！RAG 依赖这个）
    print("\n迁移 subtitle_chunks 表...")
    chunks = await local_conn.fetch("SELECT * FROM subtitle_chunks")
    if chunks:
        for chunk in chunks:
            await neon_conn.execute("""
                INSERT INTO subtitle_chunks (id, video_id, chunk_index, content, video_summary,
                    start_time, end_time, metadata, embedding, content_hash, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (content_hash) DO NOTHING
            """, chunk['id'], chunk['video_id'], chunk['chunk_index'], chunk['content'],
                chunk['video_summary'], chunk['start_time'], chunk['end_time'],
                chunk['metadata'], chunk['embedding'], chunk['content_hash'], chunk['created_at'])
        print(f"✓ 已迁移 {len(chunks)} 个字幕块")
    else:
        print("  - subtitle_chunks 表为空")

        # 如果数据库没有字幕块，尝试从本地文件导入
        print("\n[4/4] 从字幕文件导入数据...")
        await import_transcripts_from_files(neon_conn)

    # 关闭连接
    await local_conn.close()
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

        print(f"  ✓ {title}: {len(chunks)} 个块")

    print(f"\n✓ 从 {len(files)} 个文件导入完成")


if __name__ == "__main__":
    asyncio.run(migrate_data())
