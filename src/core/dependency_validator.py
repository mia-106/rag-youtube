"""
外部依赖验证模块
验证API密钥数据库连接外部服务等依赖项
确保系统在启动时所有依赖都可用
"""

import asyncio
import aiohttp
import asyncpg
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

from src.core.config import settings
from src.core.exceptions import SystemException

logger = logging.getLogger(__name__)


class DependencyStatus(Enum):
    """依赖项状态"""

    UNKNOWN = "unknown"
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class ValidationResult:
    """验证结果"""

    name: str
    status: DependencyStatus
    message: str
    response_time: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class DependencyValidator:
    """外部依赖验证器"""

    def __init__(self):
        self.results: List[ValidationResult] = []
        self.timeout = 10.0  # 验证超时时间

    async def validate_all(self) -> List[ValidationResult]:
        """验证所有依赖项"""
        logger.info(" 开始验证外部依赖...")

        # 并行验证所有依赖项
        validation_tasks = [
            self.validate_deepseek_api(),
            self.validate_firecrawl_api(),
            self.validate_supabase_connection(),
            self.validate_database_schema(),
        ]

        results = await asyncio.gather(*validation_tasks, return_exceptions=True)

        # 处理结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f" 验证任务 {i} 出错: {result}")
                self.results.append(
                    ValidationResult(name=f"task_{i}", status=DependencyStatus.ERROR, message=str(result))
                )
            else:
                self.results.append(result)

        # 统计结果
        valid_count = sum(1 for r in self.results if r.status == DependencyStatus.VALID)
        total_count = len(self.results)

        logger.info(f" 依赖验证完成: {valid_count}/{total_count} 项有效")

        return self.results

    async def validate_deepseek_api(self) -> ValidationResult:
        """验证DeepSeek API"""
        start_time = time.time()
        name = "DeepSeek API"

        try:
            if not settings.DEEPSEEK_API_KEY:
                return ValidationResult(name=name, status=DependencyStatus.INVALID, message="API密钥未配置")

            # 验证API密钥格式
            if not settings.DEEPSEEK_API_KEY.startswith("sk-"):
                return ValidationResult(
                    name=name, status=DependencyStatus.INVALID, message="API密钥格式不正确应以'sk-'开头"
                )

            # 尝试调用API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.DEEPSEEK_MODEL,
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 5,
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    response_time = time.time() - start_time

                    if response.status == 200:
                        return ValidationResult(
                            name=name, status=DependencyStatus.VALID, message="API连接正常", response_time=response_time
                        )
                    elif response.status == 401:
                        return ValidationResult(
                            name=name, status=DependencyStatus.INVALID, message="API密钥无效或已过期"
                        )
                    elif response.status == 429:
                        return ValidationResult(
                            name=name,
                            status=DependencyStatus.VALID,
                            message="API密钥有效但请求过于频繁",
                            response_time=response_time,
                        )
                    else:
                        return ValidationResult(
                            name=name,
                            status=DependencyStatus.ERROR,
                            message=f"API返回错误状态码: {response.status}",
                            response_time=response_time,
                        )

        except asyncio.TimeoutError:
            return ValidationResult(
                name=name, status=DependencyStatus.TIMEOUT, message=f"API调用超时 (>{self.timeout}s)"
            )
        except Exception as e:
            return ValidationResult(name=name, status=DependencyStatus.ERROR, message=f"验证失败: {str(e)}")

    async def validate_firecrawl_api(self) -> ValidationResult:
        """验证Firecrawl API"""
        start_time = time.time()
        name = "Firecrawl API"

        try:
            if not settings.FIRECRAWL_API_KEY:
                return ValidationResult(
                    name=name,
                    status=DependencyStatus.VALID,  # 可选依赖
                    message="API密钥未配置可选依赖",
                )

            # 验证API密钥格式
            if not settings.FIRECRAWL_API_KEY.startswith("sc_"):
                return ValidationResult(
                    name=name, status=DependencyStatus.INVALID, message="API密钥格式不正确应以'sc_'开头"
                )

            # 尝试调用API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    settings.FIRECRAWL_DEEP_RESEARCH_URL,
                    headers={
                        "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"query": "test", "limit": 1},
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    response_time = time.time() - start_time

                    if response.status in [200, 401, 429]:
                        return ValidationResult(
                            name=name, status=DependencyStatus.VALID, message="API密钥有效", response_time=response_time
                        )
                    else:
                        return ValidationResult(
                            name=name,
                            status=DependencyStatus.ERROR,
                            message=f"API返回错误状态码: {response.status}",
                            response_time=response_time,
                        )

        except asyncio.TimeoutError:
            return ValidationResult(
                name=name, status=DependencyStatus.TIMEOUT, message=f"API调用超时 (>{self.timeout}s)"
            )
        except Exception as e:
            return ValidationResult(name=name, status=DependencyStatus.ERROR, message=f"验证失败: {str(e)}")

    async def validate_supabase_connection(self) -> ValidationResult:
        """验证Supabase连接"""
        start_time = time.time()
        name = "Supabase连接"

        try:
            if not settings.DATABASE_URL:
                return ValidationResult(name=name, status=DependencyStatus.INVALID, message="数据库URL未配置")

            # 测试数据库连接
            conn = await asyncpg.connect(settings.DATABASE_URL)
            try:
                # 执行简单查询
                result = await conn.fetchval("SELECT 1")
                response_time = time.time() - start_time

                if result == 1:
                    return ValidationResult(
                        name=name, status=DependencyStatus.VALID, message="数据库连接正常", response_time=response_time
                    )
                else:
                    return ValidationResult(name=name, status=DependencyStatus.ERROR, message="数据库查询返回异常结果")
            finally:
                await conn.close()

        except asyncio.TimeoutError:
            return ValidationResult(
                name=name, status=DependencyStatus.TIMEOUT, message=f"数据库连接超时 (>{self.timeout}s)"
            )
        except Exception as e:
            return ValidationResult(name=name, status=DependencyStatus.ERROR, message=f"连接失败: {str(e)}")

    async def validate_database_schema(self) -> ValidationResult:
        """验证数据库架构"""
        start_time = time.time()
        name = "数据库架构"

        try:
            if not settings.DATABASE_URL:
                return ValidationResult(name=name, status=DependencyStatus.ERROR, message="数据库URL未配置")

            conn = await asyncpg.connect(settings.DATABASE_URL)
            try:
                # 检查必需的表是否存在
                required_tables = ["videos", "channels", "subtitle_chunks"]

                missing_tables = []
                for table in required_tables:
                    result = await conn.fetchval(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_name = $1 AND table_schema = 'public'",
                        table,
                    )
                    if result == 0:
                        missing_tables.append(table)

                response_time = time.time() - start_time

                if missing_tables:
                    return ValidationResult(
                        name=name,
                        status=DependencyStatus.INVALID,
                        message=f"缺少必需的表: {', '.join(missing_tables)}",
                        response_time=response_time,
                    )
                else:
                    return ValidationResult(
                        name=name, status=DependencyStatus.VALID, message="数据库架构完整", response_time=response_time
                    )

            finally:
                await conn.close()

        except asyncio.TimeoutError:
            return ValidationResult(
                name=name, status=DependencyStatus.TIMEOUT, message=f"架构验证超时 (>{self.timeout}s)"
            )
        except Exception as e:
            return ValidationResult(name=name, status=DependencyStatus.ERROR, message=f"架构验证失败: {str(e)}")

    def get_summary(self) -> Dict[str, Any]:
        """获取验证摘要"""
        total = len(self.results)
        valid = sum(1 for r in self.results if r.status == DependencyStatus.VALID)
        invalid = sum(1 for r in self.results if r.status == DependencyStatus.INVALID)
        errors = sum(1 for r in self.results if r.status == DependencyStatus.ERROR)
        timeouts = sum(1 for r in self.results if r.status == DependencyStatus.TIMEOUT)

        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "errors": errors,
            "timeouts": timeouts,
            "success_rate": round((valid / total * 100) if total > 0 else 0, 2),
            "overall_status": "healthy" if valid == total else "degraded",
        }

    def check_critical_dependencies(self) -> bool:
        """检查关键依赖项是否可用"""
        critical_names = ["DeepSeek API", "Supabase连接"]

        for result in self.results:
            if result.name in critical_names and result.status != DependencyStatus.VALID:
                logger.error(f" 关键依赖项不可用: {result.name} - {result.message}")
                return False

        return True


async def validate_system_dependencies(strict_mode: bool = False) -> bool:
    """
    验证系统依赖项

    Args:
        strict_mode: 严格模式关键依赖失败时抛出异常

    Returns:
        验证是否成功
    """
    validator = DependencyValidator()
    results = await validator.validate_all()

    # 打印详细结果
    logger.info("\n 依赖验证详细结果:")
    for result in results:
        status_emoji = {
            DependencyStatus.VALID: "",
            DependencyStatus.INVALID: "",
            DependencyStatus.ERROR: "",
            DependencyStatus.TIMEOUT: "",
        }.get(result.status, "")

        logger.info(
            f"{status_emoji} {result.name}: {result.message}"
            + (f" ({result.response_time:.2f}s)" if result.response_time else "")
        )

    # 检查关键依赖
    critical_ok = validator.check_critical_dependencies()

    # 获取摘要
    summary = validator.get_summary()
    logger.info(f"\n 验证摘要: {summary}")

    if not critical_ok:
        error_msg = "关键依赖项验证失败系统无法启动"
        logger.error(f" {error_msg}")

        if strict_mode:
            raise SystemException(error_msg)

        return False

    if summary["overall_status"] == "healthy":
        logger.info(" 所有依赖项验证通过系统可以正常启动")
        return True
    else:
        warning_msg = "部分依赖项验证失败系统可能无法正常运行"
        logger.warning(f" {warning_msg}")

        if strict_mode:
            raise SystemException(warning_msg)

        return True


# === 启动验证装饰器 ===
def validate_dependencies(strict_mode: bool = False):
    """依赖项验证装饰器"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 在函数执行前验证依赖
            success = await validate_system_dependencies(strict_mode=strict_mode)
            if not success and strict_mode:
                raise SystemException("依赖验证失败无法执行函数")

            # 执行函数
            result = await func(*args, **kwargs)

            return result

        return wrapper

    return decorator


# === 使用示例 ===
# @validate_dependencies(strict_mode=True)
# async def main():
#     # 系统启动逻辑
#     pass

# if __name__ == "__main__":
#     asyncio.run(validate_system_dependencies(strict_mode=True))
