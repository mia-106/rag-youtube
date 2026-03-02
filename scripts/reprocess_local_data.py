import asyncio
import sys
import os
import json
import logging

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from sibling script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try to import from process_and_index, handling potential import errors
try:
    from process_and_index import process_video
except ImportError:
    # If direct import fails, try to import as module if possible, or define dummy
    print("Could not import process_video from process_and_index.py")
    sys.exit(1)

from src.vector_storage.superabase_client import SuperabaseClient
from src.vector_storage.pgvector_handler import PGVectorHandler
from src.parsing.contextual_chunking import ContextualChunker

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    target_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "crawl_records_20260210_234728.json"
    )

    if not os.path.exists(target_file):
        logger.error(f"Target file not found: {target_file}")
        return

    logger.info(f"📂 Loading data from: {target_file}")
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            video_data_list = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON: {e}")
        return

    logger.info(f"📊 Found {len(video_data_list)} videos.")

    # Init components
    db_client = SuperabaseClient()
    await db_client.connect()

    vector_handler = PGVectorHandler()
    await vector_handler.initialize()

    chunker = ContextualChunker(chunk_size=1000, overlap_size=200)

    try:
        for video_data in video_data_list:
            video_id = video_data.get("video_id")
            if video_id:
                try:
                    logger.info(f"🧹 Pre-clearance: Removing existing chunks for {video_id}...")
                    await db_client.delete_video_chunks(video_id)
                except Exception as e:
                    logger.warning(f"Failed to clear existing chunks for {video_id}: {e}")

            await process_video(video_data, db_client, vector_handler, chunker)
    finally:
        await db_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
