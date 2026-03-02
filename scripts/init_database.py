"""
数据库初始化脚本
创建数据库表和索引
"""

import asyncio
import asyncpg
import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent

# 解决 Windows 上 asyncio SelectorEventLoop 的问题
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables():
    """创建数据库表"""
    try:
        sys.path.append(str(project_root))
        from src.core.config import settings

        # 连接数据库
        # 移除 ssl=True，因为 connection_lost() 错误通常与 SSL 握手或 asyncio 事件循环有关
        # 尝试显式设置 command_timeout
        conn = await asyncpg.connect(settings.DATABASE_URL, command_timeout=60)
        logger.info("Database connection successful")

        # 读取初始化脚本
        init_script_path = project_root / "init.sql"
        with open(init_script_path, "r", encoding="utf-8") as f:
            init_script = f.read()

        # 执行初始化脚本
        await conn.execute(init_script)
        logger.info("Database tables created successfully")

        # 创建 agent_insights 表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_insights (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                content TEXT NOT NULL,
                topic TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("agent_insights table created successfully")

        await conn.close()

    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise


async def create_vector_index():
    """创建向量索引"""
    try:
        sys.path.append(str(project_root))
        from src.core.config import settings

        conn = await asyncpg.connect(settings.DATABASE_URL)

        # 创建向量索引 (需要先插入一些数据)
        index_script = """
            -- 创建向量索引 (使用IVFFlat算法)
            -- 注意: 需要先在subtitle_chunks表中插入一些数据
            DO $$
            BEGIN
                IF (SELECT COUNT(*) FROM subtitle_chunks) > 0 THEN
                    CREATE INDEX IF NOT EXISTS idx_subtitle_chunks_embedding
                    ON subtitle_chunks USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                    RAISE NOTICE '向量索引创建成功';
                ELSE
                    RAISE NOTICE 'subtitle_chunks表为空，跳过索引创建';
                END IF;
            END $$;
        """

        await conn.execute(index_script)
        logger.info("Vector index created successfully")

        await conn.close()

    except Exception as e:
        logger.error(f"Vector index creation failed: {str(e)}")
        raise


async def verify_database():
    """验证数据库结构"""
    try:
        sys.path.append(str(project_root))
        from src.core.config import settings

        conn = await asyncpg.connect(settings.DATABASE_URL)

        # 检查表是否存在
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        table_names = [row["table_name"] for row in tables]

        logger.info(f"Database tables: {', '.join(table_names)}")

        # 检查扩展
        extensions = await conn.fetch("""
            SELECT extname
            FROM pg_extension
        """)
        ext_names = [row["extname"] for row in extensions]

        logger.info(f"Database extensions: {', '.join(ext_names)}")

        await conn.close()

        return True

    except Exception as e:
        logger.error(f"Database verification failed: {str(e)}")
        return False


async def main():
    """主函数"""
    sys.path.append(str(project_root))
    from src.core.config import settings

    print("\n" + "=" * 60)
    print("Database Initialization Script")
    print("=" * 60 + "\n")

    # 检查数据库URL
    if not settings.DATABASE_URL:
        print("DATABASE_URL not configured")
        print("请在 .env 文件中配置数据库连接字符串")
        return

    print(f"Database URL: {settings.DATABASE_URL}")
    print()

    try:
        # 1. 创建表
        print("Step 1: Creating database tables...")
        await create_tables()
        print()

        # 2. 创建向量索引
        print("Step 2: Creating vector index...")
        await create_vector_index()
        print()

        # 3. 验证数据库
        print("Step 3: Verifying database structure...")
        is_valid = await verify_database()
        print()

        if is_valid:
            print("=" * 60)
            print("Database initialization complete!")
            print("=" * 60)
        else:
            print("Database verification failed")

    except Exception as e:
        print(f"\nInitialization failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
