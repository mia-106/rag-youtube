import asyncio
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vector_storage.superabase_client import SuperabaseClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_chat_history():
    logger.info("Initializing chat history table...")

    client = SuperabaseClient()
    await client.connect()

    try:
        # Read SQL file
        sql_path = os.path.join(os.path.dirname(__file__), "create_chat_history.sql")
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        async with client.pool.acquire() as conn:
            await conn.execute(sql_content)

        logger.info("Chat history table created successfully!")

    except Exception as e:
        logger.error(f"Failed to create chat history table: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(init_chat_history())
