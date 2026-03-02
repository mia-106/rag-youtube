import torch
import logging
import asyncio
from typing import List, Tuple, Optional
from src.core.config import settings

logger = logging.getLogger(__name__)

# 环境自适应：根据 RUN_MODE 决定使用本地模型还是 API
USE_PRODUCTION_MODE = settings.RUN_MODE == "production"

if USE_PRODUCTION_MODE:
    # 生产模式：使用 Cohere Rerank API
    try:
        from langchain_community.retrievers import ContextualCompressionRetriever
        from langchain_cohere import CohereRerank
        COHERE_AVAILABLE = True
    except ImportError:
        COHERE_AVAILABLE = False
        logger.warning("Cohere not installed, falling back to local reranker")
else:
    # 开发模式：使用本地 BGE Reranker
    from transformers import AutoModelForSequenceClassification, AutoTokenizer


class BGEReranker:
    """
    BAAI/bge-reranker-v2-m3 重排序器
    支持 fp16 和 自动设备选择 (CUDA/CPU)
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BGEReranker, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.model_name = settings.RERANKER_MODEL
        self.device = self._get_device()
        self.use_fp16 = self.device.type == "cuda"

        logger.info(f"Initializing Reranker: {self.model_name} | Device: {self.device} | FP16: {self.use_fp16}")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name, torch_dtype=torch.float16 if self.use_fp16 else torch.float32, trust_remote_code=True
            )
            self.model.to(self.device)
            self.model.eval()
            self._initialized = True
            logger.info("Reranker model loaded successfully")
        except Exception as e:
            logger.error(f"Reranker model load failed: {e}")
            raise e

    def _get_device(self) -> torch.device:
        if torch.cuda.is_available():
            return torch.device("cuda")
        elif torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    def compute_score(self, query: str, documents: List[str], batch_size: int = 8) -> List[float]:
        """
        计算文档与查询的相关性分数
        """
        if not documents:
            return []

        all_scores = []
        pairs = [[query, doc] for doc in documents]

        try:
            # 批量处理
            for i in range(0, len(pairs), batch_size):
                batch_pairs = pairs[i : i + batch_size]

                with torch.no_grad():
                    inputs = self.tokenizer(
                        batch_pairs, padding=True, truncation=True, return_tensors="pt", max_length=512
                    )

                    inputs = {k: v.to(self.device) for k, v in inputs.items()}

                    scores = (
                        self.model(**inputs, return_dict=True)
                        .logits.view(
                            -1,
                        )
                        .float()
                    )
                    all_scores.extend(scores.cpu().numpy().tolist())

            return all_scores

        except Exception as e:
            logger.error(f"Rerank computation error: {e}")
            # 出错时返回默认低分避免阻断流程
            return [-10.0] * len(documents)

    def rerank(self, query: str, documents: List[str], top_k: int = 5) -> List[Tuple[int, float]]:
        """
        重排序并返回 (原始索引, 分数) 列表 (同步方法)
        """
        scores = self.compute_score(query, documents)

        # 创建 (index, score) 对
        ranked_results = []
        for i, score in enumerate(scores):
            ranked_results.append((i, score))

        # 按分数降序排序
        ranked_results.sort(key=lambda x: x[1], reverse=True)

        return ranked_results[:top_k]

    async def rerank_async(self, query: str, documents: List[str], top_k: int = 5) -> List[Tuple[int, float]]:
        """
        异步重排序 (运行在线程池中避免阻塞事件循环)
        """
        return await asyncio.to_thread(self.rerank, query, documents, top_k)
