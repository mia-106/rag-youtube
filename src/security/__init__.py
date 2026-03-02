"""
Security Package
Comprehensive security module for the YouTube Agentic RAG system

This package provides:
- Input validation
- Authentication and authorization
- Encryption and hashing
- Rate limiting
- Security middleware
- Security utilities
"""

from .validation import (
    InputValidator,
    ValidationResult,
    ValidationSeverity,
    StringValidator,
    EmailValidator,
    URLValidator,
    NumberValidator,
    ChoiceValidator,
    ListValidator,
    validate_input,
    sanitize_html,
    sanitize_filename,
    escape_sql_value,
    validate_file_path,
    get_youtube_url_validator,
    get_email_validator,
    get_api_key_validator,
    get_sql_query_validator,
    get_search_query_validator,
    ValidationError,
)

from .utils import (
    SecurityManager,
    get_security_manager,
    RateLimiter,
    SecureConfig,
    PasswordPolicy,
    SecurityError,
    TokenExpiredError,
    InvalidTokenError,
    CryptographyError,
)

from .auth import (
    AuthManager,
    User,
    Session,
    Role,
    Permission,
    UserStore,
    SessionStore,
    InMemoryUserStore,
    InMemorySessionStore,
    RoleBasedAccessControl,
    get_auth_manager,
    get_user_store,
    get_session_store,
    require_permission,
    require_role,
    AuthError,
    PermissionError,
)

from .middleware import (
    SecurityMiddleware,
    SecurityConfig,
    SecurityEvent,
    SecurityHeaders,
    get_security_middleware,
    secure_endpoint,
)

__all__ = [
    # Validation
    "InputValidator",
    "ValidationResult",
    "ValidationSeverity",
    "StringValidator",
    "EmailValidator",
    "URLValidator",
    "NumberValidator",
    "ChoiceValidator",
    "ListValidator",
    "validate_input",
    "sanitize_html",
    "sanitize_filename",
    "escape_sql_value",
    "validate_file_path",
    "get_youtube_url_validator",
    "get_email_validator",
    "get_api_key_validator",
    "get_sql_query_validator",
    "get_search_query_validator",
    "ValidationError",
    # Utils
    "SecurityManager",
    "get_security_manager",
    "RateLimiter",
    "SecureConfig",
    "PasswordPolicy",
    "SecurityError",
    "TokenExpiredError",
    "InvalidTokenError",
    "CryptographyError",
    # Auth
    "AuthManager",
    "User",
    "Session",
    "Role",
    "Permission",
    "UserStore",
    "SessionStore",
    "InMemoryUserStore",
    "InMemorySessionStore",
    "RoleBasedAccessControl",
    "get_auth_manager",
    "get_user_store",
    "get_session_store",
    "require_permission",
    "require_role",
    "AuthError",
    "PermissionError",
    # Middleware
    "SecurityMiddleware",
    "SecurityConfig",
    "SecurityEvent",
    "SecurityHeaders",
    "get_security_middleware",
    "secure_endpoint",
]

# Version
__version__ = "1.0.0"
