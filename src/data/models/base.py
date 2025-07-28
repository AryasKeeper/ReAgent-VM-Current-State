"""
ReAgent Sydney - Base Model Classes

Base SQLAlchemy models with common functionality and mixins.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import Session


class BaseModel:
    """Base model class with common functionality."""
    
    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        return cls.__name__.lower()
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
        doc="Unique identifier"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update(self, **kwargs: Any) -> None:
        """Update model instance with provided values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    def create(cls, session: Session, **kwargs: Any) -> "BaseModel":
        """Create and save new model instance."""
        instance = cls(**kwargs)
        session.add(instance)
        session.commit()
        session.refresh(instance)
        return instance
    
    def save(self, session: Session) -> "BaseModel":
        """Save model instance to database."""
        session.add(self)
        session.commit()
        session.refresh(self)
        return self
    
    def delete(self, session: Session) -> None:
        """Delete model instance from database."""
        session.delete(self)
        session.commit()


class TimestampMixin:
    """Mixin for adding timestamp fields."""
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Record creation timestamp"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Record last update timestamp"
    )


class AuditMixin:
    """Mixin for audit trail functionality."""
    
    created_by = Column(
        String(255),
        nullable=True,
        doc="User who created the record"
    )
    
    updated_by = Column(
        String(255),
        nullable=True,
        doc="User who last updated the record"
    )
    
    version = Column(
        String(50),
        nullable=True,
        doc="Record version for optimistic locking"
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Soft deletion timestamp"
    )
    
    is_deleted = Column(
        String(1),
        default="N",
        nullable=False,
        doc="Soft deletion flag (Y/N)"
    )
    
    def soft_delete(self, session: Session) -> None:
        """Soft delete the record."""
        self.deleted_at = datetime.utcnow()
        self.is_deleted = "Y"
        session.commit()
    
    def restore(self, session: Session) -> None:
        """Restore soft deleted record."""
        self.deleted_at = None
        self.is_deleted = "N"
        session.commit()
    
    @property
    def is_active(self) -> bool:
        """Check if record is active (not soft deleted)."""
        return self.is_deleted == "N"


# Create base model class with declarative_base
Base = declarative_base(cls=BaseModel)