"""Authentication API routes for ReAgent Sydney."""

from datetime import timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_database
from ...core.auth import (
    UserService, UserCreate, UserLogin, UserResponse, UserUpdate,
    Token, APIKeyCreate, APIKeyResponse, User, UserRole,
    create_access_token, create_refresh_token,
    get_current_active_user, require_admin, require_role
)
from ...utils.logging import get_reagent_logger

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = get_reagent_logger("auth_api")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_create: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_database)
):
    """
    Register a new user account.
    
    - **email**: Valid email address
    - **username**: Unique username (3-50 characters, alphanumeric + underscore/dash)
    - **password**: Strong password (8+ characters, mixed case, numbers, special chars)
    - **full_name**: Optional full name
    - **role**: User role (default: viewer)
    """
    try:
        user_service = UserService(db)
        
        # Create user
        new_user = await user_service.create_user(user_create)
        
        logger.info(
            "User registered successfully",
            user_id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            role=new_user.role.value
        )
        
        # TODO: Send verification email in background
        # background_tasks.add_task(send_verification_email, new_user.email)
        
        return UserResponse.from_orm(new_user)
        
    except ValueError as e:
        logger.warning(
            "User registration failed",
            error=str(e),
            username=user_create.username,
            email=user_create.email
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "User registration error",
            error=str(e),
            username=user_create.username,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=Token)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_database)
):
    """
    Authenticate user and return JWT tokens.
    
    - **username**: Username or email address
    - **password**: User password
    
    Returns access and refresh tokens for API authentication.
    """
    try:
        user_service = UserService(db)
        
        # Authenticate user
        user = await user_service.authenticate_user(
            form_data.username,
            form_data.password
        )
        
        if not user:
            logger.warning(
                "Login attempt failed",
                username=form_data.username,
                reason="invalid_credentials"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            logger.warning(
                "Login attempt failed",
                username=form_data.username,
                user_id=user.id,
                reason="account_disabled"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled"
            )
        
        # Create tokens
        token_data = {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value,
            "scopes": form_data.scopes if form_data.scopes else []
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"sub": user.username, "user_id": user.id})
        
        logger.info(
            "User logged in successfully",
            user_id=user.id,
            username=user.username,
            role=user.role.value
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=30 * 60,  # 30 minutes
            refresh_token=refresh_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Login error",
            error=str(e),
            username=form_data.username,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_database)
):
    """
    Refresh access token using refresh token.
    
    - **refresh_token**: Valid refresh token
    
    Returns new access and refresh tokens.
    """
    try:
        from ...core.auth.jwt_handler import verify_token
        
        # Verify refresh token
        token_data = verify_token(refresh_token)
        
        # Get user
        user_service = UserService(db)
        user = await user_service.get_user_by_id(token_data.user_id)
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Create new tokens
        new_token_data = {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value,
            "scopes": token_data.scopes
        }
        
        new_access_token = create_access_token(new_token_data)
        new_refresh_token = create_refresh_token({"sub": user.username, "user_id": user.id})
        
        logger.info(
            "Token refreshed successfully",
            user_id=user.id,
            username=user.username
        )
        
        return Token(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=30 * 60,
            refresh_token=new_refresh_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information."""
    return UserResponse.from_orm(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database)
):
    """Update current user information."""
    try:
        user_service = UserService(db)
        
        # Prevent role elevation (only admins can change roles)
        if user_update.role and current_user.role != UserRole.ADMIN:
            user_update.role = None
        
        updated_user = await user_service.update_user(current_user.id, user_update)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(
            "User updated profile",
            user_id=current_user.id,
            username=current_user.username
        )
        
        return UserResponse.from_orm(updated_user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "User update error",
            error=str(e),
            user_id=current_user.id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User update failed"
        )


@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database)
):
    """Change user password."""
    try:
        from ...core.auth.password import PasswordSecurity
        
        # Validate new password strength
        is_valid, error_message = PasswordSecurity.validate_password_strength(new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        user_service = UserService(db)
        success = await user_service.change_password(
            current_user.id,
            old_password,
            new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        logger.info(
            "User changed password",
            user_id=current_user.id,
            username=current_user.username
        )
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Password change error",
            error=str(e),
            user_id=current_user.id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.post("/api-key", response_model=APIKeyResponse)
async def create_api_key(
    api_key_create: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database)
):
    """Create an API key for the current user."""
    try:
        user_service = UserService(db)
        
        api_key = await user_service.create_api_key(
            current_user.id,
            api_key_create.expires_days
        )
        
        logger.info(
            "API key created",
            user_id=current_user.id,
            username=current_user.username,
            expires_days=api_key_create.expires_days
        )
        
        return APIKeyResponse(
            name=api_key_create.name,
            key=api_key,
            expires_at=current_user.api_key_expires,
            created_at=datetime.utcnow(),
            scopes=api_key_create.scopes
        )
        
    except Exception as e:
        logger.error(
            "API key creation error",
            error=str(e),
            user_id=current_user.id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key creation failed"
        )


@router.delete("/api-key")
async def revoke_api_key(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_database)
):
    """Revoke the current user's API key."""
    try:
        user_service = UserService(db)
        success = await user_service.revoke_api_key(current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No API key found"
            )
        
        logger.info(
            "API key revoked",
            user_id=current_user.id,
            username=current_user.username
        )
        
        return {"message": "API key revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "API key revocation error",
            error=str(e),
            user_id=current_user.id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key revocation failed"
        )


# Admin-only endpoints
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_database)
):
    """List all users (admin only)."""
    try:
        user_service = UserService(db)
        users = await user_service.list_users(skip, limit, role, is_active)
        
        return [UserResponse.from_orm(user) for user in users]
        
    except Exception as e:
        logger.error("List users error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user_admin(
    user_id: int,
    user_update: UserUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_database)
):
    """Update any user (admin only)."""
    try:
        user_service = UserService(db)
        updated_user = await user_service.update_user(user_id, user_update)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(
            "Admin updated user",
            admin_user_id=_.id,
            target_user_id=user_id,
            updated_fields=user_update.dict(exclude_unset=True)
        )
        
        return UserResponse.from_orm(updated_user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Admin user update error",
            error=str(e),
            user_id=user_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User update failed"
        )


@router.delete("/users/{user_id}")
async def delete_user_admin(
    user_id: int,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_database)
):
    """Delete/deactivate user (admin only)."""
    try:
        user_service = UserService(db)
        success = await user_service.delete_user(user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(
            "Admin deleted user",
            admin_user_id=_.id,
            target_user_id=user_id
        )
        
        return {"message": "User deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Admin user deletion error",
            error=str(e),
            user_id=user_id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User deletion failed"
        )