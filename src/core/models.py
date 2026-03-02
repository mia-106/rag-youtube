"""
数据模型定义合并版
定义系统中使用的核心数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class AgentStatus(Enum):
    """Agent执行状态"""

    PENDING = "pending"
    THINKING = "thinking"
    RETRIEVING = "retrieving"
    EVALUATING = "evaluating"
    REFLECTING = "reflecting"
    ANSWERING = "answering"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Channel:
    """频道数据模型"""

    channel_id: str
    channel_name: str
    description: Optional[str] = None
    subscriber_count: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class VideoMetadata:
    """视频元数据模型"""

    video_id: str
    channel_id: str
    title: str
    description: Optional[str] = None
    duration: Optional[int] = None  # 秒
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    published_at: Optional[datetime] = None
    upload_date: Optional[str] = None  # yt-dlp返回的上传日期YYYYMMDD格式
    channel_name: Optional[str] = None  # 频道名称
    content_hash: str = ""
    thumbnail_url: Optional[str] = None
    webpage_url: Optional[str] = None  # 视频页面URL
    tags: List[str] = field(default_factory=list)
    transcript: Optional[str] = None  # 视频字幕文本
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class SubtitleChunk:
    """字幕分块模型"""

    video_id: str
    chunk_index: int
    content: str  # IBM Dockling解析的Markdown
    video_summary: str  # 上下文增强: 视频摘要
    start_time: Optional[int] = None  # 开始时间(秒)
    end_time: Optional[int] = None  # 结束时间(秒)
    content_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None  # 向量嵌入
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SearchResult:
    """搜索结果模型"""

    chunk_id: str
    video_id: str
    title: str
    content: str
    score: float
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """Agent状态模型完整版"""

    # 基本信息
    question: str
    session_id: str
    status: AgentStatus = AgentStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 思考阶段
    query_strategy: Optional[str] = None
    original_query: Optional[str] = None
    optimized_queries: List[str] = field(default_factory=list)
    current_query: Optional[str] = None

    # 检索阶段
    retrieval_results: List[Dict[str, Any]] = field(default_factory=list)
    retrieval_metadata: Dict[str, Any] = field(default_factory=dict)

    # 评估阶段
    evaluation_score: float = 0.0
    evaluation_details: Dict[str, Any] = field(default_factory=dict)
    sufficient: bool = False
    evaluation_feedback: Optional[str] = None

    # 反思阶段
    reflection_count: int = 0
    max_reflections: int = 3
    reflection_notes: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)

    # 回答阶段
    final_answer: Optional[str] = None
    confidence_score: float = 0.0
    answer_metadata: Dict[str, Any] = field(default_factory=dict)

    # 性能指标
    total_time: float = 0.0
    retrieval_time: float = 0.0
    thinking_time: float = 0.0
    evaluation_time: float = 0.0

    # 错误信息
    error_message: Optional[str] = None
    error_stack: Optional[str] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        state_dict = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                state_dict[key] = value.isoformat()
            elif isinstance(value, Enum):
                state_dict[key] = value.value
            else:
                state_dict[key] = value
        return state_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        """从字典创建实例"""
        # 处理枚举类型
        if "status" in data and isinstance(data["status"], str):
            data["status"] = AgentStatus(data["status"])

        # 处理datetime类型
        for field_name in ["created_at", "updated_at"]:
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])

        return cls(**data)


@dataclass
class RetrievalLog:
    """检索日志模型"""

    query_text: str
    query_vector: Optional[List[float]] = None
    retrieved_chunks: List[Dict[str, Any]] = field(default_factory=list)
    reranked_chunks: List[Dict[str, Any]] = field(default_factory=list)
    final_answer: Optional[str] = None
    context_precision: Optional[float] = None
    faithfulness_score: Optional[float] = None
    retrieval_time: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceMetric:
    """性能指标模型"""

    response_time: float
    retrieval_latency: float
    token_count: int
    memory_usage: float
    cpu_usage: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class QualityMetrics:
    """质量指标模型"""

    context_precision: float
    faithfulness_score: float
    answer_relevance: float
    context_recall: float
    overall_score: float
    timestamp: datetime = field(default_factory=datetime.now)


# 枚举类型定义
class SearchType:
    """搜索类型"""

    VECTOR = "vector"
    BM25 = "bm25"
    HYBRID = "hybrid"
    RERANKED = "reranked"


class ErrorType:
    """错误类型"""

    API_ERROR = "api_error"
    DATABASE_ERROR = "database_error"
    PARSING_ERROR = "parsing_error"
    VALIDATION_ERROR = "validation_error"
    WORKFLOW_ERROR = "workflow_error"


# 工具函数
def to_dict(obj) -> Dict[str, Any]:
    """将数据类转换为字典"""
    if hasattr(obj, "__dataclass_fields__"):
        return {field.name: getattr(obj, field.name) for field in obj.__dataclass_fields__.values()}
    return obj.__dict__


def from_dict(data: Dict[str, Any], cls):
    """从字典创建数据类实例"""
    return cls(**data)


def test_models():
    """测试数据模型"""
    # 测试VideoMetadata
    video = VideoMetadata(
        video_id="test123", channel_id="channel456", title="测试视频", description="这是一个测试视频", duration=300
    )
    assert video.video_id == "test123"
    print(" VideoMetadata模型测试通过")

    # 测试SubtitleChunk
    chunk = SubtitleChunk(video_id="test123", chunk_index=0, content="这是第一段内容", video_summary="测试视频摘要")
    assert chunk.video_id == "test123"
    print(" SubtitleChunk模型测试通过")

    # 测试AgentState
    state = AgentState(question="什么是Python")
    assert state.question == "什么是Python"
    print(" AgentState模型测试通过")

    print(" 所有数据模型测试通过")


if __name__ == "__main__":
    test_models()
