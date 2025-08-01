"""JWT token handling for ReAgent Sydney authentication."""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from pydantic import ValidationError

from ...config.settings import settings
from .models import TokenData, UserRole


class JWTHandler:
    """Handles JWT token creation, validation, and management."""
    
    # JWT Configuration
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    @classmethod
    def create_access_token(
        cls,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a new JWT access token.
        
        Args:
            data: Payload data to encode in token
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        # Set expiration time
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        # Encode token with secret key
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.secret_key, 
            algorithm=cls.ALGORITHM
        )
        
        return encoded_jwt
    
    @classmethod
    def create_refresh_token(
        cls,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a new JWT refresh token.
        
        Args:
            data: Payload data to encode in token
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT refresh token string
        """
        to_encode = data.copy()
        
        # Set expiration time (longer for refresh tokens)
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=cls.REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        # Encode token with secret key
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.secret_key, 
            algorithm=cls.ALGORITHM
        )
        
        return encoded_jwt
    
    @classmethod
    def verify_token(cls, token: str) -> TokenData:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token string to verify
            
        Returns:
            TokenData object with decoded payload
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            # Decode token
            payload = jwt.decode(
                token, 
                settings.secret_key, 
                algorithms=[cls.ALGORITHM]
            )
            
            # Extract user information
            username: Optional[str] = payload.get("sub")
            user_id: Optional[int] = payload.get("user_id")
            role: Optional[str] = payload.get("role")
            scopes: List[str] = payload.get("scopes", [])
            token_type: Optional[str] = payload.get("type", "access")
            
            # Validate required fields
            if username is None or user_id is None:
                raise credentials_exception
            
            # Create token data
            token_data = TokenData(
                username=username,
                user_id=user_id,
                role=UserRole(role) if role else None,
                scopes=scopes
            )
            
            return token_data
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTError:
            raise credentials_exception
        except ValidationError:
            raise credentials_exception
    
    @classmethod
    def decode_token_payload(cls, token: str) -> Dict[str, Any]:
        """
        Decode token payload without verification (for debugging).
        
        Args:
            token: JWT token string
            
        Returns:
            Dictionary with token payload
        """
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except jwt.DecodeError:
            return {}
    
    @classmethod
    def is_token_expired(cls, token: str) -> bool:
        """
        Check if a token is expired.
        
        Args:
            token: JWT token string
            
        Returns:
            True if token is expired, False otherwise
        """
        try:
            payload = cls.decode_token_payload(token)
            exp = payload.get("exp")
            if exp:
                return datetime.utcnow() > datetime.fromtimestamp(exp)
            return True
        except Exception:
            return True
    
    @classmethod
    def get_token_scopes(cls, token: str) -> List[str]:
        """
        Get scopes from a token.
        
        Args:
            token: JWT token string
            
        Returns:
            List of scopes
        """
        try:
            payload = cls.decode_token_payload(token)
            return payload.get("scopes", [])
        except Exception:
            return []


# Convenience functions
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a new access token."""
    return JWTHandler.create_access_token(data, expires_delta)


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a new refresh token."""
    return JWTHandler.create_refresh_token(data, expires_delta)


def verify_token(token: str) -> TokenData:
    """Verify and decode a JWT token."""
    return JWTHandler.verify_token(token)