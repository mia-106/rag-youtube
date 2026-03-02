# Agentic RAG系统 - 常量定义

from enum import Enum


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SearchWeights:
    """混合搜索权重配置"""

    VECTOR_WEIGHT = 0.7
    BM25_WEIGHT = 0.2
    RECENCY_WEIGHT = 0.1


class AgentState:
    """Agent状态常量"""

    THINKING = "thinking"
    RETRIEVING = "retrieving"
    EVALUATING = "evaluating"
    REFLECTING = "reflecting"
    ANSWERING = "answering"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoMetadata:
    """视频元数据字段"""

    VIDEO_ID = "video_id"
    CHANNEL_ID = "channel_id"
    TITLE = "title"
    DESCRIPTION = "description"
    DURATION = "duration"
    VIEW_COUNT = "view_count"
    LIKE_COUNT = "like_count"
    PUBLISHED_AT = "published_at"
    CONTENT_HASH = "content_hash"


class DatabaseTables:
    """数据库表名"""

    CHANNELS = "channels"
    VIDEOS = "videos"
    SUBTITLE_CHUNKS = "subtitle_chunks"
    RETRIEVAL_LOGS = "retrieval_logs"


class APIEndpoints:
    """API端点"""

    FIRECRAWL_DEEP_SEARCH = "/v1/deep-search"
    DEEPSEEK_CHAT = "/v1/chat/completions"
    COHERE_RERANK = "/v1/rerank"


class VectorConfig:
    """向量配置"""

    DIMENSIONS = 1536
    SIMILARITY_THRESHOLD = 0.8
    MAX_RESULTS = 100


class PerformanceThresholds:
    """性能阈值"""

    MAX_RESPONSE_TIME = 5.0  # 秒
    MIN_CONTEXT_PRECISION = 0.85
    MIN_FAITHFULNESS = 0.90
    MAX_RETRIEVAL_LATENCY = 0.2  # 秒


class ErrorMessages:
    """错误消息"""

    INVALID_API_KEY = "无效的API密钥"
    DATABASE_CONNECTION_FAILED = "数据库连接失败"
    RETRIEVAL_FAILED = "检索失败"
    INVALID_CONFIGURATION = "配置无效"
    WORKFLOW_FAILED = "工作流执行失败"


class SuccessMessages:
    """成功消息"""

    CONFIG_LOADED = "配置加载成功"
    DATABASE_CONNECTED = "数据库连接成功"
    WORKFLOW_COMPLETED = "工作流执行完成"
    RETRIEVAL_SUCCESSFUL = "检索成功"
    EVALUATION_COMPLETED = "评估完成"


# 视频支持格式
SUPPORTED_SUBTITLE_FORMATS = [".srt", ".vtt", ".ass", ".ssa"]

# 嵌入模型映射
EMBEDDING_MODELS = {"text-embedding-3-large": 3072, "text-embedding-3-small": 1536, "text-embedding-ada-002": 1536}

# 重排序模型配置
RERANK_MODELS = {
    "rerank-english-v3.0": {"max_tokens": 512, "truncate": "END"},
    "rerank-multilingual-v3.0": {"max_tokens": 512, "truncate": "END"},
}

# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = """你是一个专业的YouTube视频分析助手专门基于已解析的视频内容回答用户问题

回答准则
1. 只基于提供的上下文信息回答不要添加外部知识
2. 如果上下文信息不足明确说明无法回答
3. 引用具体的视频和时间戳
4. 保持准确简洁有帮助的回答风格
5. 对于不确定的信息使用"可能""似乎"等表达

上下文信息
{context}

用户问题{question}

请根据上下文信息回答问题"""

# JSON输出格式模板
JSON_RESPONSE_TEMPLATE = {
    "answer": "文本答案",
    "confidence": 0.0,
    "source_videos": [{"video_id": "视频ID", "title": "视频标题", "timestamp": "时间戳", "relevance_score": 0.0}],
    "metadata": {"retrieval_time": 0.0, "total_chunks": 0, "agent_reflections": []},
}
