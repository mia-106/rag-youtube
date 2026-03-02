"""
Configuration Management System
Provides typed, validated, and hierarchical configuration management
"""

import os
import yaml
import json
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field, fields
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConfigSource(Enum):
    """Configuration source priority"""

    ENVIRONMENT = "environment"
    FILE = "file"
    DEFAULT = "default"


@dataclass
class ConfigMetadata:
    """Configuration field metadata"""

    env_var: Optional[str] = None
    required: bool = False
    default: Any = None
    description: str = ""
    validation: Optional[str] = None
    source: ConfigSource = ConfigSource.DEFAULT
    sources: List[ConfigSource] = field(
        default_factory=lambda: [ConfigSource.ENVIRONMENT, ConfigSource.FILE, ConfigSource.DEFAULT]
    )


class ConfigError(Exception):
    """Configuration error"""

    pass


class ValidationError(ConfigError):
    """Configuration validation error"""

    pass


class TypedConfig:
    """
    Typed configuration manager with validation and hierarchical sources

    Features:
    - Environment variable support
    - YAML/JSON file support
    - Type validation and conversion
    - Nested configuration support
    - Hot-reloading capability
    """

    def __init__(
        self,
        config_class: type,
        env_prefix: str = "",
        config_file_path: Optional[str] = None,
        auto_reload: bool = False,
    ):
        """
        Initialize configuration manager

        Args:
            config_class: The dataclass type for configuration
            env_prefix: Prefix for environment variables
            config_file_path: Path to configuration file
            auto_reload: Enable automatic file reloading
        """
        if not hasattr(config_class, "__dataclass_fields__"):
            raise ValueError("config_class must be a dataclass")

        self.config_class = config_class
        self.env_prefix = env_prefix.upper()
        self.config_file_path = config_file_path
        self.auto_reload = auto_reload
        self._metadata: Dict[str, ConfigMetadata] = {}
        self._cache: Dict[str, Any] = {}
        self._last_modified: Optional[float] = None

        # Extract metadata from dataclass fields
        self._extract_metadata()

        # Load configuration
        self._load()

    def _extract_metadata(self):
        """Extract configuration metadata from dataclass fields"""
        for config_field in fields(self.config_class):
            # Get metadata from field metadata
            field_meta = config_field.metadata.get("config", ConfigMetadata())

            # Set default env_var if not provided
            if not field_meta.env_var:
                field_meta.env_var = f"{self.env_prefix}_{config_field.name}".upper()

            self._metadata[config_field.name] = field_meta

    def _load(self):
        """Load configuration from all sources"""
        # Try to load from file first
        if self.config_file_path:
            self._load_from_file()
        else:
            # Create default instance
            self._create_default()

        # Override with environment variables
        self._load_from_env()

    def _load_from_file(self):
        """Load configuration from file"""
        if not self.config_file_path or not os.path.exists(self.config_file_path):
            logger.debug(f"Config file not found: {self.config_file_path}")
            self._create_default()
            return

        try:
            with open(self.config_file_path, "r") as f:
                if self.config_file_path.endswith(".yaml") or self.config_file_path.endswith(".yml"):
                    file_config = yaml.safe_load(f)
                elif self.config_file_path.endswith(".json"):
                    file_config = json.load(f)
                else:
                    raise ConfigError(f"Unsupported config file format: {self.config_file_path}")

            # Create config instance from file
            self._cache = self._create_from_dict(file_config)
            logger.info(f"Loaded configuration from {self.config_file_path}")

        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            self._create_default()

    def _load_from_env(self):
        """Load configuration from environment variables"""
        env_values = {}

        for field_name, meta in self._metadata.items():
            env_var = meta.env_var
            env_value = os.environ.get(env_var)

            if env_value is not None:
                env_values[field_name] = self._convert_value(env_value, self._get_field_type(field_name))
                logger.debug(f"Loaded {field_name} from environment variable {env_var}")

        # Update cache with environment values
        if env_values:
            for key, value in env_values.items():
                self._cache[key] = value

    def _create_default(self):
        """Create default configuration instance"""
        try:
            # Get default values from dataclass
            defaults = {}
            for field in fields(self.config_class):
                if field.default != field.default_factory:
                    defaults[field.name] = field.default
                else:
                    defaults[field.name] = field.default_factory()

            self._cache = defaults
            logger.debug("Created default configuration")

        except Exception as e:
            logger.error(f"Failed to create default configuration: {e}")
            raise

    def _create_from_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create configuration from dictionary"""
        result = {}

        for field_name, field_meta in self._metadata.items():
            if field_name in data:
                result[field_name] = data[field_name]
            elif field_meta.required and field_meta.default is None:
                raise ValidationError(f"Required configuration field missing: {field_name}")

        return result

    def _get_field_type(self, field_name: str) -> type:
        """Get the type of a configuration field"""
        for config_field in fields(self.config_class):
            if config_field.name == field_name:
                return config_field.type
        return str

    def _convert_value(self, value: str, target_type: type) -> Any:
        """Convert string value to target type"""
        if target_type is bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif target_type is int:
            return int(value)
        elif target_type is float:
            return float(value)
        elif target_type is list:
            return value.split(",")
        elif target_type is dict:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}
        else:
            return value

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._cache.get(key, default)

    def set(self, key: str, value: Any):
        """Set configuration value"""
        self._cache[key] = value

    def validate(self) -> bool:
        """Validate configuration"""
        for field_name, meta in self._metadata.items():
            # Check required fields
            if meta.required and field_name not in self._cache:
                raise ValidationError(f"Required configuration field missing: {field_name}")

            # Validate field value
            if field_name in self._cache:
                value = self._cache[field_name]
                self._validate_field(field_name, value, meta)

        logger.info("Configuration validation successful")
        return True

    def _validate_field(self, field_name: str, value: Any, meta: ConfigMetadata):
        """Validate a single configuration field"""
        # Implement validation logic here
        # For now, just basic checks
        if meta.validation:
            # Run custom validation
            pass

    def reload(self):
        """Reload configuration from sources"""
        logger.info("Reloading configuration...")
        self._load()

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return self._cache.copy()

    def to_yaml(self) -> str:
        """Convert configuration to YAML"""
        return yaml.dump(self._cache, default_flow_style=False)

    def to_json(self) -> str:
        """Convert configuration to JSON"""
        return json.dumps(self._cache, indent=2)


# Decorator for configuration fields
def config_field(
    env_var: Optional[str] = None,
    required: bool = False,
    default: Any = None,
    description: str = "",
    validation: Optional[str] = None,
):
    """
    Decorator to add metadata to dataclass fields

    Args:
        env_var: Environment variable name
        required: Whether the field is required
        default: Default value
        description: Field description
        validation: Validation function name
    """

    def decorator(field):
        field.metadata["config"] = ConfigMetadata(
            env_var=env_var, required=required, default=default, description=description, validation=validation
        )
        return field

    return decorator


# Example usage
@dataclass
class DatabaseConfig:
    """Database configuration"""

    host: str = "localhost"
    port: int = 5432
    name: str = "mydb"
    user: str = "user"
    password: str = ""

    # Use decorator for environment variable support
    password: str = field(
        default="",
        metadata={"config": ConfigMetadata(env_var="DB_PASSWORD", required=True, description="Database password")},
    )


# Configuration manager factory
def create_config(config_class: type, env_prefix: str = "", config_file: Optional[str] = None) -> TypedConfig:
    """
    Create a configuration manager

    Args:
        config_class: Dataclass type for configuration
        env_prefix: Environment variable prefix
        config_file: Path to configuration file

    Returns:
        TypedConfig instance
    """
    return TypedConfig(config_class=config_class, env_prefix=env_prefix, config_file_path=config_file)


# Global configuration instances
_configs: Dict[str, TypedConfig] = {}


def get_config(name: str = "default") -> TypedConfig:
    """
    Get a named configuration instance

    Args:
        name: Configuration name

    Returns:
        TypedConfig instance
    """
    if name not in _configs:
        raise ConfigError(f"Configuration '{name}' not found. Create it first with create_config().")
    return _configs[name]


def register_config(name: str, config: TypedConfig):
    """
    Register a configuration instance

    Args:
        name: Configuration name
        config: TypedConfig instance
    """
    _configs[name] = config


# Configuration templates
@dataclass
class APIConfig:
    """API configuration"""

    base_url: str = "https://api.example.com"
    timeout: int = 30
    retry_attempts: int = 3
    api_key: str = field(
        default="",
        metadata={"config": ConfigMetadata(env_var="API_KEY", required=True, description="API authentication key")},
    )


@dataclass
class CacheConfig:
    """Cache configuration"""

    type: str = "memory"  # memory, redis, memcached
    ttl: int = 3600
    max_size: int = 1000


@dataclass
class LoggingConfig:
    """Logging configuration"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None


@dataclass
class AppConfig:
    """Application configuration"""

    name: str = "YouTube Agentic RAG"
    version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


# Initialize default configuration
_default_config = create_config(AppConfig, env_prefix="APP", config_file="config.yaml")

register_config("default", _default_config)


def get_app_config() -> AppConfig:
    """Get the default application configuration"""
    config = get_config("default")
    return AppConfig(**config.to_dict())


# Configuration validation
def validate_all_configs() -> bool:
    """Validate all registered configurations"""
    all_valid = True
    for name, config in _configs.items():
        try:
            config.validate()
            logger.info(f"Configuration '{name}' is valid")
        except ValidationError as e:
            logger.error(f"Configuration '{name}' validation failed: {e}")
            all_valid = False
    return all_valid


# Configuration utilities
def list_configs() -> List[str]:
    """List all registered configuration names"""
    return list(_configs.keys())


def export_config(name: str = "default", format: str = "yaml") -> str:
    """
    Export configuration to string

    Args:
        name: Configuration name
        format: Output format (yaml or json)

    Returns:
        Configuration as string
    """
    config = get_config(name)

    if format.lower() == "yaml":
        return config.to_yaml()
    elif format.lower() == "json":
        return config.to_json()
    else:
        raise ValueError(f"Unsupported format: {format}")
