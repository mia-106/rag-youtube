"""
统一异常处理模块
定义系统中所有异常的层次结构和错误处理策略
"""

from typing import Optional, Dict, Any
import logging
import traceback
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """错误严重程度"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误类别"""

    VALIDATION = "validation"
    NETWORK = "network"
    DATABASE = "database"
    API = "api"
    SYSTEM = "system"
    SECURITY = "security"
    CONFIGURATION = "configuration"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class BaseAppException(Exception):
    """应用程序基础异常类"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.cause = cause
        self.timestamp = None  # 将在初始化时设置

    def __str__(self) -> str:
        base_msg = f"[{self.error_code}] {self.message}"
        if self.details:
            base_msg += f" | Details: {self.details}"
        return base_msg

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
            "timestamp": self.timestamp,
        }

    def log_error(self, logger_instance: Optional[logging.Logger] = None):
        """记录错误日志"""
        log = logger_instance or logger

        log_levels = {
            ErrorSeverity.LOW: logging.DEBUG,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }

        level = log_levels.get(self.severity, logging.ERROR)

        log.log(
            level,
            f"异常详情: {self}\n堆栈跟踪:\n{''.join(traceback.format_exception(type(self), self, self.__traceback__))}",
        )


# === 网络相关异常 ===
class NetworkException(BaseAppException):
    """网络相关异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.NETWORK, **kwargs)


class ConnectionTimeoutException(NetworkException):
    """连接超时异常"""

    def __init__(self, message: str = "连接超时", **kwargs):
        super().__init__(message, severity=ErrorSeverity.MEDIUM, **kwargs)


class ConnectionErrorException(NetworkException):
    """连接错误异常"""

    def __init__(self, message: str = "连接错误", **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)


class RateLimitException(NetworkException):
    """速率限制异常"""

    def __init__(self, message: str = "请求过于频繁", **kwargs):
        super().__init__(message, category=ErrorCategory.RATE_LIMIT, severity=ErrorSeverity.LOW, **kwargs)


# === 数据库相关异常 ===
class DatabaseException(BaseAppException):
    """数据库相关异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.DATABASE, **kwargs)


class ConnectionPoolException(DatabaseException):
    """连接池异常"""

    def __init__(self, message: str = "连接池错误", **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)


class QueryException(DatabaseException):
    """查询异常"""

    def __init__(self, message: str = "查询执行失败", **kwargs):
        super().__init__(message, severity=ErrorSeverity.MEDIUM, **kwargs)


# === API相关异常 ===
class APIException(BaseAppException):
    """API相关异常"""

    def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(message, category=ErrorCategory.API, **kwargs)
        self.status_code = status_code


class APIKeyException(APIException):
    """API密钥异常"""

    def __init__(self, message: str = "API密钥无效或缺失", **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)


class APITimeoutException(APIException):
    """API超时异常"""

    def __init__(self, message: str = "API调用超时", **kwargs):
        super().__init__(message, category=ErrorCategory.TIMEOUT, severity=ErrorSeverity.MEDIUM, **kwargs)


# === 验证相关异常 ===
class ValidationException(BaseAppException):
    """验证相关异常"""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, category=ErrorCategory.VALIDATION, severity=ErrorSeverity.LOW, **kwargs)
        self.field = field


class InputValidationException(ValidationException):
    """输入验证异常"""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, field, severity=ErrorSeverity.LOW, **kwargs)


# === 安全相关异常 ===
class SecurityException(BaseAppException):
    """安全相关异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.SECURITY, severity=ErrorSeverity.CRITICAL, **kwargs)


class SQLInjectionException(SecurityException):
    """SQL注入异常"""

    def __init__(self, message: str = "检测到SQL注入攻击", **kwargs):
        super().__init__(message, severity=ErrorSeverity.CRITICAL, **kwargs)


class AuthenticationException(SecurityException):
    """认证异常"""

    def __init__(self, message: str = "认证失败", **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)


# === 配置相关异常 ===
class ConfigurationException(BaseAppException):
    """配置相关异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.CONFIGURATION, severity=ErrorSeverity.HIGH, **kwargs)


class MissingConfigurationException(ConfigurationException):
    """缺失配置异常"""

    def __init__(self, message: str = "缺少必需的配置", **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)


# === 系统异常 ===
class SystemException(BaseAppException):
    """系统异常"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.SYSTEM, severity=ErrorSeverity.CRITICAL, **kwargs)


class ResourceExhaustionException(SystemException):
    """资源耗尽异常"""

    def __init__(self, message: str = "系统资源不足", **kwargs):
        super().__init__(message, severity=ErrorSeverity.CRITICAL, **kwargs)


# === 错误处理工具函数 ===
def handle_exception(
    exception: Exception,
    context: Optional[str] = None,
    logger_instance: Optional[logging.Logger] = None,
    reraise: bool = True,
) -> Optional[BaseAppException]:
    """
    统一异常处理函数

    Args:
        exception: 原始异常
        context: 异常上下文
        logger_instance: 日志记录器
        reraise: 是否重新抛出异常

    Returns:
        处理后的异常如果需要
    """
    log = logger_instance or logger
    context_info = f" | Context: {context}" if context else ""

    # 如果是已知异常类型直接处理
    if isinstance(exception, BaseAppException):
        exception.log_error(log)
        if reraise:
            raise exception
        return exception

    # 处理未知异常
    log.error(f"未处理的异常{context_info}: {type(exception).__name__}: {str(exception)}\n{traceback.format_exc()}")

    # 转换为系统异常
    system_exception = SystemException(
        message=f"系统内部错误: {str(exception)}",
        details={"original_exception": type(exception).__name__, "context": context},
        cause=exception,
    )

    system_exception.log_error(log)

    if reraise:
        raise system_exception

    return system_exception


def safe_execute(
    func,
    *args,
    default_return=None,
    exception_types: tuple = (Exception,),
    context: Optional[str] = None,
    logger_instance: Optional[logging.Logger] = None,
    **kwargs,
):
    """
    安全执行函数

    Args:
        func: 要执行的函数
        *args: 函数参数
        default_return: 默认返回值
        exception_types: 要捕获的异常类型
        context: 异常上下文
        logger_instance: 日志记录器
        **kwargs: 函数关键字参数

    Returns:
        函数执行结果或默认值
    """
    try:
        return func(*args, **kwargs)
    except exception_types as e:
        handle_exception(
            e, context=context or f"safe_execute({func.__name__})", logger_instance=logger_instance, reraise=False
        )
        return default_return


# === 异常装饰器 ===
def exception_handler(
    reraise: bool = True,
    exception_types: tuple = (Exception,),
    context: Optional[str] = None,
    logger_instance: Optional[logging.Logger] = None,
):
    """
    异常处理装饰器

    Args:
        reraise: 是否重新抛出异常
        exception_types: 要捕获的异常类型
        context: 异常上下文
        logger_instance: 日志记录器
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                handle_exception(
                    e,
                    context=context or f"{func.__module__}.{func.__name__}",
                    logger_instance=logger_instance,
                    reraise=reraise,
                )
            return None

        return wrapper

    return decorator
