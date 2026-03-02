"""
Comprehensive Input Validation Module
Provides secure input validation for all user inputs
"""

import re
import html
from typing import Any, Optional, Dict, List, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Validation error"""

    pass


class ValidationSeverity(Enum):
    """Validation error severity"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Validation result"""

    is_valid: bool
    severity: ValidationSeverity
    message: str
    field: Optional[str] = None
    value: Any = None
    suggestions: List[str] = None

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


class ValidationRule:
    """Base validation rule"""

    def __init__(self, required: bool = True, allow_none: bool = False):
        self.required = required
        self.allow_none = allow_none

    def validate(self, value: Any, field_name: str = None) -> ValidationResult:
        """Validate a value"""
        raise NotImplementedError


class StringValidator(ValidationRule):
    """String validation rule"""

    def __init__(
        self,
        min_length: int = 0,
        max_length: int = 10000,
        pattern: Optional[str] = None,
        allowed_chars: Optional[str] = None,
        forbidden_chars: Optional[str] = None,
        required: bool = True,
        allow_none: bool = False,
        strip_whitespace: bool = True,
        encoding: str = "utf-8",
    ):
        super().__init__(required, allow_none)
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = re.compile(pattern) if pattern else None
        self.allowed_chars = allowed_chars
        self.forbidden_chars = forbidden_chars
        self.strip_whitespace = strip_whitespace
        self.encoding = encoding

    def validate(self, value: Any, field_name: str = None) -> ValidationResult:
        """Validate string value"""
        # Check None
        if value is None:
            if self.allow_none:
                return ValidationResult(True, ValidationSeverity.INFO, "Value is None (allowed)")
            if not self.required:
                return ValidationResult(True, ValidationSeverity.INFO, "Value is None (optional)")

            return ValidationResult(
                False, ValidationSeverity.ERROR, f"Field {field_name} is required", field_name, value
            )

        # Type check
        if not isinstance(value, str):
            return ValidationResult(
                False,
                ValidationSeverity.ERROR,
                f"Field {field_name} must be a string, got {type(value).__name__}",
                field_name,
                value,
            )

        # Strip whitespace
        if self.strip_whitespace:
            original_value = value
            value = value.strip()
            if value != original_value:
                logger.debug(f"Stripped whitespace from {field_name}")

        # Length check
        if len(value) < self.min_length:
            return ValidationResult(
                False,
                ValidationSeverity.ERROR,
                f"Field {field_name} is too short (min: {self.min_length}, got: {len(value)})",
                field_name,
                value,
            )

        if len(value) > self.max_length:
            return ValidationResult(
                False,
                ValidationSeverity.ERROR,
                f"Field {field_name} is too long (max: {self.max_length}, got: {len(value)})",
                field_name,
                value,
            )

        # Pattern check
        if self.pattern and not self.pattern.match(value):
            return ValidationResult(
                False,
                ValidationSeverity.ERROR,
                f"Field {field_name} does not match required pattern",
                field_name,
                value,
            )

        # Allowed characters check
        if self.allowed_chars:
            invalid_chars = set(value) - set(self.allowed_chars)
            if invalid_chars:
                return ValidationResult(
                    False,
                    ValidationSeverity.ERROR,
                    f"Field {field_name} contains invalid characters: {invalid_chars}",
                    field_name,
                    value,
                )

        # Forbidden characters check
        if self.forbidden_chars:
            forbidden_found = set(value) & set(self.forbidden_chars)
            if forbidden_found:
                return ValidationResult(
                    False,
                    ValidationSeverity.ERROR,
                    f"Field {field_name} contains forbidden characters: {forbidden_found}",
                    field_name,
                    value,
                )

        return ValidationResult(True, ValidationSeverity.INFO, f"Field {field_name} is valid", field_name, value)


class EmailValidator(StringValidator):
    """Email validation rule"""

    def __init__(self, required: bool = True):
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        super().__init__(
            min_length=5,
            max_length=320,  # RFC 5321 limit
            pattern=pattern,
            required=required,
        )


class URLValidator(StringValidator):
    """URL validation rule"""

    def __init__(self, required: bool = True, allowed_schemes: List[str] = None):
        self.allowed_schemes = allowed_schemes or ["http", "https"]
        pattern = r"^https?://"  # Basic URL pattern
        super().__init__(min_length=10, max_length=2048, pattern=pattern, required=required)

    def validate(self, value: Any, field_name: str = None) -> ValidationResult:
        """Validate URL value"""
        result = super().validate(value, field_name)
        if not result.is_valid:
            return result

        # Check scheme
        try:
            from urllib.parse import urlparse

            parsed = urlparse(value)
            if parsed.scheme not in self.allowed_schemes:
                return ValidationResult(
                    False,
                    ValidationSeverity.ERROR,
                    f"Field {field_name} has invalid scheme: {parsed.scheme}",
                    field_name,
                    value,
                )
        except Exception as e:
            return ValidationResult(
                False, ValidationSeverity.ERROR, f"Field {field_name} is not a valid URL: {str(e)}", field_name, value
            )

        return result


class NumberValidator(ValidationRule):
    """Number validation rule"""

    def __init__(
        self,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        integer_only: bool = False,
        required: bool = True,
        allow_none: bool = False,
    ):
        super().__init__(required, allow_none)
        self.min_value = min_value
        self.max_value = max_value
        self.integer_only = integer_only

    def validate(self, value: Any, field_name: str = None) -> ValidationResult:
        """Validate numeric value"""
        # Check None
        if value is None:
            if self.allow_none:
                return ValidationResult(True, ValidationSeverity.INFO, "Value is None (allowed)")
            if not self.required:
                return ValidationResult(True, ValidationSeverity.INFO, "Value is None (optional)")

            return ValidationResult(
                False, ValidationSeverity.ERROR, f"Field {field_name} is required", field_name, value
            )

        # Type check
        if self.integer_only:
            if not isinstance(value, int):
                return ValidationResult(
                    False, ValidationSeverity.ERROR, f"Field {field_name} must be an integer", field_name, value
                )
        else:
            if not isinstance(value, (int, float)):
                return ValidationResult(
                    False, ValidationSeverity.ERROR, f"Field {field_name} must be a number", field_name, value
                )

        # Range check
        if self.min_value is not None and value < self.min_value:
            return ValidationResult(
                False,
                ValidationSeverity.ERROR,
                f"Field {field_name} is too small (min: {self.min_value}, got: {value})",
                field_name,
                value,
            )

        if self.max_value is not None and value > self.max_value:
            return ValidationResult(
                False,
                ValidationSeverity.ERROR,
                f"Field {field_name} is too large (max: {self.max_value}, got: {value})",
                field_name,
                value,
            )

        return ValidationResult(True, ValidationSeverity.INFO, f"Field {field_name} is valid", field_name, value)


class ChoiceValidator(ValidationRule):
    """Choice validation rule"""

    def __init__(
        self, choices: List[Any], case_sensitive: bool = True, required: bool = True, allow_none: bool = False
    ):
        super().__init__(required, allow_none)
        self.choices = choices
        self.case_sensitive = case_sensitive

    def validate(self, value: Any, field_name: str = None) -> ValidationResult:
        """Validate choice value"""
        # Check None
        if value is None:
            if self.allow_none:
                return ValidationResult(True, ValidationSeverity.INFO, "Value is None (allowed)")
            if not self.required:
                return ValidationResult(True, ValidationSeverity.INFO, "Value is None (optional)")

            return ValidationResult(
                False, ValidationSeverity.ERROR, f"Field {field_name} is required", field_name, value
            )

        # Check choice
        choices = self.choices
        if not self.case_sensitive and isinstance(value, str):
            choices = [c.lower() if isinstance(c, str) else c for c in choices]
            value = value.lower()

        if value not in choices:
            return ValidationResult(
                False, ValidationSeverity.ERROR, f"Field {field_name} must be one of: {self.choices}", field_name, value
            )

        return ValidationResult(True, ValidationSeverity.INFO, f"Field {field_name} is valid", field_name, value)


class ListValidator(ValidationRule):
    """List validation rule"""

    def __init__(
        self,
        item_validator: Optional[ValidationRule] = None,
        min_items: int = 0,
        max_items: int = 100,
        required: bool = True,
        allow_none: bool = False,
    ):
        super().__init__(required, allow_none)
        self.item_validator = item_validator
        self.min_items = min_items
        self.max_items = max_items

    def validate(self, value: Any, field_name: str = None) -> ValidationResult:
        """Validate list value"""
        # Check None
        if value is None:
            if self.allow_none:
                return ValidationResult(True, ValidationSeverity.INFO, "Value is None (allowed)")
            if not self.required:
                return ValidationResult(True, ValidationSeverity.INFO, "Value is None (optional)")

            return ValidationResult(
                False, ValidationSeverity.ERROR, f"Field {field_name} is required", field_name, value
            )

        # Type check
        if not isinstance(value, (list, tuple)):
            return ValidationResult(
                False, ValidationSeverity.ERROR, f"Field {field_name} must be a list", field_name, value
            )

        # Length check
        if len(value) < self.min_items:
            return ValidationResult(
                False,
                ValidationSeverity.ERROR,
                f"Field {field_name} has too few items (min: {self.min_items}, got: {len(value)})",
                field_name,
                value,
            )

        if len(value) > self.max_items:
            return ValidationResult(
                False,
                ValidationSeverity.ERROR,
                f"Field {field_name} has too many items (max: {self.max_items}, got: {len(value)})",
                field_name,
                value,
            )

        # Validate items
        if self.item_validator:
            for i, item in enumerate(value):
                item_result = self.item_validator.validate(item, f"{field_name}[{i}]")
                if not item_result.is_valid:
                    return item_result

        return ValidationResult(True, ValidationSeverity.INFO, f"Field {field_name} is valid", field_name, value)


class InputValidator:
    """Comprehensive input validator"""

    def __init__(self):
        self.rules: Dict[str, ValidationRule] = {}

    def add_rule(self, field_name: str, rule: ValidationRule):
        """Add a validation rule"""
        self.rules[field_name] = rule

    def validate(self, data: Dict[str, Any]) -> Dict[str, List[ValidationResult]]:
        """Validate input data"""
        results: Dict[str, List[ValidationResult]] = {}

        for field_name, rule in self.rules.items():
            value = data.get(field_name)
            result = rule.validate(value, field_name)
            results[field_name] = [result]

        return results

    def is_valid(self, results: Dict[str, List[ValidationResult]]) -> bool:
        """Check if validation results are valid"""
        for field_results in results.values():
            for result in field_results:
                if not result.is_valid:
                    return False
        return True


# Predefined validators
def get_youtube_url_validator() -> URLValidator:
    """Get YouTube URL validator"""
    return URLValidator(required=True, allowed_schemes=["http", "https"])


def get_email_validator() -> EmailValidator:
    """Get email validator"""
    return EmailValidator(required=False)


def get_api_key_validator() -> StringValidator:
    """Get API key validator"""
    return StringValidator(min_length=20, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$", required=True)


def get_sql_query_validator() -> StringValidator:
    """Get SQL query validator"""
    return StringValidator(
        min_length=1, max_length=10000, forbidden_chars=[";", "--", "/*", "*/", "xp_", "sp_"], required=True
    )


def get_search_query_validator() -> StringValidator:
    """Get search query validator"""
    return StringValidator(
        min_length=1, max_length=500, forbidden_chars=["<", ">", "{", "}", "[", "]", "\\", "^", "~"], required=True
    )


# Security utilities
def sanitize_html(value: str) -> str:
    """Sanitize HTML to prevent XSS"""
    if not isinstance(value, str):
        return str(value)
    return html.escape(value)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename"""
    if not isinstance(filename, str):
        return "unnamed"

    # Remove path separators and dangerous characters
    filename = re.sub(r'[\\/:*?"<>|]', "", filename)

    # Limit length
    if len(filename) > 255:
        filename = filename[:255]

    return filename or "unnamed"


def escape_sql_value(value: str) -> str:
    """Escape SQL special characters"""
    if not isinstance(value, str):
        return str(value)

    # Escape single quotes
    value = value.replace("'", "''")

    # Escape wildcards
    value = value.replace("%", "\\%")
    value = value.replace("_", "\\_")

    return value


def validate_file_path(path: str) -> bool:
    """Validate file path for security"""
    if not isinstance(path, str):
        return False

    # Check for path traversal
    if ".." in path or path.startswith("/"):
        return False

    # Check for absolute paths
    if ":" in path:  # Windows drive
        return False

    return True


# Decorator for input validation
def validate_input(validator: InputValidator):
    """Decorator for input validation"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get data from first argument (typically self or first param)
            if args:
                data = args[0] if isinstance(args[0], dict) else args[0].__dict__
            else:
                data = kwargs

            results = validator.validate(data)
            if not validator.is_valid(results):
                errors = []
                for field, field_results in results.items():
                    for result in field_results:
                        if not result.is_valid:
                            errors.append(f"{field}: {result.message}")

                raise ValidationError(f"Input validation failed: {'; '.join(errors)}")

            return func(*args, **kwargs)

        return wrapper

    return decorator


# Example usage
if __name__ == "__main__":
    # Create validator
    validator = InputValidator()

    # Add rules
    validator.add_rule("email", EmailValidator(required=True))
    validator.add_rule("age", NumberValidator(min_value=0, max_value=150))
    validator.add_rule("url", URLValidator(required=False))
    validator.add_rule("category", ChoiceValidator(["A", "B", "C"]))

    # Validate data
    data = {"email": "test@example.com", "age": 25, "url": "https://example.com", "category": "A"}

    results = validator.validate(data)
    print(f"Is valid: {validator.is_valid(results)}")
    print(f"Results: {results}")
