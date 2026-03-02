import asyncio
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def generate_wisdom_snapshot():
    """
    Scan existing video summaries and generate a 'Dan Koe Core Wisdom Graph'.
    Save it to the agent_insights table.
    """
    project_root = Path(__file__).parent.parent
    sys.path.append(str(project_root))

    from src.agent.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage
    from src.core.config import settings
    import asyncpg

    logger.info("🚀 Starting Wisdom Snapshot Generation...")

    # 0. Ensure agent_insights table exists
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_insights (
                id SERIAL PRIMARY KEY,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await conn.close()
    except Exception as e:
        logger.error(f"❌ Failed to create table: {e}")
        return

    # 1. Retrieve all video summaries from the database
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)

        # Check if videos table exists (using correct table name now)
        table_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'videos')"
        )
        if not table_exists:
            logger.warning("⚠️ Table 'videos' does not exist. Please ingest videos first.")
            await conn.close()
            return

        # Query using JOIN between videos and subtitle_chunks
        # We use DISTINCT ON to get only one summary per video
        query = """
            SELECT DISTINCT ON (v.video_id)
                v.title as video_title,
                s.video_summary
            FROM videos v
            JOIN subtitle_chunks s ON v.video_id = s.video_id
            WHERE s.video_summary IS NOT NULL AND s.video_summary != ''
            ORDER BY v.video_id, s.chunk_index
        """
        rows = await conn.fetch(query)
        await conn.close()

        if not rows:
            logger.warning("⚠️ No video summaries found in database.")
            return

        logger.info(f"📚 Found {len(rows)} videos. Synthesizing wisdom...")

        # Prepare context
        context_text = ""
        for row in rows:
            context_text += f"Title: {row['video_title']}\nSummary: {row['video_summary']}\n\n"

    except Exception as e:
        logger.error(f"❌ Failed to fetch data: {e}")
        return

    # 2. Generate Wisdom Graph using LLM
    # Use the centralized LLM factory (DeepSeek)
    llm = get_llm(temperature=0.3)

    prompt = f"""
    You are the "Digital Soul" of Dan Koe. 
    Analyze the following summaries of your past content (videos/newsletters).
    
    Task:
    Distill a "Core Wisdom Graph" (Logic Map) of your philosophy.
    This text will be used as the immutable "Long-term Memory" for your AI Agent.
    
    Requirements:
    1. **Length**: Approximately 2000 words (in Chinese, but keep key English terms).
    2. **Structure**:
       - **Core Philosophy**: The One-Person Business, Focus, Entropy, The Good Life.
       - **Key Frameworks**: The 4-Hour Workday, Deep Work, Value Creation.
       - **Worldview**: Modern society as a distraction engine, the need for clarity.
       - **Actionable Principles**: How to execute.
    3. **Tone**: Deep, philosophical, yet actionable. Minimalist.
    
    Input Content:
    {context_text[:50000]} # Limit to avoid context overflow if too large
    
    Output the full wisdom graph text.
    """

    messages = [SystemMessage(content="You are Dan Koe."), HumanMessage(content=prompt)]

    try:
        logger.info("🧠 LLM is thinking... (This may take a minute)")
        response = await llm.ainvoke(messages)
        wisdom_content = response.content

        logger.info("✅ Wisdom Snapshot generated.")

        # 3. Save to Supabase (agent_insights table)
        conn = await asyncpg.connect(settings.DATABASE_URL)

        # Ensure table exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_insights (
                id SERIAL PRIMARY KEY,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Clear old snapshot (assuming single source of truth for now)
        await conn.execute("DELETE FROM agent_insights WHERE topic = 'dan_koe_wisdom_graph'")

        await conn.execute(
            "INSERT INTO agent_insights (topic, content) VALUES ($1, $2)", "dan_koe_wisdom_graph", wisdom_content
        )
        await conn.close()
        logger.info("💾 Wisdom Snapshot saved to database.")

    except Exception as e:
        logger.error(f"❌ Failed to generate/save wisdom: {e}")


if __name__ == "__main__":
    asyncio.run(generate_wisdom_snapshot())

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(generate_wisdom_snapshot())
