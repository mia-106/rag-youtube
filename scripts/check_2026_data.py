import asyncio
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings
from src.vector_storage.superabase_client import SuperabaseClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_data():
    client = SuperabaseClient(settings.DATABASE_URL)
    await client.connect()

    # Check total chunks
    count = await client.pool.fetchval("SELECT COUNT(*) FROM subtitle_chunks")
    print(f"📊 Total subtitle chunks: {count}")

    # Check specific video title
    rows = await client.pool.fetch("SELECT video_id, title FROM videos WHERE title ILIKE '%2026%'")
    if rows:
        print("\nFound videos matching '2026':")
        for row in rows:
            print(f"- {row['title']} ({row['video_id']})")

            # Check chunks for this video
            chunk_count = await client.pool.fetchval(
                "SELECT COUNT(*) FROM subtitle_chunks WHERE video_id = $1", row["video_id"]
            )
            print(f"  Chunks: {chunk_count}")

            # Check embedding dimension
            emb_row = await client.pool.fetchrow(
                "SELECT embedding FROM subtitle_chunks WHERE video_id = $1 LIMIT 1", row["video_id"]
            )
            if emb_row and emb_row["embedding"]:
                # pgvector returns a string like "[0.1, 0.2, ...]"
                emb_str = emb_row["embedding"]
                # parse manually or count commas
                dim = emb_str.count(",") + 1
                print(f"  Embedding Dimension: {dim}")
            else:
                print("  No embedding found")
    else:
        print("\n❌ No videos found matching '2026'")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_data())
