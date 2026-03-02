import asyncio
import json
import os
import sys
import glob
import logging
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings
from src.core.models import VideoMetadata, SubtitleChunk, Channel
from src.vector_storage.superabase_client import SuperabaseClient
from src.vector_storage.pgvector_handler import PGVectorHandler
from src.parsing.contextual_chunking import ContextualChunker
from src.ingestion.content_hasher import ContentHasher
from src.core.deepseek_client import DeepSeekClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Fix for Windows asyncio loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def parse_wire_magic_transcript(transcript_json: str) -> str:
    """Parse YouTube's wireMagic/pb3 JSON format (simplified)"""
    try:
        data = json.loads(transcript_json)
        text_parts = []

        if "events" in data:
            for event in data["events"]:
                if "segs" in event:
                    for seg in event["segs"]:
                        if "utf8" in seg:
                            text_parts.append(seg["utf8"])
        return "".join(text_parts)
    except Exception:
        # If it's not valid JSON or other error, return as is
        return transcript_json


def get_latest_crawl_file() -> Optional[str]:
    files = glob.glob("data/crawl_records_*.json")
    if not files:
        return None
    return max(files, key=os.path.getctime)


async def generate_video_summary(content: str, title: str, description: str) -> str:
    if not content or not content.strip():
        return (description or title or "")[:300]

    if not settings.DEEPSEEK_API_KEY:
        base = description or title or content[:300]
        return base[:300]

    client = DeepSeekClient()
    trimmed_content = content[:6000]
    prompt = (
        "请基于以下视频字幕生成一段约300字的中文摘要，要求信息密度高，"
        "不使用列表或项目符号，不添加来源标注，不要超过300字。\n\n"
        f"标题：{title}\n"
        f"已有描述：{description}\n\n"
        f"字幕：\n{trimmed_content}"
    )
    messages = [{"role": "user", "content": prompt}]
    try:
        summary = await asyncio.wait_for(
            client.generate_completion(messages, temperature=0.2, max_tokens=400, stream=False), timeout=30
        )
        summary = summary.strip()
        if len(summary) > 300:
            summary = summary[:300]
        return summary
    except asyncio.TimeoutError:
        logger.warning("⚠️ 摘要生成超时，回退到描述/标题")
        base = description or title or content[:300]
        return base[:300]
    except Exception as e:
        logger.warning(f"⚠️ 摘要生成失败，回退到描述/标题: {e}")
        base = description or title or content[:300]
        return base[:300]


async def process_video(
    video_data: Dict[str, Any], db_client: SuperabaseClient, vector_handler: PGVectorHandler, chunker: ContextualChunker
):
    """Process a single video: store metadata, chunk transcript, embed, and store chunks."""

    video_id = video_data.get("video_id")
    title = video_data.get("title", "Unknown Title")
    channel_id = video_data.get("channel_id", "")
    channel_name = video_data.get("channel_name", "Unknown Channel")

    logger.info(f"🎬 Processing video: {title} ({video_id})")

    # 0. Ensure Channel Exists
    if channel_id:
        channel = Channel(
            channel_id=channel_id,
            channel_name=channel_name,
            description=None,  # Not available in video metadata usually
            subscriber_count=None,
        )
        await db_client.store_channel(channel)

    # 1. Prepare VideoMetadata
    # Handle dates and types safely
    try:
        duration = int(video_data.get("duration", 0))
    except Exception:
        duration = 0

    try:
        view_count = int(video_data.get("view_count", 0))
    except Exception:
        view_count = 0

    try:
        like_count = int(video_data.get("like_count", 0))
    except Exception:
        like_count = 0

    video_meta = VideoMetadata(
        video_id=video_id,
        channel_id=video_data.get("channel_id", ""),
        channel_name=video_data.get("channel_name", ""),
        title=title,
        description=video_data.get("description", ""),
        duration=duration,
        view_count=view_count,
        like_count=like_count,
        upload_date=video_data.get("upload_date", ""),
        content_hash=video_data.get("content_hash", ContentHasher.generate_hash(title)),
        thumbnail_url=video_data.get("thumbnail_url", ""),
        webpage_url=video_data.get("webpage_url", ""),
        tags=video_data.get("tags", []),
        transcript=video_data.get("transcript", ""),  # Store raw transcript in video metadata if needed, or truncate
    )

    # 2. Store Video Metadata
    await db_client.store_video(video_meta)

    # 3. Process Transcript
    raw_transcript = video_data.get("transcript")
    if not raw_transcript:
        logger.warning(f"⚠️ No transcript for video {video_id}, skipping chunks.")
        return

    content = ""
    if isinstance(raw_transcript, str):
        if raw_transcript.strip().startswith("{") and '"wireMagic"' in raw_transcript:
            content = parse_wire_magic_transcript(raw_transcript)
        else:
            content = raw_transcript
    else:
        content = str(raw_transcript)

    if not content.strip():
        logger.warning(f"⚠️ Empty content for video {video_id}, skipping chunks.")
        return

    # 4. Chunk Transcript
    video_summary = await generate_video_summary(
        content=content, title=title, description=video_data.get("description", "")
    )

    # The ContextualChunker in src/parsing/contextual_chunking.py splits text
    # We need to manually construct SubtitleChunk objects

    logger.info(f"🧩 开始递归分块: {video_id}")
    try:
        text_chunks = chunker.chunk_text(content)
    except Exception as e:
        logger.error(f"❌ 分块失败: {e}")
        return
    # We could use chunker.add_overlap(text_chunks) but let's stick to basic chunks first or assume chunker handles it

    if not text_chunks:
        logger.warning(f"⚠️ No chunks generated for video {video_id}")
        return

    logger.info(f"📄 Generated {len(text_chunks)} chunks for video {video_id}")

    # 5. Generate Embeddings (Batch)
    # We will generate embeddings for the pure chunk content

    texts_to_embed = []
    chunk_objects = []

    for i, chunk_text in enumerate(text_chunks):
        # User Requirement:
        # 1. page_content (for vectorization): Only pure subtitle chunk content
        # 2. metadata: Store video_summary in Supabase

        # We DO NOT prepend video_summary to the text to be embedded or stored as content
        texts_to_embed.append(chunk_text)

        chunk_obj = SubtitleChunk(
            video_id=video_id,
            chunk_index=i,
            content=chunk_text,  # Pure content
            video_summary=video_summary,  # Stored separately
            content_hash=ContentHasher.generate_chunk_hash(chunk_text, video_summary),
            metadata={"source": "youtube_crawl"},
        )
        chunk_objects.append(chunk_obj)

    # Generate embeddings
    try:
        embeddings = await asyncio.wait_for(vector_handler.batch_create_embeddings(texts_to_embed), timeout=300)
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ Embedding batch timeout for {video_id}, falling back to smaller batches")
        embeddings = []
        batch_size = 8
        for start in range(0, len(texts_to_embed), batch_size):
            batch = texts_to_embed[start : start + batch_size]
            logger.info(
                f"🔁 Embedding fallback batch {start // batch_size + 1}/{(len(texts_to_embed) + batch_size - 1) // batch_size}"
            )
            try:
                batch_embeddings = await asyncio.wait_for(vector_handler.batch_create_embeddings(batch), timeout=120)
            except Exception as e:
                logger.error(f"❌ Failed to generate embeddings for {video_id} fallback batch: {e}")
                return
            embeddings.extend(batch_embeddings)
    except Exception as e:
        logger.error(f"❌ Failed to generate embeddings for {video_id}: {e}")
        return

    # Assign embeddings to chunks
    if len(embeddings) != len(chunk_objects):
        logger.error(f"❌ Mismatch in embeddings count: {len(embeddings)} vs {len(chunk_objects)}")
        return

    for chunk_obj, emb in zip(chunk_objects, embeddings):
        chunk_obj.embedding = emb

    # 6. Store Chunks
    await db_client.store_subtitle_chunks(chunk_objects)
    logger.info(f"✅ Stored {len(chunk_objects)} chunks for video {video_id}")


async def main():
    print("============================================================")
    print("YouTube Agentic RAG - Processing & Indexing")
    print("============================================================")

    # 1. Check Environment
    # if not settings.OPENAI_API_KEY:
    #     print("❌ Error: OPENAI_API_KEY is missing in .env")
    #     return
    if not settings.DATABASE_URL:
        print("❌ Error: DATABASE_URL is missing in .env")
        return

    # 2. Load Data
    data_file = get_latest_crawl_file()
    if not data_file:
        print("❌ No crawl records found in data/")
        return

    print(f"📂 Loading data from: {data_file}")
    with open(data_file, "r", encoding="utf-8") as f:
        videos_data = json.load(f)

    print(f"📊 Found {len(videos_data)} videos to process.")

    # 3. Initialize Components
    print("🔧 Initializing system components...")
    db_client = SuperabaseClient()
    vector_handler = PGVectorHandler()
    chunker = ContextualChunker(chunk_size=1000, overlap_size=200)

    await db_client.connect()

    # 🔧 Auto-update schema for correct vector dimensions
    try:
        async with db_client.pool.acquire() as conn:
            print(f"🔧 Updating vector dimensions to {settings.EMBEDDING_DIMENSIONS}...")
            # Ensure the vector extension is enabled (idempotent)
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # Try to alter the column type
            try:
                await conn.execute(
                    f"ALTER TABLE subtitle_chunks ALTER COLUMN embedding TYPE VECTOR({settings.EMBEDDING_DIMENSIONS});"
                )
                print("✅ Schema dimensions updated successfully.")
            except Exception as e:
                # If alter fails (likely due to dimension mismatch with existing data), we need to clear data
                print(f"⚠️ Alter column failed ({e})...")
                print("⚠️ Dimension mismatch detected. Clearing existing subtitle chunks to allow schema update...")
                # Truncate chunks table
                await conn.execute("TRUNCATE TABLE subtitle_chunks CASCADE;")
                # Retry alter
                await conn.execute(
                    f"ALTER TABLE subtitle_chunks ALTER COLUMN embedding TYPE VECTOR({settings.EMBEDDING_DIMENSIONS});"
                )
                print("✅ Schema dimensions updated successfully (after truncate).")

            # Also update retrieval_logs if it exists
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS retrieval_logs (id UUID PRIMARY KEY, query_vector VECTOR(1536));"
            )
            try:
                await conn.execute(
                    f"ALTER TABLE retrieval_logs ALTER COLUMN query_vector TYPE VECTOR({settings.EMBEDDING_DIMENSIONS});"
                )
            except Exception:
                # Truncate logs if needed
                await conn.execute("TRUNCATE TABLE retrieval_logs;")
                await conn.execute(
                    f"ALTER TABLE retrieval_logs ALTER COLUMN query_vector TYPE VECTOR({settings.EMBEDDING_DIMENSIONS});"
                )

            print("✅ Retrieval logs schema updated.")
    except Exception as e:
        print(f"ℹ️ Schema update note: {e}")

    # Initialize vector handler (checks OpenAI connection)
    await vector_handler.initialize()

    # 4. Process Videos
    print("🚀 Starting processing...")
    success_count = 0

    for i, video_data in enumerate(videos_data):
        print(f"\n[{i + 1}/{len(videos_data)}] Processing: {video_data.get('title', 'Unknown')[:50]}...")
        try:
            await process_video(video_data, db_client, vector_handler, chunker)
            success_count += 1
        except Exception as e:
            logger.error(f"❌ Error processing video {video_data.get('video_id')}: {e}")

    # 5. Finalize
    await db_client.disconnect()

    print("\n============================================================")
    print("✅ Processing Complete!")
    print(f"Successful: {success_count}/{len(videos_data)}")
    print("============================================================")


if __name__ == "__main__":
    asyncio.run(main())
