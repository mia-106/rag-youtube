"""
Core interfaces for the YouTube Agentic RAG system
Abstract interfaces for database, API, and storage operations
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator


class IAsyncClient(ABC):
    """Base interface for async clients"""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the service"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the service"""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if client is healthy"""
        pass


class IDatabaseClient(IAsyncClient):
    """Database client interface"""

    @abstractmethod
    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a database query"""
        pass

    @abstractmethod
    async def fetch_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        pass

    @abstractmethod
    async def fetch_many(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch multiple rows"""
        pass

    @abstractmethod
    async def fetch_val(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Fetch a single value"""
        pass

    @abstractmethod
    async def begin_transaction(self) -> None:
        """Begin a database transaction"""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction"""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current transaction"""
        pass


class IAPIClient(IAsyncClient):
    """API client interface"""

    @abstractmethod
    async def call(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make an API call"""
        pass

    @abstractmethod
    async def stream(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """Make a streaming API call"""
        pass

    @abstractmethod
    async def generate_completion(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4000
    ) -> str:
        """Generate text completion"""
        pass


class IVectorStore(IAsyncClient):
    """Vector storage interface"""

    @abstractmethod
    async def insert_vectors(self, vectors: List[Dict[str, Any]]) -> bool:
        """Insert vectors into the store"""
        pass

    @abstractmethod
    async def search_similar(
        self, query_vector: List[float], limit: int = 10, threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors"""
        pass

    @abstractmethod
    async def create_index(self, dimension: int) -> bool:
        """Create vector index"""
        pass

    @abstractmethod
    async def drop_index(self) -> bool:
        """Drop vector index"""
        pass


class ICache(ABC):
    """Cache interface"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set a value in cache"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from cache"""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists"""
        pass


class ILogger(ABC):
    """Logger interface"""

    @abstractmethod
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message"""
        pass

    @abstractmethod
    def info(self, message: str, **kwargs) -> None:
        """Log info message"""
        pass

    @abstractmethod
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message"""
        pass

    @abstractmethod
    def error(self, message: str, **kwargs) -> None:
        """Log error message"""
        pass

    @abstractmethod
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message"""
        pass


class IConfigProvider(ABC):
    """Configuration provider interface"""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate configuration"""
        pass


class IEmbeddingsProvider(ABC):
    """Embeddings provider interface"""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text"""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts"""
        pass


class IQueue(ABC):
    """Queue interface"""

    @abstractmethod
    async def enqueue(self, item: Any) -> bool:
        """Add item to queue"""
        pass

    @abstractmethod
    async def dequeue(self) -> Optional[Any]:
        """Remove and return item from queue"""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get queue size"""
        pass

    @abstractmethod
    async def empty(self) -> bool:
        """Check if queue is empty"""
        pass


class IMetricsCollector(ABC):
    """Metrics collector interface"""

    @abstractmethod
    def record_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a counter metric"""
        pass

    @abstractmethod
    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a gauge metric"""
        pass

    @abstractmethod
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram metric"""
        pass


class IHealthCheck(ABC):
    """Health check interface"""

    @abstractmethod
    async def check(self) -> Dict[str, Any]:
        """Perform health check"""
        pass
