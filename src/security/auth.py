"""
Authentication and Authorization Module
Provides user authentication, authorization, and session management
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set
from enum import Enum
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

from src.security.utils import get_security_manager

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Authentication error"""

    pass


class PermissionError(Exception):
    """Permission error"""

    pass


class Role(Enum):
    """User roles"""

    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    READ_ONLY = "read_only"


class Permission(Enum):
    """System permissions"""

    # User management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # Content management
    CONTENT_CREATE = "content:create"
    CONTENT_READ = "content:read"
    CONTENT_UPDATE = "content:update"
    CONTENT_DELETE = "content:delete"

    # System administration
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MONITOR = "system:monitor"

    # API access
    API_ACCESS = "api:access"
    API_ADMIN = "api:admin"


@dataclass
class User:
    """User model"""

    user_id: str
    username: str
    email: str
    role: Role
    permissions: Set[Permission]
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has specific permission"""
        if not self.is_active:
            return False

        # Admin has all permissions
        if self.role == Role.ADMIN:
            return True

        return permission in self.permissions

    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(self.has_permission(p) for p in permissions)

    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """Check if user has all of the specified permissions"""
        return all(self.has_permission(p) for p in permissions)

    def add_permission(self, permission: Permission):
        """Add permission to user"""
        self.permissions.add(permission)

    def remove_permission(self, permission: Permission):
        """Remove permission from user"""
        self.permissions.discard(permission)


@dataclass
class Session:
    """User session model"""

    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    last_accessed: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True

    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.now() > self.expires_at

    def extend(self, hours: int = 24):
        """Extend session expiration"""
        self.expires_at = datetime.now() + timedelta(hours=hours)
        self.last_accessed = datetime.now()


class UserStore(ABC):
    """Abstract user storage"""

    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        pass

    @abstractmethod
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        pass

    @abstractmethod
    async def create_user(self, user: User, password: str) -> User:
        """Create new user"""
        pass

    @abstractmethod
    async def update_user(self, user: User) -> User:
        """Update user"""
        pass

    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """Delete user"""
        pass

    @abstractmethod
    async def verify_password(self, user_id: str, password: str) -> bool:
        """Verify user password"""
        pass

    @abstractmethod
    async def list_users(self) -> List[User]:
        """List all users"""
        pass


class SessionStore(ABC):
    """Abstract session storage"""

    @abstractmethod
    async def create_session(self, session: Session) -> Session:
        """Create new session"""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        pass

    @abstractmethod
    async def update_session(self, session: Session) -> Session:
        """Update session"""
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        pass

    @abstractmethod
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        pass

    @abstractmethod
    async def get_user_sessions(self, user_id: str) -> List[Session]:
        """Get all sessions for a user"""
        pass


class InMemoryUserStore(UserStore):
    """In-memory user store (for testing/demo)"""

    def __init__(self):
        self.users: Dict[str, User] = {}
        self.users_by_username: Dict[str, str] = {}
        self.users_by_email: Dict[str, str] = {}
        self.passwords: Dict[str, str] = {}
        self.security = get_security_manager()

    async def get_user(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)

    async def get_user_by_username(self, username: str) -> Optional[User]:
        user_id = self.users_by_username.get(username)
        if user_id:
            return self.users.get(user_id)
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        user_id = self.users_by_email.get(email)
        if user_id:
            return self.users.get(user_id)
        return None

    async def create_user(self, user: User, password: str) -> User:
        if user.user_id in self.users:
            raise AuthError(f"User {user.user_id} already exists")

        if user.username in self.users_by_username:
            raise AuthError(f"Username {user.username} already exists")

        if user.email in self.users_by_email:
            raise AuthError(f"Email {user.email} already exists")

        # Hash password
        salt, hashed_pwd = self.security.hash_password(password)
        self.passwords[user.user_id] = salt.hex() + ":" + hashed_pwd.hex()

        # Store user
        self.users[user.user_id] = user
        self.users_by_username[user.username] = user.user_id
        self.users_by_email[user.email] = user.user_id

        return user

    async def update_user(self, user: User) -> User:
        if user.user_id not in self.users:
            raise AuthError(f"User {user.user_id} not found")

        # Update indices if username or email changed
        old_user = self.users[user.user_id]
        if old_user.username != user.username:
            del self.users_by_username[old_user.username]
            self.users_by_username[user.username] = user.user_id

        if old_user.email != user.email:
            del self.users_by_email[old_user.email]
            self.users_by_email[user.email] = user.user_id

        self.users[user.user_id] = user
        return user

    async def delete_user(self, user_id: str) -> bool:
        if user_id not in self.users:
            return False

        user = self.users[user_id]
        del self.users[user_id]
        del self.users_by_username[user.username]
        del self.users_by_email[user.email]
        del self.passwords[user_id]

        return True

    async def verify_password(self, user_id: str, password: str) -> bool:
        if user_id not in self.users or user_id not in self.passwords:
            return False

        password_data = self.passwords[user_id]
        salt_hex, hash_hex = password_data.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)

        return self.security.verify_password(password, salt, expected_hash)

    async def list_users(self) -> List[User]:
        return list(self.users.values())


class InMemorySessionStore(SessionStore):
    """In-memory session store (for testing/demo)"""

    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.sessions_by_user: Dict[str, Set[str]] = {}

    async def create_session(self, session: Session) -> Session:
        self.sessions[session.session_id] = session

        if session.user_id not in self.sessions_by_user:
            self.sessions_by_user[session.user_id] = set()
        self.sessions_by_user[session.user_id].add(session.session_id)

        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        session = self.sessions.get(session_id)
        if session and session.is_expired():
            await self.delete_session(session_id)
            return None
        return session

    async def update_session(self, session: Session) -> Session:
        if session.session_id in self.sessions:
            self.sessions[session.session_id] = session
        return session

    async def delete_session(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False

        del self.sessions[session_id]
        if session.user_id in self.sessions_by_user:
            self.sessions_by_user[session.user_id].discard(session_id)

        return True

    async def cleanup_expired_sessions(self) -> int:
        expired = []
        for session_id, session in self.sessions.items():
            if session.is_expired():
                expired.append(session_id)

        for session_id in expired:
            await self.delete_session(session_id)

        return len(expired)

    async def get_user_sessions(self, user_id: str) -> List[Session]:
        session_ids = self.sessions_by_user.get(user_id, set())
        return [self.sessions[sid] for sid in session_ids if sid in self.sessions]


class AuthManager:
    """Authentication and authorization manager"""

    def __init__(self, user_store: UserStore, session_store: SessionStore):
        self.user_store = user_store
        self.session_store = session_store
        self.security = get_security_manager()

    async def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user"""
        user = await self.user_store.get_user_by_username(username)
        if not user:
            logger.warning(f"Login attempt with non-existent username: {username}")
            return None

        if not user.is_active:
            logger.warning(f"Login attempt with inactive user: {username}")
            return None

        is_valid = await self.user_store.verify_password(user.user_id, password)
        if not is_valid:
            logger.warning(f"Invalid password for user: {username}")
            return None

        # Update last login
        user.last_login = datetime.now()
        await self.user_store.update_user(user)

        logger.info(f"User {username} logged in successfully")
        return user

    async def create_session(
        self, user: User, ip_address: Optional[str] = None, user_agent: Optional[str] = None, expiration_hours: int = 24
    ) -> Session:
        """Create user session"""
        session_id = self.security.generate_token(32)
        now = datetime.now()
        expires_at = now + timedelta(hours=expiration_hours)

        session = Session(
            session_id=session_id,
            user_id=user.user_id,
            created_at=now,
            expires_at=expires_at,
            last_accessed=now,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return await self.session_store.create_session(session)

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        return await self.session_store.get_session(session_id)

    async def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        return await self.session_store.delete_session(session_id)

    async def require_permission(self, user: User, permission: Permission):
        """Check if user has permission"""
        if not user.has_permission(permission):
            logger.warning(f"User {user.username} denied access to {permission.value}")
            raise PermissionError(f"User does not have permission: {permission.value}")

    async def require_any_permission(self, user: User, permissions: List[Permission]):
        """Check if user has any of the permissions"""
        if not user.has_any_permission(permissions):
            logger.warning(f"User {user.username} denied access to any of: {[p.value for p in permissions]}")
            raise PermissionError(
                f"User does not have any of the required permissions: {[p.value for p in permissions]}"
            )

    async def require_role(self, user: User, role: Role):
        """Check if user has role"""
        if user.role != role:
            logger.warning(f"User {user.username} denied access - requires role {role.value}")
            raise PermissionError(f"User does not have required role: {role.value}")

    def check_permission(self, user: Optional[User], permission: Permission) -> bool:
        """Synchronous permission check"""
        if user is None:
            return False
        return user.has_permission(permission)


# Role-based access control (RBAC)
class RoleBasedAccessControl:
    """Role-based access control"""

    # Default permissions for roles
    ROLE_PERMISSIONS = {
        Role.ADMIN: set(Permission),  # Admin has all permissions
        Role.USER: {
            Permission.CONTENT_CREATE,
            Permission.CONTENT_READ,
            Permission.CONTENT_UPDATE,
            Permission.API_ACCESS,
        },
        Role.READ_ONLY: {
            Permission.CONTENT_READ,
            Permission.API_ACCESS,
        },
        Role.GUEST: {
            Permission.CONTENT_READ,
        },
    }

    @staticmethod
    def get_default_permissions(role: Role) -> Set[Permission]:
        """Get default permissions for a role"""
        return RoleBasedAccessControl.ROLE_PERMISSIONS.get(role, set())

    @staticmethod
    def assign_role(user: User, role: Role):
        """Assign role to user (includes default permissions)"""
        user.role = role
        user.permissions = RoleBasedAccessControl.get_default_permissions(role)


# Global instances
_user_store = InMemoryUserStore()
_session_store = InMemorySessionStore()
_auth_manager = AuthManager(_user_store, _session_store)


def get_auth_manager() -> AuthManager:
    """Get global auth manager"""
    return _auth_manager


def get_user_store() -> UserStore:
    """Get global user store"""
    return _user_store


def get_session_store() -> SessionStore:
    """Get global session store"""
    return _session_store


# Decorators
def require_permission(permission: Permission):
    """Decorator to require specific permission"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get user from first argument (assumes self or first param is user)
            user = None
            if args:
                if hasattr(args[0], "user"):
                    user = args[0].user
                elif isinstance(args[0], User):
                    user = args[0]

            if user:
                auth_manager = get_auth_manager()
                await auth_manager.require_permission(user, permission)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(role: Role):
    """Decorator to require specific role"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get user from first argument
            user = None
            if args:
                if hasattr(args[0], "user"):
                    user = args[0].user
                elif isinstance(args[0], User):
                    user = args[0]

            if user:
                auth_manager = get_auth_manager()
                await auth_manager.require_role(user, role)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Example usage
if __name__ == "__main__":
    import asyncio

    async def example():
        # Get auth manager
        auth = get_auth_manager()

        # Create admin user
        admin_user = User(
            user_id="admin1",
            username="admin",
            email="admin@example.com",
            role=Role.ADMIN,
            permissions=set(),
            created_at=datetime.now(),
        )

        # Assign admin role (which gives all permissions)
        RoleBasedAccessControl.assign_role(admin_user, Role.ADMIN)

        # Create user
        await auth.user_store.create_user(admin_user, "AdminPassword123!")

        # Authenticate
        user = await auth.authenticate("admin", "AdminPassword123!")
        print(f"Authenticated user: {user.username}")

        # Create session
        session = await auth.create_session(user, "127.0.0.1", "Mozilla/5.0")
        print(f"Created session: {session.session_id}")

        # Check permission
        try:
            await auth.require_permission(user, Permission.SYSTEM_ADMIN)
            print("User has system:admin permission")
        except PermissionError as e:
            print(f"Permission denied: {e}")

    asyncio.run(example())
