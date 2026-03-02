"""
Security Middleware
Provides middleware for request security, authentication, and authorization
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from dataclasses import dataclass

from src.security.validation import InputValidator, ValidationResult, ValidationSeverity
from src.security.utils import RateLimiter, get_security_manager
from src.security.auth import User, get_auth_manager

logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Security configuration"""

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # Input validation
    input_validation_enabled: bool = True
    strict_validation: bool = True

    # Authentication
    require_auth: bool = False
    session_timeout: int = 24  # hours

    # CSRF protection
    csrf_protection_enabled: bool = True

    # Security headers
    security_headers_enabled: bool = True

    # Logging
    log_security_events: bool = True
    log_level: str = "WARNING"


class SecurityEvent:
    """Security event for logging"""

    def __init__(self, event_type: str, message: str, severity: str, details: Optional[Dict[str, Any]] = None):
        self.timestamp = datetime.now()
        self.event_type = event_type
        self.message = message
        self.severity = severity
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.event_type,
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
        }


class SecurityLogger:
    """Security event logger"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.logger = logging.getLogger("security")
        self._setup_logger()

    def _setup_logger(self):
        """Setup logger"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - SECURITY - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(getattr(logging, self.config.log_level))

    def log_event(self, event: SecurityEvent):
        """Log security event"""
        if not self.config.log_security_events:
            return

        log_message = f"[{event.event_type}] {event.message}"
        if event.details:
            log_message += f" | Details: {event.details}"

        if event.severity == "CRITICAL":
            self.logger.critical(log_message)
        elif event.severity == "ERROR":
            self.logger.error(log_message)
        elif event.severity == "WARNING":
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)


class SecurityMiddleware:
    """Security middleware for requests"""

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()
        self.rate_limiter = RateLimiter(self.config.rate_limit_requests, self.config.rate_limit_window)
        self.input_validator = InputValidator()
        self.auth_manager = get_auth_manager()
        self.security_manager = get_security_manager()
        self.security_logger = SecurityLogger(self.config)

        # Setup default validators
        self._setup_validators()

    def _setup_validators(self):
        """Setup input validators"""
        from src.security.validation import (
            StringValidator,
            EmailValidator,
        )

        # Common validators
        self.input_validator.add_rule("email", EmailValidator(required=False))
        self.input_validator.add_rule(
            "username", StringValidator(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
        )
        self.input_validator.add_rule(
            "query",
            StringValidator(min_length=1, max_length=500, forbidden_chars=["<", ">", "{", "}", "\\", "^", "~", "`"]),
        )

    async def __call__(self, request: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process request through security middleware

        Args:
            request: Request data
            context: Additional context

        Returns:
            Processed request with security metadata
        """
        context = context or {}

        # Rate limiting
        if self.config.rate_limit_enabled:
            client_id = self._get_client_id(request)
            if not await self._check_rate_limit(client_id):
                self._log_security_event(
                    "RATE_LIMIT_EXCEEDED", f"Rate limit exceeded for client: {client_id}", "WARNING"
                )
                raise Exception("Rate limit exceeded")

        # Input validation
        if self.config.input_validation_enabled:
            validation_results = await self._validate_input(request)
            context["validation_results"] = validation_results

            if not self._is_validation_valid(validation_results):
                self._log_security_event(
                    "VALIDATION_FAILED",
                    "Input validation failed",
                    "WARNING",
                    {"validation_results": validation_results},
                )
                raise Exception("Input validation failed")

        # Authentication
        user = None
        if self.config.require_auth:
            user = await self._authenticate_request(request)
            if not user:
                self._log_security_event("AUTHENTICATION_FAILED", "Authentication required but failed", "WARNING")
                raise Exception("Authentication required")
            context["user"] = user

        # Add security metadata to request
        request["__security__"] = {
            "timestamp": datetime.now(),
            "client_id": self._get_client_id(request),
            "user": user,
            "context": context,
        }

        return request

    def _get_client_id(self, request: Dict[str, Any]) -> str:
        """Extract client ID from request"""
        # Try different sources
        if "client_ip" in request:
            return request["client_ip"]
        if "user_id" in request:
            return request["user_id"]
        if "session_id" in request:
            return request["session_id"]
        return "unknown"

    async def _check_rate_limit(self, client_id: str) -> bool:
        """Check rate limit for client"""
        return self.rate_limiter.is_allowed(client_id)

    async def _validate_input(self, request: Dict[str, Any]) -> Dict[str, List[ValidationResult]]:
        """Validate request input"""
        # Extract data from request
        data = {}
        if "data" in request:
            data = request["data"]
        elif "params" in request:
            data = request["params"]
        elif isinstance(request, dict):
            # Exclude internal fields
            data = {k: v for k, v in request.items() if not k.startswith("_")}

        return self.input_validator.validate(data)

    def _is_validation_valid(self, results: Dict[str, List[ValidationResult]]) -> bool:
        """Check if validation results are valid"""
        for field, field_results in results.items():
            for result in field_results:
                if not result.is_valid and result.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
                    return False
        return True

    async def _authenticate_request(self, request: Dict[str, Any]) -> Optional[User]:
        """Authenticate request"""
        # Try different authentication methods
        # 1. Session token
        if "session_token" in request:
            session = await self.auth_manager.get_session(request["session_token"])
            if session and not session.is_expired():
                user = await self.auth_manager.user_store.get_user(session.user_id)
                if user and user.is_active:
                    return user

        # 2. JWT token
        if "auth_token" in request:
            try:
                payload = self.security_manager.verify_jwt_token(request["auth_token"])
                user_id = payload.get("user_id")
                if user_id:
                    return await self.auth_manager.user_store.get_user(user_id)
            except Exception as e:
                logger.debug(f"JWT authentication failed: {e}")

        return None

    def _log_security_event(
        self, event_type: str, message: str, severity: str, details: Optional[Dict[str, Any]] = None
    ):
        """Log security event"""
        event = SecurityEvent(event_type, message, severity, details)
        self.security_logger.log_event(event)

    def add_validation_rule(self, field_name: str, rule):
        """Add custom validation rule"""
        self.input_validator.add_rule(field_name, rule)


# Security headers
class SecurityHeaders:
    """Security HTTP headers"""

    @staticmethod
    def get_headers() -> Dict[str, str]:
        """Get security headers"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        }


# Global middleware instance
_middleware = None


def get_security_middleware() -> SecurityMiddleware:
    """Get global security middleware instance"""
    global _middleware
    if _middleware is None:
        _middleware = SecurityMiddleware()
    return _middleware


# Decorators
def secure_endpoint(config: SecurityConfig = None):
    """Decorator to secure an endpoint"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get middleware
            middleware = get_security_middleware()
            if config:
                middleware = SecurityMiddleware(config)

            # Create mock request
            request = {"endpoint": func.__name__, "args": args, "kwargs": kwargs}

            # Process through middleware
            try:
                processed_request = await middleware(request)
                # Call function with processed request
                if hasattr(func, "__annotations__"):
                    # Pass processed request if function expects it
                    return await func(processed_request, *args, **kwargs)
                else:
                    return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Security middleware error: {e}")
                raise

        return wrapper

    return decorator


# Example usage
if __name__ == "__main__":
    import asyncio

    async def example():
        # Create middleware
        config = SecurityConfig(rate_limit_enabled=True, input_validation_enabled=True, require_auth=False)
        middleware = SecurityMiddleware(config)

        # Test request
        request = {
            "data": {"email": "test@example.com", "username": "testuser", "query": "What is Python?"},
            "client_ip": "127.0.0.1",
        }

        # Process request
        try:
            processed = await middleware(request)
            print("Request processed successfully")
            print(f"Security metadata: {processed.get('__security__')}")
        except Exception as e:
            print(f"Request failed: {e}")

    asyncio.run(example())
