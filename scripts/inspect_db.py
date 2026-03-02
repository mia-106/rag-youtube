import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vector_storage.superabase_client import SuperabaseClient


async def main():
    print("🔍 Inspecting Database...")
    client = SuperabaseClient()
    try:
        await client.connect()
        print("✅ Database connected successfully")

        async with client.pool.acquire() as conn:
            # Check tables
            print("\n📊 Checking 'videos' table:")
            try:
                count = await conn.fetchval("SELECT COUNT(*) FROM videos")
                print(f"   - Count: {count}")
                rows = await conn.fetch("SELECT * FROM videos LIMIT 1")
                # Handle potentially non-serializable data for printing
                safe_rows = []
                for row in rows:
                    r_dict = dict(row)
                    # Convert datetime to string for display
                    for k, v in r_dict.items():
                        if hasattr(v, "isoformat"):
                            r_dict[k] = v.isoformat()
                    safe_rows.append(r_dict)
                print(f"   - Sample: {safe_rows}")
            except Exception as e:
                print(f"   ❌ Error checking videos: {e}")

            print("\n📊 Checking 'subtitle_chunks' table:")
            try:
                count = await conn.fetchval("SELECT COUNT(*) FROM subtitle_chunks")
                print(f"   - Count: {count}")
                rows = await conn.fetch("SELECT * FROM subtitle_chunks LIMIT 1")
                safe_rows = []
                for row in rows:
                    r_dict = dict(row)
                    for k, v in r_dict.items():
                        if hasattr(v, "isoformat"):
                            r_dict[k] = v.isoformat()
                    safe_rows.append(r_dict)
                print(f"   - Sample: {safe_rows}")
            except Exception as e:
                print(f"   ❌ Error checking subtitle_chunks: {e}")

    except Exception as e:
        print(f"❌ Failed to connect or query database: {e}")
    finally:
        if client.pool:
            await client.pool.close()


if __name__ == "__main__":
    asyncio.run(main())
