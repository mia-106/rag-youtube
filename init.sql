-- YouTube Agentic RAG系统数据库初始化脚本
-- PostgreSQL + PGVector扩展

-- 启用PGVector扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 启用全文搜索
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 创建频道表
CREATE TABLE IF NOT EXISTS channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id VARCHAR UNIQUE NOT NULL,
    channel_name VARCHAR NOT NULL,
    description TEXT,
    subscriber_count BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建视频元数据表
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id VARCHAR UNIQUE NOT NULL,
    channel_id VARCHAR REFERENCES channels(channel_id),
    title VARCHAR NOT NULL,
    description TEXT,
    duration INTEGER,
    view_count BIGINT,
    like_count BIGINT,
    published_at TIMESTAMP,
    content_hash VARCHAR UNIQUE NOT NULL,
    thumbnail_url TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建字幕分块表 (使用PGVector)
CREATE TABLE IF NOT EXISTS subtitle_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id VARCHAR REFERENCES videos(video_id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    video_summary TEXT,
    start_time INTEGER,
    end_time INTEGER,
    metadata JSONB,
    embedding VECTOR(1024),  -- PGVector存储嵌入向量
    content_hash VARCHAR UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建检索日志表
CREATE TABLE IF NOT EXISTS retrieval_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text TEXT NOT NULL,
    query_vector VECTOR(1024),
    retrieved_chunks JSONB,
    reranked_chunks JSONB,
    final_answer TEXT,
    context_precision FLOAT,
    faithfulness_score FLOAT,
    retrieval_time FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引

-- 频道表索引
CREATE INDEX IF NOT EXISTS idx_channels_channel_id ON channels(channel_id);

-- 视频表索引
CREATE INDEX IF NOT EXISTS idx_videos_video_id ON videos(video_id);
CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id);
CREATE INDEX IF NOT EXISTS idx_videos_content_hash ON videos(content_hash);
CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at DESC);

-- 全文搜索索引
CREATE INDEX IF NOT EXISTS idx_videos_title_search ON videos USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_videos_description_search ON videos USING gin(to_tsvector('english', description));

-- 字幕分块表索引
CREATE INDEX IF NOT EXISTS idx_subtitle_chunks_video_id ON subtitle_chunks(video_id);
CREATE INDEX IF NOT EXISTS idx_subtitle_chunks_content_hash ON subtitle_chunks(content_hash);

-- PGVector相似度搜索索引 (使用IVFFlat算法)
-- 注意: 需要先插入一些数据才能创建索引
-- CREATE INDEX IF NOT EXISTS idx_subtitle_chunks_embedding ON subtitle_chunks
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 检索日志表索引
CREATE INDEX IF NOT EXISTS idx_retrieval_logs_created_at ON retrieval_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retrieval_logs_query_text ON retrieval_logs USING gin(to_tsvector('english', query_text));

-- 创建触发器函数 - 自动更新updated_at字段
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为需要的表添加触发器
CREATE TRIGGER update_channels_updated_at BEFORE UPDATE ON channels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 创建视图 - 视频统计信息
CREATE OR REPLACE VIEW video_statistics AS
SELECT
    c.channel_id,
    c.channel_name,
    COUNT(v.video_id) as total_videos,
    SUM(v.view_count) as total_views,
    AVG(v.duration) as avg_duration,
    MAX(v.published_at) as latest_video_date
FROM channels c
LEFT JOIN videos v ON c.channel_id = v.channel_id
GROUP BY c.channel_id, c.channel_name;

-- 创建视图 - 分块统计信息
CREATE OR REPLACE VIEW chunk_statistics AS
SELECT
    v.video_id,
    v.title,
    COUNT(sc.id) as total_chunks,
    AVG(LENGTH(sc.content)) as avg_chunk_length
FROM videos v
LEFT JOIN subtitle_chunks sc ON v.video_id = sc.video_id
GROUP BY v.video_id, v.title;

-- 插入示例数据 (仅用于测试)
-- 注意: 实际生产环境中应删除或修改这些数据

-- 插入示例频道
INSERT INTO channels (channel_id, channel_name, description, subscriber_count)
VALUES
    ('UC_test_channel_1', 'Python编程教程', '专注于Python编程教学', 100000),
    ('UC_test_channel_2', 'AI技术分享', '分享最新的人工智能技术', 50000)
ON CONFLICT (channel_id) DO NOTHING;

-- 插入示例视频
INSERT INTO videos (video_id, channel_id, title, description, duration, view_count, content_hash)
VALUES
    ('video_test_1', 'UC_test_channel_1', 'Python基础教程', '学习Python编程的基础知识', 3600, 50000, 'hash_python_basics'),
    ('video_test_2', 'UC_test_channel_1', 'Python进阶教程', 'Python高级特性讲解', 5400, 30000, 'hash_python_advanced'),
    ('video_test_3', 'UC_test_channel_2', 'AI入门指南', '人工智能基础概念介绍', 4500, 40000, 'hash_ai_intro')
ON CONFLICT (video_id) DO NOTHING;

-- 创建用户和权限 (可选)
-- CREATE USER youtube_rag_user WITH PASSWORD 'youtube_rag_password';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO youtube_rag_user;

-- 输出初始化完成信息
DO $$
BEGIN
    RAISE NOTICE 'YouTube Agentic RAG数据库初始化完成！';
    RAISE NOTICE '已创建表: channels, videos, subtitle_chunks, retrieval_logs';
    RAISE NOTICE '已启用扩展: vector, uuid-ossp, pg_trgm';
    RAISE NOTICE '请在插入数据后创建向量索引';
END $$;