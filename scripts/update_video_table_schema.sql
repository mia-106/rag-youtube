-- =====================================================
-- YouTube Agentic RAG - 数据库表结构更新脚本
-- =====================================================
-- 此脚本用于同步VideoMetadata模型与Supabase数据库表结构
-- 请在Supabase SQL Editor中运行此脚本
-- =====================================================

-- 添加channel_name字段到videos表
ALTER TABLE videos
ADD COLUMN IF NOT EXISTS channel_name TEXT;

-- 为现有记录设置默认值
UPDATE videos
SET channel_name = COALESCE(channel_name, 'Unknown Channel')
WHERE channel_name IS NULL;

-- 为channel_name字段添加注释
COMMENT ON COLUMN videos.channel_name IS 'YouTube频道名称';

-- 验证表结构
DO $$
BEGIN
    -- 检查videos表是否存在channel_name字段
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'videos'
        AND column_name = 'channel_name'
    ) THEN
        RAISE NOTICE '✅ 字段channel_name已成功添加到videos表';
    ELSE
        RAISE EXCEPTION '❌ 字段channel_name添加失败';
    END IF;
END $$;

-- 显示当前videos表结构
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'videos'
ORDER BY ordinal_position;

-- =====================================================
-- 执行完成提示
-- =====================================================
-- 运行以下命令验证更新：
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'videos';
-- =====================================================
