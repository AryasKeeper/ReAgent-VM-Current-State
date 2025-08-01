"""
ReAgent Sydney - Crew Orchestrator

Central orchestration system for managing and coordinating multiple agents using CrewAI.
"""

from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import asyncio
import logging
from enum import Enum

from crewai import Crew, Process
from crewai.crew import CrewOutput
from tenacity import retry, stop_after_attempt, wait_exponential

from reagent.agents.base import BaseReAgentAgent, AgentConfig, AgentRole, AgentPriority
from reagent.core.database import DatabaseManager
from reagent.utils.logging import get_logger
from reagent.config.settings import get_settings


class OrchestrationMode(str, Enum):
    """Orchestration execution modes."""
    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"
    CONSENSUS = "consensus"


class CrewOrchestrator:
    """
    Central orchestrator for managing ReAgent crews and coordinating agent execution.
    
    Handles:
    - Agent registration and lifecycle management
    - Task routing and execution
    - Performance monitoring
    - Error handling and recovery
    """
    
    def __init__(self):
        self.logger = get_logger("orchestrator")
        self.settings = get_settings()
        
        # Agent registry
        self.agents: Dict[str, BaseReAgentAgent] = {}
        self.agent_configs: Dict[str, AgentConfig] = {}
        
        # Crew management
        self.crews: Dict[str, Crew] = {}
        self.active_executions: Dict[str, Dict[str, Any]] = {}
        
        # Services
        self.db_manager: Optional[DatabaseManager] = None
        
        # Status
        self.is_initialized = False
        self.is_running = False
    
    async def initialize(self) -> None:
        """Initialize the orchestrator and its dependencies."""
        try:
            self.logger.info("Initializing CrewAI orchestrator...")
            
            # Initialize database connection
            self.db_manager = DatabaseManager()
            await self.db_manager.initialize()
            
            # Initialize all registered agents
            for agent_name, agent in self.agents.items():
                try:
                    await agent.initialize()
                    self.logger.info(f"Agent {agent_name} initialized successfully")
                except Exception as e:
                    self.logger.error(f"Failed to initialize agent {agent_name}: {e}")
                    raise
            
            self.is_initialized = True
            self.logger.info("CrewAI orchestrator initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize orchestrator: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the orchestrator and cleanup resources."""
        try:
            self.logger.info("Shutting down CrewAI orchestrator...")
            
            # Stop all active executions
            await self._stop_active_executions()
            
            # Shutdown all agents
            for agent_name, agent in self.agents.items():
                try:
                    await agent.shutdown()
                    self.logger.info(f"Agent {agent_name} shutdown completed")
                except Exception as e:
                    self.logger.error(f"Error shutting down agent {agent_name}: {e}")
            
            # Close database connection
            if self.db_manager:
                await self.db_manager.close()
            
            self.is_running = False
            self.is_initialized = False
            self.logger.info("CrewAI orchestrator shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during orchestrator shutdown: {e}")
    
    def register_agent(self, agent: BaseReAgentAgent) -> None:
        """Register an agent with the orchestrator."""
        agent_name = agent.config.name
        
        if agent_name in self.agents:
            raise ValueError(f"Agent {agent_name} is already registered")
        
        self.agents[agent_name] = agent
        self.agent_configs[agent_name] = agent.config
        
        self.logger.info(f"Registered agent: {agent_name} ({agent.config.role})")
    
    def unregister_agent(self, agent_name: str) -> None:
        """Unregister an agent from the orchestrator."""
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} is not registered")
        
        # Remove from active crews
        crews_to_remove = []
        for crew_name, crew in self.crews.items():
            if agent_name in [agent.role for agent in crew.agents]:
                crews_to_remove.append(crew_name)
        
        for crew_name in crews_to_remove:
            del self.crews[crew_name]
        
        # Remove agent
        del self.agents[agent_name]
        del self.agent_configs[agent_name]
        
        self.logger.info(f"Unregistered agent: {agent_name}")
    
    def create_crew(
        self,
        crew_name: str,
        agent_names: List[str],
        mode: OrchestrationMode = OrchestrationMode.SEQUENTIAL,
        manager_agent: Optional[str] = None
    ) -> str:
        """Create a new crew with specified agents."""
        
        # Validate agents exist
        for agent_name in agent_names:
            if agent_name not in self.agents:
                raise ValueError(f"Agent {agent_name} is not registered")
        
        # Get agent instances
        crew_agents = [self.agents[agent_name]._crew_agent for agent_name in agent_names]
        
        # Determine process type
        if mode == OrchestrationMode.SEQUENTIAL:
            process = Process.sequential
        elif mode == OrchestrationMode.HIERARCHICAL:
            process = Process.hierarchical
        else:
            process = Process.sequential  # Default fallback
        
        # Create crew
        crew_config = {
            "agents": crew_agents,
            "process": process,
            "verbose": self.settings.crewai.verbose,
            "max_execution_time": self.settings.crewai.max_execution_time,
        }
        
        # Add manager if hierarchical
        if mode == OrchestrationMode.HIERARCHICAL and manager_agent:
            if manager_agent not in self.agents:
                raise ValueError(f"Manager agent {manager_agent} is not registered")
            crew_config["manager_agent"] = self.agents[manager_agent]._crew_agent
        
        crew = Crew(**crew_config)
        self.crews[crew_name] = crew
        
        self.logger.info(f"Created crew '{crew_name}' with agents: {agent_names}")
        return crew_name
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def execute_crew(
        self,
        crew_name: str,
        tasks: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a crew with specified tasks."""
        
        if crew_name not in self.crews:
            raise ValueError(f"Crew {crew_name} does not exist")
        
        crew = self.crews[crew_name]
        execution_id = f"{crew_name}_{datetime.utcnow().isoformat()}"
        
        try:
            self.logger.info(f"Starting crew execution: {execution_id}")
            
            # Track execution
            self.active_executions[execution_id] = {
                "crew_name": crew_name,
                "started_at": datetime.utcnow(),
                "status": "running",
                "tasks": tasks,
                "context": context or {}
            }
            
            # Create CrewAI tasks
            crew_tasks = []
            for task_config in tasks:
                # Find the appropriate agent for this task
                agent_name = task_config.get("agent")
                if agent_name and agent_name in self.agents:
                    agent = self.agents[agent_name]
                    task = agent.create_crew_task(
                        description=task_config["description"],
                        expected_output=task_config.get("expected_output", "Task completed successfully"),
                        **task_config.get("kwargs", {})
                    )
                    crew_tasks.append(task)
            
            # Execute crew
            start_time = datetime.utcnow()
            result = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: crew.kickoff(tasks=crew_tasks, inputs=context or {})
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update execution tracking
            self.active_executions[execution_id].update({
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "execution_time": execution_time,
                "result": result
            })
            
            self.logger.info(f"Crew execution {execution_id} completed in {execution_time:.2f}s")
            
            return {
                "execution_id": execution_id,
                "success": True,
                "result": result,
                "execution_time": execution_time
            }
            
        except Exception as e:
            # Update execution tracking
            self.active_executions[execution_id].update({
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow()
            })
            
            self.logger.error(f"Crew execution {execution_id} failed: {e}")
            
            return {
                "execution_id": execution_id,
                "success": False,
                "error": str(e)
            }
        
        finally:
            # Cleanup
            if execution_id in self.active_executions:
                # Move to history or cleanup after some time
                pass
    
    async def execute_single_agent(
        self,
        agent_name: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a single agent directly."""
        
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} is not registered")
        
        agent = self.agents[agent_name]
        return await agent.execute(input_data)
    
    async def execute_workflow(
        self,
        workflow_name: str,
        agents: List[str],
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a predefined workflow of agents."""
        
        results = {}
        execution_id = f"workflow_{workflow_name}_{datetime.utcnow().isoformat()}"
        
        try:
            self.logger.info(f"Starting workflow execution: {execution_id}")
            
            for agent_name in agents:
                if agent_name not in self.agents:
                    raise ValueError(f"Agent {agent_name} is not registered")
                
                # Execute agent
                agent_result = await self.execute_single_agent(agent_name, input_data)
                results[agent_name] = agent_result
                
                # Pass successful results to next agent as input
                if agent_result.get("success") and agent_result.get("data"):
                    input_data = {**(input_data or {}), **agent_result["data"]}
            
            self.logger.info(f"Workflow execution {execution_id} completed successfully")
            
            return {
                "execution_id": execution_id,
                "workflow": workflow_name,
                "success": True,
                "results": results
            }
            
        except Exception as e:
            self.logger.error(f"Workflow execution {execution_id} failed: {e}")
            
            return {
                "execution_id": execution_id,
                "workflow": workflow_name,
                "success": False,
                "error": str(e),
                "partial_results": results
            }
    
    def get_agent_status(self, agent_name: str) -> Dict[str, Any]:
        """Get status information for a specific agent."""
        
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} is not registered")
        
        agent = self.agents[agent_name]
        
        return {
            "name": agent.config.name,
            "role": agent.config.role,
            "version": agent.config.version,
            "is_running": agent.is_running,
            "metrics": {
                "total_executions": agent.metrics.total_executions,
                "success_rate": agent.metrics.success_rate,
                "avg_execution_time": agent.metrics.avg_execution_time,
                "last_execution": agent.metrics.last_execution.isoformat() if agent.metrics.last_execution else None
            }
        }
    
    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get overall orchestrator status."""
        
        return {
            "is_initialized": self.is_initialized,
            "is_running": self.is_running,
            "registered_agents": list(self.agents.keys()),
            "active_crews": list(self.crews.keys()),
            "active_executions": len(self.active_executions),
            "total_agents": len(self.agents)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on orchestrator and all agents."""
        
        health_status = {
            "orchestrator": "healthy",
            "agents": {},
            "services": {}
        }
        
        try:
            # Check database
            if self.db_manager:
                db_healthy = await self.db_manager.is_healthy()
                health_status["services"]["database"] = "healthy" if db_healthy else "unhealthy"
            
            # Check each agent
            for agent_name, agent in self.agents.items():
                try:
                    # Basic agent health check
                    agent_healthy = not agent.is_running or agent.current_execution is None
                    health_status["agents"][agent_name] = "healthy" if agent_healthy else "busy"
                except Exception as e:
                    health_status["agents"][agent_name] = f"error: {str(e)}"
            
        except Exception as e:
            health_status["orchestrator"] = f"error: {str(e)}"
        
        return health_status
    
    async def _stop_active_executions(self) -> None:
        """Stop all active executions gracefully."""
        
        if not self.active_executions:
            return
        
        self.logger.info(f"Stopping {len(self.active_executions)} active executions...")
        
        # For now, we'll just mark them as cancelled
        # In a production system, you'd want more sophisticated cancellation
        for execution_id in list(self.active_executions.keys()):
            self.active_executions[execution_id]["status"] = "cancelled"
            self.active_executions[execution_id]["completed_at"] = datetime.utcnow()
    
    def __repr__(self) -> str:
        return f"<CrewOrchestrator(agents={len(self.agents)}, crews={len(self.crews)})>"