"""
Dependency Injection Container
Provides DI container for managing service dependencies
"""

import logging
from typing import Any, Dict, Type, Callable, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class ServiceNotRegisteredError(Exception):
    """Raised when trying to get an unregistered service"""

    pass


class ServiceAlreadyRegisteredError(Exception):
    """Raised when trying to register a service that already exists"""

    pass


class DIContainer:
    """
    Dependency Injection Container

    Manages service registration and resolution with support for:
    - Singleton and transient lifetimes
    - Factory functions
    - Circular dependency detection
    """

    def __init__(self):
        self._services: Dict[Type, Dict[str, Any]] = {}
        self._singletons: Dict[Type, Any] = {}
        self._resolving: set[Type] = set()

    def register(
        self,
        interface: Type,
        implementation: Optional[Type] = None,
        lifetime: str = "singleton",
        factory: Optional[Callable] = None,
    ):
        """
        Register a service

        Args:
            interface: The interface or base class type
            implementation: The concrete implementation (if not using factory)
            lifetime: "singleton" or "transient"
            factory: Factory function to create the service
        """
        if interface in self._services:
            raise ServiceAlreadyRegisteredError(f"Service {interface.__name__} already registered")

        if not implementation and not factory:
            raise ValueError("Must provide either implementation or factory")

        if implementation and factory:
            raise ValueError("Cannot specify both implementation and factory")

        self._services[interface] = {"implementation": implementation, "factory": factory, "lifetime": lifetime}

        logger.debug(f"Registered service: {interface.__name__} ({lifetime})")

    def register_singleton(self, interface: Type, instance: Any):
        """
        Register a pre-created singleton instance

        Args:
            interface: The interface type
            instance: The singleton instance
        """
        self._singletons[interface] = instance
        self._services[interface] = {
            "implementation": None,
            "factory": None,
            "lifetime": "singleton",
            "pre_created": True,
        }
        logger.debug(f"Registered singleton: {interface.__name__}")

    def get(self, interface: Type) -> Any:
        """
        Resolve a service from the container

        Args:
            interface: The interface type

        Returns:
            The resolved service instance

        Raises:
            ServiceNotRegisteredError: If service is not registered
        """
        if interface not in self._services:
            raise ServiceNotRegisteredError(f"Service {interface.__name__} not registered")

        # Return pre-created singleton if available
        if interface in self._singletons and "pre_created" in self._services[interface]:
            return self._singletons[interface]

        # Check if already resolving (circular dependency detection)
        if interface in self._resolving:
            raise RuntimeError(f"Circular dependency detected for service {interface.__name__}")

        config = self._services[interface]
        lifetime = config["lifetime"]

        # Return existing singleton if lifetime is singleton
        if lifetime == "singleton" and interface in self._singletons:
            return self._singletons[interface]

        # Mark as resolving
        self._resolving.add(interface)

        try:
            # Create instance
            if config["factory"]:
                instance = config["factory"]()
            elif config["implementation"]:
                instance = self._create_instance(config["implementation"])
            else:
                raise RuntimeError(f"No factory or implementation for service {interface.__name__}")

            # Store singleton if needed
            if lifetime == "singleton":
                self._singletons[interface] = instance

            logger.debug(f"Resolved service: {interface.__name__}")
            return instance

        finally:
            # Remove from resolving
            self._resolving.discard(interface)

    def _create_instance(self, implementation: Type) -> Any:
        """
        Create an instance of a class with dependency injection

        Args:
            implementation: The class to instantiate

        Returns:
            The created instance
        """
        # Get constructor signature (simplified - in real implementation,
        # use inspect.signature)
        try:
            # Try to create with no arguments first
            return implementation()
        except TypeError:
            # If that fails, try to resolve dependencies from container
            # This is a simplified implementation
            # In practice, you'd want to inspect the __init__ signature
            # and resolve each parameter
            logger.warning(
                f"Could not automatically resolve dependencies for "
                f"{implementation.__name__}. Using parameterless constructor."
            )
            return implementation()

    def has(self, interface: Type) -> bool:
        """Check if a service is registered"""
        return interface in self._services

    def clear(self):
        """Clear all registered services"""
        self._services.clear()
        self._singletons.clear()
        self._resolving.clear()
        logger.info("DI container cleared")

    def get_registered_services(self) -> list:
        """Get list of registered service types"""
        return list(self._services.keys())


# Global DI container instance
_container = DIContainer()


def get_container() -> DIContainer:
    """Get the global DI container instance"""
    return _container


def register_service(
    interface: Type,
    implementation: Optional[Type] = None,
    lifetime: str = "singleton",
    factory: Optional[Callable] = None,
):
    """
    Decorator for registering services

    Example:
        @register_service(IMyService, MyService)
        class MyService:
            pass
    """

    def decorator(cls: Type):
        get_container().register(interface, cls, lifetime, factory)
        return cls

    return decorator


def inject(*interfaces: Type):
    """
    Decorator for automatic dependency injection

    Example:
        class MyService:
            @inject(IDatabaseClient, ILogger)
            def __init__(self, db: IDatabaseClient, logger: ILogger):
                self.db = db
                self.logger = logger
    """

    def decorator(cls: Type):
        original_init = cls.__init__

        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            container = get_container()

            # Inject dependencies
            for interface in interfaces:
                if interface in kwargs or any(isinstance(a, interface) for a in args):
                    continue

                try:
                    instance = container.get(interface)
                    kwargs[interface.__name__.lower()] = instance
                except ServiceNotRegisteredError:
                    logger.warning(f"Service {interface.__name__} not found for injection")

            # Call original init
            original_init(self, *args, **kwargs)

        cls.__init__ = new_init
        return cls

    return decorator


# Context manager for scoped containers
class ContainerScope:
    """Scope for DI container with automatic cleanup"""

    def __init__(self, container: Optional[DIContainer] = None):
        self.container = container or DIContainer()
        self._parent = None

    def __enter__(self) -> DIContainer:
        self._parent = get_container()
        # In a full implementation, you'd switch to this container
        # For now, just return it
        return self.container

    def __exit__(self, exc_type, exc_val, exc_tb):
        # In a full implementation, you'd restore the parent container
        pass
