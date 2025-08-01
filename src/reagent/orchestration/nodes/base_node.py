"""
ReAgent Sydney - Base LangGraph Node

Abstract base class for all ReAgent LangGraph nodes with common functionality.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import time

from langchain_core.messages import AIMessage, HumanMessage

from ..state import ReAgentState, AgentStatus, AgentResult, update_agent_result
from ...core.cache.redis_client import get_cache_manager
from ...core.vector_db.client import get_weaviate_client
from ...utils.logging import get_logger
from ...utils.monitoring.metrics import get_metrics_client


class BaseReAgentNode(ABC):
    """
    Abstract base class for all ReAgent LangGraph nodes.
    
    Provides common functionality:
    - State management and updates
    - Error handling and recovery
    - Metrics collection
    - Caching integration
    - Logging and monitoring
    """
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = get_logger(f"nodes.{agent_name.lower().replace(' ', '_')}")
        
        # Initialize services
        self.cache_manager = get_cache_manager()
        self.weaviate_client = get_weaviate_client()
        self.metrics_client = get_metrics_client()
        
        # Node configuration
        self.max_retries = 3
        self.retry_delay = 5.0
        self.timeout = 300.0  # 5 minutes
        
    async def __call__(self, state: ReAgentState) -> ReAgentState:
        """
        Main node execution method with comprehensive error handling.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting {self.agent_name} node execution")
            
            # Update state to show current agent
            state["current_agent"] = self.agent_name
            state["updated_at"] = datetime.utcnow()
            
            # Add message about starting execution
            state["messages"].append(
                HumanMessage(content=f"Starting {self.agent_name} execution")
            )
            
            # Execute the agent logic with retries
            result = await self._execute_with_retries(state)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Create agent result
            agent_result = AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.COMPLETED,
                data=result,
                execution_time=execution_time,
                metadata={
                    "node_type": self.__class__.__name__,
                    "execution_id": state["workflow_id"]
                }
            )
            
            # Update state with result
            state = update_agent_result(state, self.agent_name, agent_result)
            
            # Record metrics
            if self.metrics_client:
                self.metrics_client.increment(
                    "reagent.node.executed",
                    tags=[f"agent:{self.agent_name}", "status:success"]
                )
                self.metrics_client.histogram(
                    "reagent.node.execution_time",
                    execution_time,
                    tags=[f"agent:{self.agent_name}"]
                )
            
            self.logger.info(f"{self.agent_name} node completed successfully in {execution_time:.2f}s")
            
            return state
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"{self.agent_name} node failed: {str(e)}"
            
            self.logger.error(error_msg, exc_info=True)
            
            # Create failure result
            agent_result = AgentResult(
                agent_name=self.agent_name,
                status=AgentStatus.FAILED,
                error=error_msg,
                execution_time=execution_time,
                metadata={
                    "node_type": self.__class__.__name__,
                    "execution_id": state["workflow_id"]
                }
            )
            
            # Update state with failure
            state = update_agent_result(state, self.agent_name, agent_result)
            
            # Record failure metrics
            if self.metrics_client:
                self.metrics_client.increment(
                    "reagent.node.executed",
                    tags=[f"agent:{self.agent_name}", "status:failed"]
                )
            
            return state

    async def _execute_with_retries(self, state: ReAgentState) -> Dict[str, Any]:
        """Execute agent logic with retry mechanism."""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    self._execute_agent_logic(state),
                    timeout=self.timeout
                )
                return result
                
            except asyncio.TimeoutError as e:
                last_exception = e
                self.logger.warning(f"{self.agent_name} execution timed out on attempt {attempt + 1}")
                
            except Exception as e:
                last_exception = e
                self.logger.warning(f"{self.agent_name} execution failed on attempt {attempt + 1}: {e}")
                
                # Wait before retry (except on last attempt)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        # All retries exhausted
        raise last_exception or RuntimeError(f"{self.agent_name} execution failed after {self.max_retries} attempts")

    @abstractmethod
    async def _execute_agent_logic(self, state: ReAgentState) -> Dict[str, Any]:
        """
        Execute the core agent logic.
        
        Args:
            state: Current workflow state
            
        Returns:
            Agent execution result data
        """
        pass

    async def _cache_get(self, key: str) -> Optional[Any]:
        """Get data from Redis cache."""
        try:
            return await self.cache_manager.get(key)
        except Exception as e:
            self.logger.warning(f"Cache get failed for key {key}: {e}")
            return None

    async def _cache_set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set data in Redis cache."""
        try:
            await self.cache_manager.set(key, value, ttl=ttl)
        except Exception as e:
            self.logger.warning(f"Cache set failed for key {key}: {e}")

    async def _vector_search(self, query: str, collection: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Perform vector search in Weaviate."""
        try:
            if not self.weaviate_client:
                return []
                
            results = await self.weaviate_client.search(
                collection=collection,
                query_text=query,
                limit=limit
            )
            return results
            
        except Exception as e:
            self.logger.warning(f"Vector search failed: {e}")
            return []

    def _should_skip_execution(self, state: ReAgentState) -> bool:
        """
        Determine if this node should be skipped based on state.
        
        Args:
            state: Current workflow state
            
        Returns:
            True if execution should be skipped
        """
        # Skip if agent already completed successfully
        if self.agent_name in state.get("completed_agents", []):
            return True
            
        # Skip if agent failed and retry limit exceeded
        if self.agent_name in state.get("failed_agents", []):
            agent_result = state["agent_results"].get(self.agent_name)
            if agent_result and state.get("retry_count", 0) >= self.max_retries:
                return True
        
        return False

    def _get_dependencies_data(self, state: ReAgentState, dependencies: List[str]) -> Dict[str, Any]:
        """
        Extract data from dependency agents.
        
        Args:
            state: Current workflow state
            dependencies: List of agent names this node depends on
            
        Returns:
            Combined data from all dependencies
        """
        dependencies_data = {}
        
        for dep_agent in dependencies:
            if dep_agent in state["agent_results"]:
                result = state["agent_results"][dep_agent]
                if result.status == AgentStatus.COMPLETED:
                    dependencies_data[dep_agent] = result.data
        
        return dependencies_data

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(agent={self.agent_name})>"