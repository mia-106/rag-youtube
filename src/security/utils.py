"""
Security Utilities Module
Provides security utilities for encryption, hashing, tokens, and more
"""

import os
import re
import secrets
import hashlib
import hmac
from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime, timedelta
import base64
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Security-related error"""

    pass


class TokenExpiredError(SecurityError):
    """Token has expired"""

    pass


class InvalidTokenError(SecurityError):
    """Token is invalid"""

    pass


class CryptographyError(SecurityError):
    """Cryptography operation failed"""

    pass


class SecurityManager:
    """Security manager for encryption, hashing, and tokens"""

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize security manager

        Args:
            secret_key: Secret key for encryption (generated if not provided)
        """
        self.secret_key = secret_key or os.environ.get("SECURITY_SECRET_KEY")
        if not self.secret_key:
            self.secret_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
            logger.warning("Generated new secret key - set SECURITY_SECRET_KEY environment variable for persistence")

        self._fernet = self._create_fernet(self.secret_key)

    def _create_fernet(self, key: str) -> Fernet:
        """Create Fernet instance from key"""
        try:
            # Derive key from secret
            key_bytes = key.encode()
            salt = b"youtube_rag_salt"  # In production, use random salt and store it
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            derived_key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
            return Fernet(derived_key)
        except Exception as e:
            raise CryptographyError(f"Failed to create Fernet instance: {e}")

    def encrypt(self, data: str) -> str:
        """
        Encrypt data

        Args:
            data: String to encrypt

        Returns:
            Encrypted string (base64 encoded)
        """
        try:
            encrypted_bytes = self._fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()
        except Exception as e:
            raise CryptographyError(f"Encryption failed: {e}")

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data

        Args:
            encrypted_data: Encrypted string (base64 encoded)

        Returns:
            Decrypted string
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        except Exception as e:
            raise CryptographyError(f"Decryption failed: {e}")

    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        Hash password using PBKDF2

        Args:
            password: Password to hash
            salt: Salt (generated if not provided)

        Returns:
            Tuple of (salt, hash)
        """
        if salt is None:
            salt = os.urandom(32)

        pwdhash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return salt, pwdhash

    def verify_password(self, password: str, salt: bytes, expected_hash: bytes) -> bool:
        """
        Verify password

        Args:
            password: Password to verify
            salt: Salt used for hashing
            expected_hash: Expected hash

        Returns:
            True if password matches, False otherwise
        """
        _, hash = self.hash_password(password, salt)
        return hmac.compare_digest(hash, expected_hash)

    def generate_token(self, length: int = 32) -> str:
        """
        Generate cryptographically secure token

        Args:
            length: Token length in bytes

        Returns:
            Hex-encoded token
        """
        return secrets.token_hex(length)

    def generate_api_key(self) -> str:
        """
        Generate API key

        Returns:
            API key string
        """
        return f"rk_{self.generate_token(24)}"

    def hash_data(self, data: str) -> str:
        """
        Hash data using SHA256

        Args:
            data: Data to hash

        Returns:
            Hex-encoded hash
        """
        return hashlib.sha256(data.encode()).hexdigest()

    def verify_hmac(self, data: str, signature: str, secret: str) -> bool:
        """
        Verify HMAC signature

        Args:
            data: Data that was signed
            signature: HMAC signature to verify
            secret: Secret key used for signing

        Returns:
            True if signature is valid, False otherwise
        """
        expected_signature = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected_signature)

    def create_jwt_token(self, payload: Dict[str, Any], expiration_hours: int = 24) -> str:
        """
        Create simple JWT token (for demonstration - use a proper JWT library in production)

        Args:
            payload: Token payload
            expiration_hours: Token expiration in hours

        Returns:
            JWT token string
        """
        # Add standard claims
        now = datetime.utcnow()
        payload.update(
            {
                "iat": now,  # Issued at
                "exp": now + timedelta(hours=expiration_hours),  # Expiration
                "jti": secrets.token_hex(16),  # JWT ID
            }
        )

        # Create header and payload
        header = {"typ": "JWT", "alg": "HS256"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

        # Create signature
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(self.secret_key.encode(), message.encode(), hashlib.sha256).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        return f"{message}.{signature_b64}"

    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT token

        Args:
            token: JWT token string

        Returns:
            Decoded payload

        Raises:
            TokenExpiredError: If token has expired
            InvalidTokenError: If token is invalid
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise InvalidTokenError("Invalid token format")

            header_b64, payload_b64, signature_b64 = parts

            # Verify signature
            message = f"{header_b64}.{payload_b64}"
            expected_signature = hmac.new(self.secret_key.encode(), message.encode(), hashlib.sha256).digest()
            provided_signature = base64.urlsafe_b64decode(signature_b64 + "==")

            if not hmac.compare_digest(expected_signature, provided_signature):
                raise InvalidTokenError("Invalid signature")

            # Decode payload
            payload_bytes = base64.urlsafe_b64decode(payload_b64 + "==")
            payload = json.loads(payload_bytes.decode())

            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
                raise TokenExpiredError("Token has expired")

            return payload

        except (json.JSONDecodeError, ValueError) as e:
            raise InvalidTokenError(f"Token decode failed: {e}")
        except Exception as e:
            raise InvalidTokenError(f"Token verification failed: {e}")

    def mask_sensitive_data(self, data: str, mask_char: str = "*", reveal_count: int = 4) -> str:
        """
        Mask sensitive data (e.g., passwords, API keys)

        Args:
            data: Data to mask
            mask_char: Character to use for masking
            reveal_count: Number of characters to reveal at end

        Returns:
            Masked string
        """
        if len(data) <= reveal_count * 2:
            return mask_char * len(data)

        return data[:reveal_count] + mask_char * (len(data) - reveal_count * 2) + data[-reveal_count:]


# Rate Limiter
class RateLimiter:
    """Rate limiter for API calls"""

    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize rate limiter

        Args:
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}

    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed

        Args:
            identifier: Unique identifier (e.g., IP address, user ID)

        Returns:
            True if request is allowed, False otherwise
        """
        now = datetime.now()

        if identifier not in self.requests:
            self.requests[identifier] = []

        # Clean old requests outside the window
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.requests[identifier] = [req_time for req_time in self.requests[identifier] if req_time > cutoff]

        # Check if under limit
        if len(self.requests[identifier]) < self.max_requests:
            self.requests[identifier].append(now)
            return True

        return False


# Secure Config
class SecureConfig:
    """Secure configuration loader"""

    @staticmethod
    def load_secure_config() -> Dict[str, Any]:
        """Load configuration from environment variables"""
        config = {}

        # API Keys (required)
        required_keys = ["DEEPSEEK_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]

        for key in required_keys:
            value = os.environ.get(key)
            if not value:
                raise SecurityError(f"Required environment variable {key} is not set")
            config[key] = value

        # Optional keys
        optional_keys = ["FIRECRAWL_API_KEY", "COHERE_API_KEY", "LANGCHAIN_API_KEY"]

        for key in optional_keys:
            value = os.environ.get(key)
            if value:
                config[key] = value

        return config


# Password Policy
class PasswordPolicy:
    """Password policy validator"""

    @staticmethod
    def validate_password(password: str) -> Tuple[bool, List[str]]:
        """
        Validate password against policy

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Minimum length
        if len(password) < 12:
            errors.append("Password must be at least 12 characters long")

        # Maximum length
        if len(password) > 128:
            errors.append("Password must be less than 128 characters")

        # At least one uppercase
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")

        # At least one lowercase
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")

        # At least one digit
        if not re.search(r"\d", password):
            errors.append("Password must contain at least one digit")

        # At least one special character
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};:,.<>?]", password):
            errors.append("Password must contain at least one special character")

        # No common patterns
        common_patterns = ["123456", "password", "qwerty", "abc123", "111111", "123456789"]
        if any(pattern in password.lower() for pattern in common_patterns):
            errors.append("Password contains common patterns")

        return len(errors) == 0, errors


# Global security manager instance
_security_manager = None


def get_security_manager() -> SecurityManager:
    """Get global security manager instance"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


# Example usage
if __name__ == "__main__":
    # Initialize security manager
    sec = SecurityManager()

    # Encrypt and decrypt
    original = "Secret message"
    encrypted = sec.encrypt(original)
    decrypted = sec.decrypt(encrypted)
    print(f"Original: {original}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")

    # Hash password
    password = "MySecurePassword123!"
    salt, hash_pwd = sec.hash_password(password)
    print(f"\nPassword: {password}")
    print(f"Salt: {salt.hex()}")
    print(f"Hash: {hash_pwd.hex()}")

    # Verify password
    is_valid = sec.verify_password(password, salt, hash_pwd)
    print(f"Password valid: {is_valid}")

    # Create and verify JWT token
    payload = {"user_id": "12345", "role": "admin"}
    token = sec.create_jwt_token(payload)
    print(f"\nToken: {token}")

    decoded = sec.verify_jwt_token(token)
    print(f"Decoded: {decoded}")

    # Mask sensitive data
    api_key = "sk-1234567890abcdef"
    masked = sec.mask_sensitive_data(api_key)
    print(f"\nAPI Key: {api_key}")
    print(f"Masked: {masked}")

    # Rate limiting
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    for i in range(7):
        allowed = limiter.is_allowed("127.0.0.1")
        print(f"Request {i + 1}: {'Allowed' if allowed else 'Blocked'}")
