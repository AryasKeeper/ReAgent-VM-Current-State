"""
ReAgent Sydney - Agent Orchestration Models

SQLAlchemy models for tracking agent executions, tasks, and performance.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Numeric, Text, DateTime, Boolean, 
    ForeignKey, Index, CheckConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from .base import Base, TimestampMixin


class ExecutionStatus(str, Enum):
    """Agent execution status enumeration."""
    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    TIMEOUT = "Timeout"


class TaskStatus(str, Enum):
    """Agent task status enumeration."""
    QUEUED = "Queued"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    FAILED = "Failed" 
    RETRYING = "Retrying"
    CANCELLED = "Cancelled"


class LogLevel(str, Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AgentExecution(Base, TimestampMixin):
    """Agent execution tracking and orchestration."""
    
    __tablename__ = "agent_executions"
    
    # Execution Identification
    execution_id = Column(String(100), nullable=False, unique=True, doc="Unique execution identifier")
    agent_name = Column(String(100), nullable=False, index=True, doc="Agent class name")
    agent_version = Column(String(20), nullable=False, doc="Agent version")
    
    # Execution Context
    trigger_type = Column(String(50), nullable=False, doc="What triggered execution")
    trigger_source = Column(String(100), nullable=True, doc="Source of trigger")
    parent_execution_id = Column(String(100), nullable=True, doc="Parent execution if chained")
    
    # Execution Status
    status = Column(String(20), default="Pending", nullable=False, doc="Execution status")
    started_at = Column(DateTime(timezone=True), nullable=True, doc="Execution start time")
    completed_at = Column(DateTime(timezone=True), nullable=True, doc="Execution completion time")
    
    # Performance Metrics
    duration_seconds = Column(Numeric(10, 3), nullable=True, doc="Execution duration")
    cpu_time_seconds = Column(Numeric(10, 3), nullable=True, doc="CPU time used")
    memory_usage_mb = Column(Numeric(10, 2), nullable=True, doc="Peak memory usage")
    
    # Input/Output
    input_data = Column(JSONB, nullable=True, doc="Execution input parameters")
    output_data = Column(JSONB, nullable=True, doc="Execution output results")
    config_data = Column(JSONB, nullable=True, doc="Agent configuration")
    
    # Results & Metrics
    items_processed = Column(Integer, nullable=True, doc="Number of items processed")
    items_successful = Column(Integer, nullable=True, doc="Number of successful items")
    items_failed = Column(Integer, nullable=True, doc="Number of failed items")
    
    # Error Handling
    error_message = Column(Text, nullable=True, doc="Error message if failed")
    error_details = Column(JSONB, nullable=True, doc="Detailed error information")
    retry_count = Column(Integer, default=0, doc="Number of retry attempts")
    max_retries = Column(Integer, default=3, doc="Maximum retry attempts")
    
    # Quality Metrics
    success_rate = Column(Numeric(5, 2), nullable=True, doc="Success rate percentage")
    data_quality_score = Column(Numeric(3, 2), nullable=True, doc="Data quality score")
    performance_score = Column(Numeric(3, 2), nullable=True, doc="Performance score")
    
    # Resource Usage
    api_calls_made = Column(Integer, nullable=True, doc="Number of API calls made")
    api_rate_limit_hits = Column(Integer, nullable=True, doc="Rate limit violations")
    database_queries = Column(Integer, nullable=True, doc="Database queries executed")
    
    # Environment Context
    environment = Column(String(20), nullable=False, doc="Execution environment")
    host_name = Column(String(100), nullable=True, doc="Host machine name")
    process_id = Column(Integer, nullable=True, doc="Process ID")
    
    # Relationships
    tasks = relationship("AgentTask", back_populates="execution", cascade="all, delete-orphan")
    logs = relationship("AgentLog", back_populates="execution", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_execution_agent_time", "agent_name", "created_at"),
        Index("idx_execution_status_time", "status", "created_at"),
        Index("idx_execution_trigger", "trigger_type", "created_at"),
        Index("idx_execution_parent", "parent_execution_id"),
        Index("idx_execution_performance", "duration_seconds", "success_rate"),
    )
    
    @validates("status")
    def validate_status(self, key: str, value: str) -> str:
        """Validate execution status."""
        if value not in [es.value for es in ExecutionStatus]:
            raise ValueError(f"Invalid execution status: {value}")
        return value
    
    @validates("trigger_type")
    def validate_trigger_type(self, key: str, value: str) -> str:
        """Validate trigger type."""
        valid_triggers = ["scheduled", "manual", "webhook", "event", "chained", "retry"]
        if value not in valid_triggers:
            raise ValueError(f"Invalid trigger type: {value}")
        return value
    
    @hybrid_property
    def is_completed(self) -> bool:
        """Check if execution is completed."""
        return self.status in [ExecutionStatus.COMPLETED.value, ExecutionStatus.FAILED.value]
    
    @hybrid_property
    def is_successful(self) -> bool:
        """Check if execution was successful."""
        return self.status == ExecutionStatus.COMPLETED.value
    
    def calculate_duration(self) -> None:
        """Calculate execution duration."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()
    
    def __repr__(self) -> str:
        return f"<AgentExecution(id={self.id}, agent='{self.agent_name}', status='{self.status}')>"


class AgentTask(Base, TimestampMixin):
    """Individual agent task tracking."""
    
    __tablename__ = "agent_tasks"
    
    # Foreign Keys
    execution_id = Column(UUID(as_uuid=True), ForeignKey("agent_executions.id"), nullable=False, index=True)
    
    # Task Identification
    task_name = Column(String(100), nullable=False, doc="Task name or identifier")
    task_type = Column(String(50), nullable=False, doc="Type of task")
    sequence_order = Column(Integer, nullable=True, doc="Task order in sequence")
    
    # Task Status
    status = Column(String(20), default="Queued", nullable=False, doc="Task status")
    assigned_at = Column(DateTime(timezone=True), nullable=True, doc="Task assignment time")
    started_at = Column(DateTime(timezone=True), nullable=True, doc="Task start time")
    completed_at = Column(DateTime(timezone=True), nullable=True, doc="Task completion time")
    
    # Task Details
    description = Column(Text, nullable=True, doc="Task description")
    priority = Column(Integer, default=5, doc="Task priority (1-10)")
    estimated_duration = Column(Integer, nullable=True, doc="Estimated duration in seconds")
    actual_duration = Column(Integer, nullable=True, doc="Actual duration in seconds")
    
    # Input/Output
    input_parameters = Column(JSONB, nullable=True, doc="Task input parameters")
    output_results = Column(JSONB, nullable=True, doc="Task output results")
    
    # Dependencies
    depends_on_tasks = Column(ARRAY(String), nullable=True, doc="List of dependent task IDs")
    blocks_tasks = Column(ARRAY(String), nullable=True, doc="List of blocked task IDs")
    
    # Performance Metrics
    items_processed = Column(Integer, nullable=True, doc="Items processed by task")
    success_count = Column(Integer, nullable=True, doc="Successful operations")
    error_count = Column(Integer, nullable=True, doc="Failed operations")
    
    # Error Handling
    error_message = Column(Text, nullable=True, doc="Error message if failed")
    error_details = Column(JSONB, nullable=True, doc="Detailed error information")
    retry_count = Column(Integer, default=0, doc="Retry attempts")
    
    # Resource Usage
    memory_usage_mb = Column(Numeric(8, 2), nullable=True, doc="Memory usage")
    api_calls = Column(Integer, nullable=True, doc="API calls made")
    
    # Task Metadata (renamed to avoid SQLAlchemy conflict)
    task_metadata = Column(JSONB, nullable=True, doc="Additional task metadata")
    
    # Relationships
    execution = relationship("AgentExecution", back_populates="tasks")
    
    # Indexes
    __table_args__ = (
        Index("idx_task_execution_order", "execution_id", "sequence_order"),
        Index("idx_task_status_time", "status", "created_at"),
        Index("idx_task_type_time", "task_type", "created_at"),
        Index("idx_task_priority", "priority", "created_at"),
        CheckConstraint("priority >= 1 AND priority <= 10", name="chk_priority_valid"),
    )
    
    @validates("status")
    def validate_status(self, key: str, value: str) -> str:
        """Validate task status."""
        if value not in [ts.value for ts in TaskStatus]:
            raise ValueError(f"Invalid task status: {value}")
        return value
    
    @hybrid_property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]
    
    @hybrid_property
    def success_rate(self) -> Optional[float]:
        """Calculate task success rate."""
        if self.success_count is not None and self.error_count is not None:
            total = self.success_count + self.error_count
            if total > 0:
                return (self.success_count / total) * 100
        return None
    
    def __repr__(self) -> str:
        return f"<AgentTask(id={self.id}, name='{self.task_name}', status='{self.status}')>"


class AgentLog(Base, TimestampMixin):
    """Agent execution logging for debugging and monitoring."""
    
    __tablename__ = "agent_logs"
    
    # Foreign Keys
    execution_id = Column(UUID(as_uuid=True), ForeignKey("agent_executions.id"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("agent_tasks.id"), nullable=True, index=True)
    
    # Log Details
    level = Column(String(10), nullable=False, doc="Log level")
    message = Column(Text, nullable=False, doc="Log message")
    logger_name = Column(String(100), nullable=False, doc="Logger name")
    
    # Context Information
    module_name = Column(String(100), nullable=True, doc="Python module name")
    function_name = Column(String(100), nullable=True, doc="Function name")
    line_number = Column(Integer, nullable=True, doc="Line number")
    
    # Additional Data
    extra_data = Column(JSONB, nullable=True, doc="Additional structured data")
    exception_info = Column(JSONB, nullable=True, doc="Exception information")
    stack_trace = Column(Text, nullable=True, doc="Stack trace if error")
    
    # Performance Context
    memory_usage = Column(Numeric(8, 2), nullable=True, doc="Memory usage at log time")
    execution_time_ms = Column(Numeric(10, 3), nullable=True, doc="Execution time in ms")
    
    # Tags and Categories
    tags = Column(ARRAY(String), nullable=True, doc="Log tags")
    category = Column(String(50), nullable=True, doc="Log category")
    
    # Relationships
    execution = relationship("AgentExecution", back_populates="logs")
    
    # Indexes optimized for TimescaleDB
    __table_args__ = (
        Index("idx_log_execution_time", "execution_id", "created_at"),
        Index("idx_log_level_time", "level", "created_at"),
        Index("idx_log_logger_time", "logger_name", "created_at"),
        Index("idx_log_category_time", "category", "created_at"),
    )
    
    @validates("level")
    def validate_level(self, key: str, value: str) -> str:
        """Validate log level."""
        if value not in [ll.value for ll in LogLevel]:
            raise ValueError(f"Invalid log level: {value}")
        return value
    
    @hybrid_property
    def is_error(self) -> bool:
        """Check if this is an error log."""
        return self.level in [LogLevel.ERROR.value, LogLevel.CRITICAL.value]
    
    def __repr__(self) -> str:
        return f"<AgentLog(id={self.id}, level='{self.level}', message='{self.message[:50]}...')>"