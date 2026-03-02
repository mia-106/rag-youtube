# Agentic RAG系统 - 核心配置

from typing import Optional
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """系统核心配置"""

    # 运行模式: development (本地) / production (云端)
    RUN_MODE: str = "development"

    # API配置
    FIRECRAWL_API_KEY: str = ""
    FIRECRAWL_DEEP_RESEARCH_URL: str = "https://api.firecrawl.dev/v1/deep-search"
    TAVILY_API_KEY: str = ""

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # 数据库配置
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    DATABASE_URL: str = ""

    # 向量数据库配置
    OPENAI_API_KEY: Optional[str] = None

    # Embedding 配置
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSIONS: int = 1024
    # 生产模式使用的 API Embedding
    EMBEDDING_PROVIDER: str = "cohere"  # "cohere" or "openai"

    # 重排序配置
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANK_TOP_K: int = 5
    COHERE_API_KEY: str = ""
    COHERE_MODEL: str = "rerank-english-v3.0"

    # LangSmith配置
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "youtube-agentic-rag"

    # 系统配置
    LOG_LEVEL: str = "INFO"
    MAX_RETRIES: int = 3
    BATCH_SIZE: int = 100

    # 检索配置
    VECTOR_SEARCH_LIMIT: int = 100
    HYBRID_SEARCH_TOP_K: int = 10
    RERANK_TOP_K: int = 5

    # 性能配置
    CACHE_TTL: int = 3600  # 1小时
    MAX_CONCURRENT_REQUESTS: int = 10

    # Hugging Face配置 (允许额外字段)
    HF_HOME: Optional[str] = None
    HF_ENDPOINT: Optional[str] = None

    # 文件路径
    DATA_DIR: Path = Path("./data")
    CACHE_DIR: Path = Path("./cache")
    LOGS_DIR: Path = Path("./logs")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._create_directories()

    def _create_directories(self):
        """创建必要的目录"""
        for directory in [self.DATA_DIR, self.CACHE_DIR, self.LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

    def validate(self) -> bool:
        """验证配置是否完整"""
        required_fields = ["FIRECRAWL_API_KEY", "DEEPSEEK_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]

        missing_fields = []
        for field in required_fields:
            if not getattr(self, field):
                missing_fields.append(field)

        if missing_fields:
            print(f" 缺少必需的配置: {', '.join(missing_fields)}")
            return False

        print(" 配置验证通过")
        return True


# 全局配置实例
settings = Settings()


# 代理人配置注册表
AGENT_CONFIGS = {
    "dan_koe": {
        "full_name": "Dan Koe",
        "search_domains": ["x.com", "youtube.com", "substack.com", "thedankoe.com", "medium.com", "github.com"],
        "core_philosophy": "Systems thinking and one-person businesses",
    },
    "naval": {
        "full_name": "Naval Ravikant",
        "search_domains": ["x.com", "naval.com", "youtube.com", "medium.com", "github.com", "substack.com"],
        "core_philosophy": "Specific knowledge, leverage, and wealth creation",
    },
}
