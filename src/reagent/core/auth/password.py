"""Password hashing and verification utilities."""

import secrets
import bcrypt
from typing import Optional


class PasswordSecurity:
    """Secure password handling with bcrypt."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt with salt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
        """
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=12)  # High cost factor for security
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Previously hashed password
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'), 
                hashed_password.encode('utf-8')
            )
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        Generate a cryptographically secure random token.
        
        Args:
            length: Token length in bytes
            
        Returns:
            Hex-encoded secure token
        """
        return secrets.token_hex(length)
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """
        Validate password meets security requirements.
        
        Args:
            password: Password to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if len(password) > 128:
            return False, "Password cannot be longer than 128 characters"
        
        # Check for required character types
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        if not has_upper:
            return False, "Password must contain at least one uppercase letter"
        
        if not has_lower:
            return False, "Password must contain at least one lowercase letter"
        
        if not has_digit:
            return False, "Password must contain at least one digit"
        
        if not has_special:
            return False, "Password must contain at least one special character"
        
        # Check for common weak patterns
        weak_patterns = [
            "password", "123456", "qwerty", "admin", "root", 
            "user", "test", "guest", "demo", "reagent"
        ]
        
        password_lower = password.lower()
        for pattern in weak_patterns:
            if pattern in password_lower:
                return False, f"Password cannot contain common weak patterns"
        
        return True, ""


# Convenience functions for backward compatibility
def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return PasswordSecurity.hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return PasswordSecurity.verify_password(plain_password, hashed_password)


def generate_api_key() -> str:
    """Generate a secure API key."""
    return PasswordSecurity.generate_secure_token(32)