import asyncio
import os
import sys
import subprocess

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vector_storage.superabase_client import SuperabaseClient


async def reset_db():
    print("🗑️ Resetting Database (Truncating Tables)...")
    # Initialize client with default settings
    client = SuperabaseClient()
    await client.connect()

    try:
        async with client.pool.acquire() as conn:
            # Truncate tables
            # Order matters due to foreign keys if they exist, though CASCADE handles it
            tables = ["subtitle_chunks", "videos", "channels", "retrieval_logs"]
            for table in tables:
                print(f"   - Truncating {table}...")
                await conn.execute(f"TRUNCATE TABLE {table} CASCADE;")
            print("✅ Database Reset Complete.")
    except Exception as e:
        print(f"❌ Database Reset Failed: {e}")
    finally:
        await client.disconnect()


def run_crawl():
    print("\n🕷️ Starting Crawl for @dankoetalks (limit 20)...")
    # URL for @dankoetalks
    url = "https://www.youtube.com/@dankoetalks"
    cmd = [sys.executable, "scripts/crawl_channel.py", url]

    try:
        subprocess.run(cmd, check=True)
        print("✅ Crawl Complete.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Crawl Failed: {e}")
        sys.exit(1)


def run_ingestion():
    print("\n⚙️ Starting Ingestion...")
    cmd = [sys.executable, "scripts/process_and_index.py"]
    try:
        subprocess.run(cmd, check=True)
        print("✅ Ingestion Complete.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ingestion Failed: {e}")
        sys.exit(1)


async def main():
    print("🚀 Starting RAG System Reset & Enhancement...")

    # 1. Reset DB
    await reset_db()

    # 2. Re-crawl
    run_crawl()

    # 3. Process & Index
    run_ingestion()

    print("\n✨ All tasks completed successfully! RAG System is ready.")


if __name__ == "__main__":
    asyncio.run(main())
