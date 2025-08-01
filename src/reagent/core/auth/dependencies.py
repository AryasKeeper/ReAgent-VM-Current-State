"""FastAPI authentication dependencies."""

from datetime import datetime
from typing import Optional, List, Callable
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_database
from .jwt_handler import verify_token
from .models import User, TokenData, UserRole
from .user_service import UserService

# Security schemes
bearer_scheme = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthenticationError(HTTPException):
    """Custom authentication error."""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationError(HTTPException):
    """Custom authorization error."""
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: AsyncSession = Depends(get_database)
) -> User:
    """
    Get current user from JWT token.
    
    Args:
        credentials: Bearer token credentials
        db: Database session
        
    Returns:
        User object
        
    Raises:
        AuthenticationError: If token is invalid or user not found
    """
    try:
        # Verify and decode token
        token_data = verify_token(credentials.credentials)
        
        # Get user from database
        user_service = UserService(db)
        user = await user_service.get_user_by_username(token_data.username)
        
        if user is None:
            raise AuthenticationError("User not found")
        
        # Update last login time
        await user_service.update_last_login(user.id)
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise AuthenticationError(f"Token validation failed: {str(e)}")


async def get_current_user_from_api_key(
    api_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_database)
) -> Optional[User]:
    """
    Get current user from API key.
    
    Args:
        api_key: API key from header
        db: Database session
        
    Returns:
        User object if API key is valid, None otherwise
    """
    if not api_key:
        return None
    
    try:
        user_service = UserService(db)
        user = await user_service.get_user_by_api_key(api_key)
        
        if user and user.api_key_expires and user.api_key_expires < datetime.utcnow():
            # API key expired
            return None
        
        return user
        
    except Exception:
        return None


async def get_current_user(
    token_user: Optional[User] = Depends(get_current_user_from_token),
    api_key_user: Optional[User] = Depends(get_current_user_from_api_key)
) -> User:
    """
    Get current user from either JWT token or API key.
    
    Args:
        token_user: User from JWT token
        api_key_user: User from API key
        
    Returns:
        Authenticated user
        
    Raises:
        AuthenticationError: If no valid authentication provided
    """
    # Try token authentication first
    if token_user:
        return token_user
    
    # Fallback to API key authentication
    if api_key_user:
        return api_key_user
    
    # No valid authentication
    raise AuthenticationError("Valid authentication required")


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (must be active and verified).
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Active user
        
    Raises:
        AuthenticationError: If user is inactive or unverified
    """
    if not current_user.is_active:
        raise AuthenticationError("User account is disabled")
    
    if not current_user.is_verified:
        raise AuthenticationError("User account is not verified")
    
    return current_user


def require_role(required_role: UserRole) -> Callable:
    """
    Create a dependency that requires a specific user role.
    
    Args:
        required_role: Required user role
        
    Returns:
        FastAPI dependency function
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        # Role hierarchy check
        role_hierarchy = {
            UserRole.ADMIN: 4,
            UserRole.AGENT: 3,
            UserRole.ANALYST: 2,
            UserRole.VIEWER: 1,
            UserRole.API_CLIENT: 1
        }
        
        user_level = role_hierarchy.get(current_user.role, 0)
        required_level = role_hierarchy.get(required_role, 999)
        
        if user_level < required_level:
            raise AuthorizationError(
                f"Role '{required_role.value}' or higher required"
            )
        
        return current_user
    
    return role_checker


def require_scopes(required_scopes: List[str]) -> Callable:
    """
    Create a dependency that requires specific token scopes.
    
    Args:
        required_scopes: List of required scopes
        
    Returns:
        FastAPI dependency function
    """
    async def scope_checker(
        credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
    ) -> TokenData:
        # Verify token and get scopes
        token_data = verify_token(credentials.credentials)
        
        # Check if all required scopes are present
        token_scopes = set(token_data.scopes)
        required_scopes_set = set(required_scopes)
        
        if not required_scopes_set.issubset(token_scopes):
            missing_scopes = required_scopes_set - token_scopes
            raise AuthorizationError(
                f"Missing required scopes: {', '.join(missing_scopes)}"
            )
        
        return token_data
    
    return scope_checker


# Convenience role dependencies
require_admin = require_role(UserRole.ADMIN)
require_agent = require_role(UserRole.AGENT)
require_analyst = require_role(UserRole.ANALYST)
require_viewer = require_role(UserRole.VIEWER)