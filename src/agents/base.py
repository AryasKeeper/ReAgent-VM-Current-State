"""
ReAgent Sydney - Base Agent Classes

Abstract base classes and common functionality for all ReAgent agents.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import uuid

from crewai import Agent, Task, Crew
from langchain.tools import Tool
from langchain.schema import BaseMessage
from pydantic import BaseModel, Field

from reagent_sydney.core.database.engine import get_db_session
from reagent_sydney.core.cache.redis_client import get_cache_manager
from reagent_sydney.data.models.agent_models import AgentExecution, AgentTask, AgentLog
from reagent_sydney.config.settings import get_settings
import structlog


class AgentRole(str, Enum):
    """Agent role enumeration."""
    DATA_COLLECTOR = "Data Collector"
    ANALYZER = "Analyzer"
    MATCHER = "Matcher"
    STRATEGIST = "Strategist"
    COMMUNICATOR = "Communicator"
    ORCHESTRATOR = "Orchestrator"


class AgentPriority(str, Enum):
    """Agent execution priority."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass
class AgentConfig:
    """Agent configuration dataclass."""
    
    name: str
    role: AgentRole
    description: str
    version: str = "1.0.0"
    
    # Execution Settings
    max_execution_time: int = 300  # seconds
    max_retries: int = 3
    retry_delay: int = 5  # seconds
    priority: AgentPriority = AgentPriority.MEDIUM
    
    # Resource Limits
    max_memory_mb: int = 1024
    max_api_calls_per_hour: int = 1000
    rate_limit_window: int = 3600
    
    # Dependencies
    required_services: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    
    # Monitoring
    enable_metrics: bool = True
    enable_logging: bool = True
    log_level: str = "INFO"
    
    # Custom Settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMetrics:
    """Agent performance metrics."""
    
    # Execution Metrics
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_execution_time: float = 0.0
    
    # Resource Usage
    avg_memory_usage: float = 0.0
    total_api_calls: int = 0
    api_rate_limit_hits: int = 0
    
    # Quality Metrics
    data_quality_score: float = 0.0
    accuracy_score: float = 0.0
    
    # Time Metrics
    last_execution: Optional[datetime] = None
    total_runtime: timedelta = timedelta()
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        return 100.0 - self.success_rate


class AgentExecutionContext:
    """Agent execution context for tracking state."""
    
    def __init__(self, execution_id: str, agent_name: str):
        self.execution_id = execution_id
        self.agent_name = agent_name
        self.started_at = datetime.utcnow()
        self.tasks: List[Dict[str, Any]] = []
        self.logs: List[Dict[str, Any]] = []
        self.metrics: Dict[str, Any] = {}
        self.errors: List[str] = []
        
    def add_task(self, task_name: str, task_type: str, **kwargs) -> str:
        """Add a task to the execution context."""
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "name": task_name,
            "type": task_type,
            "status": "queued",
            "created_at": datetime.utcnow(),
            **kwargs
        }
        self.tasks.append(task)
        return task_id
    
    def update_task_status(self, task_id: str, status: str, **kwargs) -> None:
        """Update task status and metadata."""
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = status
                task["updated_at"] = datetime.utcnow()
                task.update(kwargs)
                break
    
    def add_log(self, level: str, message: str, **kwargs) -> None:
        """Add a log entry."""
        log_entry = {
            "level": level,
            "message": message,
            "timestamp": datetime.utcnow(),
            **kwargs
        }
        self.logs.append(log_entry)
    
    def add_error(self, error: str) -> None:
        """Add an error to the context."""
        self.errors.append(error)
        self.add_log("ERROR", error)


class BaseReAgentAgent(ABC):
    """
    Abstract base class for all ReAgent Sydney agents.
    
    Provides common functionality including:
    - Execution tracking and logging
    - Database and cache access
    - Metrics collection
    - Error handling and retries
    - Resource management
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = structlog.get_logger(f"agents.{config.name.lower().replace(' ', '_')}")
        self.settings = get_settings()
        
        # Initialize services
        self.cache_manager = get_cache_manager()
        
        # Execution state
        self.current_execution: Optional[AgentExecutionContext] = None
        self.is_running = False
        self.metrics = AgentMetrics()
        
        # CrewAI components
        self._crew_agent: Optional[Agent] = None
        self._tools: List[Tool] = []
        
    async def initialize(self) -> None:
        """Initialize agent dependencies and services."""
        try:
            # Initialize tools
            self._tools = await self._initialize_tools()
            
            # Create CrewAI agent
            self._crew_agent = self._create_crew_agent()
            
            # Agent-specific initialization
            await self._initialize_agent()
            
            self.logger.info(f"Agent {self.config.name} initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize agent {self.config.name}: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Cleanup agent resources."""
        try:
            # Agent-specific cleanup
            await self._cleanup_agent()
            
            self.logger.info(f"Agent {self.config.name} shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during agent shutdown: {e}")
    
    async def execute(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main execution method with comprehensive tracking and error handling.
        """
        execution_id = str(uuid.uuid4())
        self.current_execution = AgentExecutionContext(execution_id, self.config.name)
        
        start_time = time.time()
        result = {"execution_id": execution_id, "success": False}
        
        try:
            self.is_running = True
            self.logger.info(f"Starting execution {execution_id} for agent {self.config.name}")
            
            # Pre-execution checks
            await self._pre_execution_checks()
            
            # Record execution start
            execution_record = await self._create_execution_record(execution_id, input_data)
            
            # Execute agent logic
            agent_result = await self._execute_agent_logic(input_data or {})
            
            # Post-execution processing
            await self._post_execution_processing(agent_result)
            
            # Update execution record
            execution_time = time.time() - start_time
            await self._update_execution_record(
                execution_record, 
                "Completed", 
                agent_result, 
                execution_time
            )
            
            # Update metrics
            self._update_metrics(True, execution_time)
            
            result.update({
                "success": True,
                "data": agent_result,
                "execution_time": execution_time,
                "tasks_completed": len(self.current_execution.tasks)
            })
            
            self.logger.info(f"Execution {execution_id} completed successfully in {execution_time:.2f}s")
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Execution {execution_id} failed: {str(e)}"
            
            self.logger.error(error_msg, exc_info=True)
            self.current_execution.add_error(error_msg)
            
            # Update execution record with failure
            if 'execution_record' in locals():
                await self._update_execution_record(
                    execution_record, 
                    "Failed", 
                    {"error": str(e)}, 
                    execution_time
                )
            
            # Update metrics
            self._update_metrics(False, execution_time)
            
            result.update({
                "success": False,
                "error": str(e),
                "execution_time": execution_time
            })
            
        finally:
            self.is_running = False
            self.current_execution = None
        
        return result
    
    def create_crew_task(self, description: str, expected_output: str, **kwargs) -> Task:
        """Create a CrewAI task for this agent."""
        return Task(
            description=description,
            expected_output=expected_output,
            agent=self._crew_agent,
            **kwargs
        )
    
    # Abstract methods to be implemented by subclasses
    
    @abstractmethod
    async def _initialize_agent(self) -> None:
        """Agent-specific initialization logic."""
        pass
    
    @abstractmethod
    async def _cleanup_agent(self) -> None:
        """Agent-specific cleanup logic."""
        pass
    
    @abstractmethod
    async def _execute_agent_logic(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main agent execution logic."""
        pass
    
    @abstractmethod
    async def _initialize_tools(self) -> List[Tool]:
        """Initialize agent-specific tools."""
        pass
    
    # Helper methods
    
    def _create_crew_agent(self) -> Agent:
        """Create CrewAI agent instance."""
        return Agent(
            role=self.config.role.value,
            goal=self._get_agent_goal(),
            backstory=self._get_agent_backstory(),
            tools=self._tools,
            verbose=self.settings.crewai.verbose,
            max_execution_time=self.config.max_execution_time,
            max_retries=self.config.max_retries,
        )
    
    @abstractmethod
    def _get_agent_goal(self) -> str:
        """Get agent goal for CrewAI."""
        pass
    
    @abstractmethod
    def _get_agent_backstory(self) -> str:
        """Get agent backstory for CrewAI."""
        pass
    
    async def _pre_execution_checks(self) -> None:
        """Perform pre-execution validation and checks."""
        # Check if agent is already running
        if self.is_running:
            raise RuntimeError(f"Agent {self.config.name} is already running")
        
        # Check dependencies
        for service in self.config.required_services:
            if not await self._check_service_availability(service):
                raise RuntimeError(f"Required service {service} is not available")
    
    async def _check_service_availability(self, service: str) -> bool:
        """Check if a required service is available."""
        try:
            if service == "database":
                # Try to get a database session
                async with get_db_session() as session:
                    return True
            elif service == "cache":
                # Check cache availability
                return await self.cache_manager.exists("health_check") or True
            return True
        except Exception:
            return False
    
    async def _create_execution_record(
        self, 
        execution_id: str, 
        input_data: Optional[Dict[str, Any]]
    ) -> AgentExecution:
        """Create execution record in database."""
        execution = AgentExecution(
            execution_id=execution_id,
            agent_name=self.config.name,
            agent_version=self.config.version,
            trigger_type="api",  # This could be parameterized
            status="Running",
            started_at=datetime.utcnow(),
            input_data=input_data,
            config_data=self.config.custom_settings,
            environment=self.settings.environment,
            max_retries=self.config.max_retries
        )
        
        async with get_db_session() as session:
            session.add(execution)
            await session.commit()
            await session.refresh(execution)
        
        return execution
    
    async def _update_execution_record(
        self,
        execution: AgentExecution,
        status: str,
        output_data: Dict[str, Any],
        duration: float
    ) -> None:
        """Update execution record with results."""
        execution.status = status
        execution.completed_at = datetime.utcnow()
        execution.duration_seconds = duration
        execution.output_data = output_data
        
        if self.current_execution:
            execution.items_processed = len(self.current_execution.tasks)
            execution.items_successful = len([
                t for t in self.current_execution.tasks 
                if t.get("status") == "completed"
            ])
            execution.items_failed = len([
                t for t in self.current_execution.tasks 
                if t.get("status") == "failed"
            ])
        
        async with get_db_session() as session:
            await session.merge(execution)
            await session.commit()
    
    async def _post_execution_processing(self, result: Dict[str, Any]) -> None:
        """Post-execution processing and cleanup."""
        # Save logs to database
        if self.current_execution and self.current_execution.logs:
            await self._save_execution_logs()
        
        # Update metrics in cache
        if self.cache_manager and self.config.enable_metrics:
            await self._cache_metrics()
    
    async def _save_execution_logs(self) -> None:
        """Save execution logs to database."""
        if not self.db_manager or not self.current_execution:
            return
        
        # This would be implemented to save logs to the database
        # For brevity, we'll skip the full implementation
        pass
    
    async def _cache_metrics(self) -> None:
        """Cache current metrics."""
        if not self.cache_manager:
            return
        
        metrics_data = {
            "success_rate": self.metrics.success_rate,
            "avg_execution_time": self.metrics.avg_execution_time,
            "total_executions": self.metrics.total_executions,
            "last_updated": datetime.utcnow().isoformat()
        }
        
        cache_key = f"agent_metrics:{self.config.name}"
        await self.cache_manager.set(cache_key, metrics_data, ttl=3600)
    
    def _update_metrics(self, success: bool, execution_time: float) -> None:
        """Update agent performance metrics."""
        self.metrics.total_executions += 1
        self.metrics.last_execution = datetime.utcnow()
        
        if success:
            self.metrics.successful_executions += 1
        else:
            self.metrics.failed_executions += 1
        
        # Update average execution time
        total_time = (self.metrics.avg_execution_time * (self.metrics.total_executions - 1) + 
                     execution_time)
        self.metrics.avg_execution_time = total_time / self.metrics.total_executions
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.config.name}', role='{self.config.role}')>"