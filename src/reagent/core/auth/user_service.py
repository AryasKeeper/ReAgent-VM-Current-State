"""User service for authentication operations."""

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.exc import IntegrityError

from .models import User, UserCreate, UserUpdate, UserRole
from .password import get_password_hash, verify_password, generate_api_key


class UserService:
    """Service class for user operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def create_user(self, user_create: UserCreate) -> User:
        """
        Create a new user.
        
        Args:
            user_create: User creation data
            
        Returns:
            Created user
            
        Raises:
            ValueError: If user already exists or validation fails
        """
        # Validate password match
        user_create.validate_passwords_match()
        
        # Check if user already exists
        existing_user = await self.get_user_by_username(user_create.username)
        if existing_user:
            raise ValueError("Username already exists")
        
        existing_email = await self.get_user_by_email(user_create.email)
        if existing_email:
            raise ValueError("Email already exists")
        
        # Hash password
        hashed_password = get_password_hash(user_create.password)
        
        # Create user
        db_user = User(
            email=user_create.email,
            username=user_create.username,
            hashed_password=hashed_password,
            full_name=user_create.full_name,
            role=user_create.role,
            is_active=True,
            is_verified=False,  # Require email verification
            created_at=datetime.utcnow()
        )
        
        try:
            self.db.add(db_user)
            await self.db.commit()
            await self.db.refresh(db_user)
            return db_user
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("User creation failed due to constraint violation")
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user with username and password.
        
        Args:
            username: Username or email
            password: Plain text password
            
        Returns:
            User if authentication successful, None otherwise
        """
        # Get user by username or email
        user = await self.get_user_by_username(username)
        if not user:
            user = await self.get_user_by_email(username)
        
        if not user:
            return None
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            return None
        
        # Verify password
        if not verify_password(password, user.hashed_password):
            # Increment failed login attempts
            await self._increment_failed_login(user.id)
            return None
        
        # Reset failed login attempts on successful login
        await self._reset_failed_login(user.id)
        
        return user
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """Get user by API key."""
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.api_key == api_key,
                    User.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def update_user(self, user_id: int, user_update: UserUpdate) -> Optional[User]:
        """
        Update user information.
        
        Args:
            user_id: User ID to update
            user_update: Update data
            
        Returns:
            Updated user or None if not found
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
        
        # Update fields
        update_data = user_update.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        try:
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("User update failed due to constraint violation")
    
    async def delete_user(self, user_id: int) -> bool:
        """
        Delete a user (soft delete by deactivating).
        
        Args:
            user_id: User ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.is_active = False
        await self.db.commit()
        return True
    
    async def update_last_login(self, user_id: int) -> None:
        """Update user's last login timestamp."""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login=datetime.utcnow())
        )
        await self.db.commit()
    
    async def create_api_key(self, user_id: int, expires_days: int = 365) -> str:
        """
        Create an API key for a user.
        
        Args:
            user_id: User ID
            expires_days: API key expiration in days
            
        Returns:
            Generated API key
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Generate API key
        api_key = generate_api_key()
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        # Update user with API key
        user.api_key = api_key
        user.api_key_expires = expires_at
        
        await self.db.commit()
        return api_key
    
    async def revoke_api_key(self, user_id: int) -> bool:
        """
        Revoke user's API key.
        
        Args:
            user_id: User ID
            
        Returns:
            True if revoked, False if user not found
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.api_key = None
        user.api_key_expires = None
        
        await self.db.commit()
        return True
    
    async def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """
        Change user password.
        
        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password
            
        Returns:
            True if password changed, False if validation failed
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        # Verify old password
        if not verify_password(old_password, user.hashed_password):
            return False
        
        # Hash new password
        new_hashed_password = get_password_hash(new_password)
        user.hashed_password = new_hashed_password
        
        await self.db.commit()
        return True
    
    async def list_users(
        self, 
        skip: int = 0, 
        limit: int = 100,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None
    ) -> List[User]:
        """
        List users with optional filtering.
        
        Args:
            skip: Number of users to skip
            limit: Maximum number of users to return
            role: Filter by role
            is_active: Filter by active status
            
        Returns:
            List of users
        """
        query = select(User)
        
        # Apply filters
        if role is not None:
            query = query.where(User.role == role)
        
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def _increment_failed_login(self, user_id: int) -> None:
        """Increment failed login attempts and lock account if necessary."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return
        
        user.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts for 15 minutes
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        
        await self.db.commit()
    
    async def _reset_failed_login(self, user_id: int) -> None:
        """Reset failed login attempts."""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                failed_login_attempts=0,
                locked_until=None,
                last_login=datetime.utcnow()
            )
        )
        await self.db.commit()