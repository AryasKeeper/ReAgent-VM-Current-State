"""
ReAgent Sydney - Multi-Agent Orchestrator

Sophisticated orchestration system for coordinating multiple ReAgent specialist agents
to fulfill complex real estate intelligence requests from the Agent Whisperer.

Core Capabilities:
- Intelligent agent selection based on query requirements
- Parallel and sequential task execution coordination
- Result synthesis and conflict resolution
- Performance monitoring and load balancing
- Error handling and fallback strategies
- Data quality assurance across agent outputs
"""

from typing import Any, Dict, List, Optional, Tuple, Set, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import uuid
from collections import defaultdict

from .nlp_processor import QueryIntent, IntentType


class CoordinationStrategy(str, Enum):
    """Strategies for coordinating multiple agents."""
    
    PARALLEL = "parallel"          # Execute all agents simultaneously
    SEQUENTIAL = "sequential"      # Execute agents in dependency order
    CONDITIONAL = "conditional"    # Execute based on previous results
    HIERARCHICAL = "hierarchical"  # Execute with primary/secondary structure
    ADAPTIVE = "adaptive"          # Dynamically adjust strategy based on results


class AgentPriority(str, Enum):
    """Priority levels for agent execution."""
    
    CRITICAL = "critical"    # Must complete successfully
    HIGH = "high"           # Important for comprehensive results
    MEDIUM = "medium"       # Helpful but not essential
    LOW = "low"            # Nice to have, can be skipped if needed
    OPTIONAL = "optional"   # Only execute if resources available


class ExecutionStatus(str, Enum):
    """Status of agent execution coordination."""
    
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    TIMEOUT = "timeout"


@dataclass
class AgentTask:
    """Individual task for a specific agent."""
    
    task_id: str
    agent_name: str
    task_description: str
    priority: AgentPriority
    
    # Task parameters
    input_data: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 60
    retry_count: int = 0
    max_retries: int = 2
    
    # Execution metadata
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: float = 0.0
    
    # Results
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    confidence_score: float = 0.0
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Task IDs this depends on
    blocks: List[str] = field(default_factory=list)      # Task IDs this blocks
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "task_description": self.task_description,
            "priority": self.priority.value,
            "input_data": self.input_data,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time": self.execution_time,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "confidence_score": self.confidence_score,
            "depends_on": self.depends_on,
            "blocks": self.blocks
        }
    
    def is_ready_to_execute(self, completed_tasks: Set[str]) -> bool:
        """Check if this task's dependencies are satisfied."""
        return all(dep_id in completed_tasks for dep_id in self.depends_on)
    
    def can_retry(self) -> bool:
        """Check if this task can be retried."""
        return self.retry_count < self.max_retries and self.status == ExecutionStatus.FAILED


@dataclass
class AgentCoordinationRequest:
    """Request for coordinating multiple agents."""
    
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    primary_intent: QueryIntent = None
    required_agents: List[str] = field(default_factory=list)
    optional_agents: List[str] = field(default_factory=list)
    
    # Coordination parameters
    strategy: CoordinationStrategy = CoordinationStrategy.ADAPTIVE
    timeout_seconds: int = 120
    priority: str = "medium"
    
    # Data requirements
    minimum_data_quality: float = 0.7
    require_all_agents: bool = False
    allow_partial_results: bool = True
    
    # Custom analysis
    custom_analysis: bool = False
    analysis_parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "primary_intent": self.primary_intent.to_dict() if self.primary_intent else None,
            "required_agents": self.required_agents,
            "optional_agents": self.optional_agents,
            "strategy": self.strategy.value,
            "timeout_seconds": self.timeout_seconds,
            "priority": self.priority,
            "minimum_data_quality": self.minimum_data_quality,
            "require_all_agents": self.require_all_agents,
            "allow_partial_results": self.allow_partial_results,
            "custom_analysis": self.custom_analysis,
            "analysis_parameters": self.analysis_parameters
        }


@dataclass
class CoordinationResult:
    """Result of multi-agent coordination."""
    
    request_id: str
    status: ExecutionStatus
    execution_time: float
    
    # Results by agent
    agent_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    successful_agents: List[str] = field(default_factory=list)
    failed_agents: List[str] = field(default_factory=list)
    
    # Synthesized results
    combined_data: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    data_quality_score: float = 0.0
    
    # Metadata
    tasks_completed: int = 0
    tasks_failed: int = 0
    data_sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "execution_time": self.execution_time,
            "agent_results": self.agent_results,
            "successful_agents": self.successful_agents,
            "failed_agents": self.failed_agents,
            "combined_data": self.combined_data,
            "confidence_score": self.confidence_score,
            "data_quality_score": self.data_quality_score,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "data_sources": self.data_sources,
            "warnings": self.warnings
        }
    
    def is_successful(self) -> bool:
        """Check if the coordination was successful."""
        return self.status == ExecutionStatus.COMPLETED and len(self.successful_agents) > 0
    
    def get_success_rate(self) -> float:
        """Get the success rate of agent executions."""
        total_agents = len(self.successful_agents) + len(self.failed_agents)
        if total_agents == 0:
            return 0.0
        return len(self.successful_agents) / total_agents


class MultiAgentOrchestrator:
    """
    Sophisticated orchestration system for coordinating ReAgent specialist agents.
    
    Manages complex multi-agent workflows, handles dependencies, ensures data quality,
    and provides comprehensive error handling and recovery strategies.
    """
    
    def __init__(self, max_concurrent_agents: int = 5, logger=None):
        self.max_concurrent_agents = max_concurrent_agents
        self.logger = logger
        
        # Agent registry and capabilities
        self.available_agents = {
            "listing_watcher": {
                "capabilities": ["property_search", "listing_data", "recent_sales"],
                "typical_execution_time": 15,
                "reliability_score": 0.92,
                "data_quality_score": 0.88
            },
            "suburb_signal": {
                "capabilities": ["market_analysis", "trend_analysis", "suburb_data"],
                "typical_execution_time": 25,
                "reliability_score": 0.89,
                "data_quality_score": 0.91
            },
            "buyer_matchmaker": {
                "capabilities": ["buyer_matching", "preference_analysis", "property_recommendations"],
                "typical_execution_time": 20,
                "reliability_score": 0.85,
                "data_quality_score": 0.83
            },
            "seller_strategy": {
                "capabilities": ["pricing_analysis", "market_positioning", "sale_strategy"],
                "typical_execution_time": 30,
                "reliability_score": 0.87,
                "data_quality_score": 0.86
            },
            "off_market_radar": {
                "capabilities": ["off_market_opportunities", "distress_signals", "private_sales"],
                "typical_execution_time": 35,
                "reliability_score": 0.78,
                "data_quality_score": 0.75
            }
        }
        
        # Active coordinations
        self.active_coordinations: Dict[str, Dict[str, Any]] = {}
        
        # Performance tracking
        self.orchestration_stats = {
            "total_coordinations": 0,
            "successful_coordinations": 0,
            "failed_coordinations": 0,
            "avg_execution_time": 0.0,
            "avg_agents_per_coordination": 0.0,
            "agent_success_rates": {},
            "common_agent_combinations": defaultdict(int)
        }
    
    async def initialize(self) -> None:
        """Initialize the multi-agent orchestrator."""
        
        if self.logger:
            self.logger.info(f"Initializing Multi-Agent Orchestrator with {len(self.available_agents)} agents")
        
        # Initialize agent success rate tracking
        for agent_name in self.available_agents:
            self.orchestration_stats["agent_success_rates"][agent_name] = {
                "executions": 0,
                "successes": 0,
                "failures": 0,
                "avg_execution_time": 0.0,
                "success_rate": 1.0
            }
        
        if self.logger:
            self.logger.info("Multi-Agent Orchestrator initialized successfully")
    
    async def shutdown(self) -> None:
        """Shutdown the orchestrator and cleanup resources."""
        
        # Cancel any active coordinations
        if self.active_coordinations:
            if self.logger:
                self.logger.info(f"Cancelling {len(self.active_coordinations)} active coordinations")
            
            for coordination_id in list(self.active_coordinations.keys()):
                await self._cancel_coordination(coordination_id)
    
    async def coordinate_agents(self, request: AgentCoordinationRequest) -> Dict[str, Any]:
        """
        Coordinate multiple agents to fulfill a complex request.
        
        Args:
            request: The coordination request with agent requirements and parameters
            
        Returns:
            Dictionary containing the coordination results
        """
        
        start_time = datetime.utcnow()
        
        try:
            self.orchestration_stats["total_coordinations"] += 1
            
            if self.logger:
                self.logger.info(f"Starting agent coordination: {request.request_id}")
            
            # Track active coordination
            self.active_coordinations[request.request_id] = {
                "request": request,
                "status": ExecutionStatus.PLANNING,
                "started_at": start_time,
                "tasks": {}
            }
            
            # Plan the coordination strategy
            execution_plan = await self._plan_coordination(request)
            
            # Update status
            self.active_coordinations[request.request_id]["status"] = ExecutionStatus.EXECUTING
            self.active_coordinations[request.request_id]["execution_plan"] = execution_plan
            
            # Execute the coordination plan
            coordination_result = await self._execute_coordination_plan(request, execution_plan)
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            coordination_result.execution_time = execution_time
            
            # Update statistics
            self._update_orchestration_stats(request, coordination_result, execution_time)
            
            # Clean up active coordination
            if request.request_id in self.active_coordinations:
                del self.active_coordinations[request.request_id]
            
            if self.logger:
                self.logger.info(
                    f"Coordination completed: {request.request_id} - "
                    f"Status: {coordination_result.status.value}, "
                    f"Success Rate: {coordination_result.get_success_rate():.2f}, "
                    f"Time: {execution_time:.2f}s"
                )
            
            return coordination_result.to_dict()
            
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            self.orchestration_stats["failed_coordinations"] += 1
            
            if self.logger:
                self.logger.error(f"Coordination failed: {request.request_id} - {e}", exc_info=True)
            
            # Create error result
            error_result = CoordinationResult(
                request_id=request.request_id,
                status=ExecutionStatus.FAILED,
                execution_time=execution_time,
                warnings=[f"Coordination failed: {str(e)}"]
            )
            
            # Clean up
            if request.request_id in self.active_coordinations:
                del self.active_coordinations[request.request_id]
            
            return error_result.to_dict()
    
    async def _plan_coordination(self, request: AgentCoordinationRequest) -> Dict[str, Any]:
        """Plan the coordination strategy and create execution tasks."""
        
        # Determine the optimal agents for this request
        selected_agents = await self._select_agents(request)
        
        # Create tasks for each selected agent
        tasks = await self._create_agent_tasks(request, selected_agents)
        
        # Determine execution strategy
        strategy = await self._determine_execution_strategy(request, tasks)
        
        # Build dependency graph
        dependency_graph = await self._build_dependency_graph(tasks, strategy)
        
        execution_plan = {
            "selected_agents": selected_agents,
            "tasks": {task.task_id: task for task in tasks},
            "strategy": strategy,
            "dependency_graph": dependency_graph,
            "estimated_execution_time": self._estimate_execution_time(tasks, strategy)
        }
        
        if self.logger:
            self.logger.debug(
                f"Coordination plan created: {len(selected_agents)} agents, "
                f"{len(tasks)} tasks, strategy: {strategy.value}"
            )
        
        return execution_plan
    
    async def _select_agents(self, request: AgentCoordinationRequest) -> List[str]:
        """Select the optimal agents for the coordination request."""
        
        selected_agents = []
        
        # Always include required agents (if available)
        for agent_name in request.required_agents:
            if agent_name in self.available_agents:
                selected_agents.append(agent_name)
            elif not request.allow_partial_results:
                raise ValueError(f"Required agent {agent_name} is not available")
        
        # Add optional agents based on capabilities and performance
        intent_capabilities = self._get_required_capabilities(request.primary_intent)
        
        for agent_name in request.optional_agents:
            if agent_name in self.available_agents and agent_name not in selected_agents:
                agent_info = self.available_agents[agent_name]
                
                # Check if agent has relevant capabilities
                if any(cap in agent_info["capabilities"] for cap in intent_capabilities):
                    # Consider agent reliability and current load
                    if self._should_include_optional_agent(agent_name, request):
                        selected_agents.append(agent_name)
        
        # Auto-select additional agents based on intent if not enough selected
        if len(selected_agents) < 2 and request.strategy == CoordinationStrategy.ADAPTIVE:
            additional_agents = await self._auto_select_agents(request, selected_agents)
            selected_agents.extend(additional_agents)
        
        return selected_agents
    
    async def _create_agent_tasks(self, request: AgentCoordinationRequest, selected_agents: List[str]) -> List[AgentTask]:
        """Create specific tasks for each selected agent."""
        
        tasks = []
        
        for agent_name in selected_agents:
            task_id = f"{request.request_id}_{agent_name}_{uuid.uuid4().hex[:8]}"
            
            # Determine task priority
            if agent_name in request.required_agents:
                priority = AgentPriority.CRITICAL
            else:
                priority = self._determine_task_priority(agent_name, request)
            
            # Create agent-specific input data
            input_data = await self._create_agent_input_data(agent_name, request)
            
            # Determine timeout based on agent capabilities and request complexity
            timeout = self._calculate_agent_timeout(agent_name, request)
            
            task = AgentTask(
                task_id=task_id,
                agent_name=agent_name,
                task_description=f"Execute {agent_name} for {request.primary_intent.intent_type.value if request.primary_intent else 'coordination'}",
                priority=priority,
                input_data=input_data,
                timeout_seconds=timeout,
                max_retries=2 if priority in [AgentPriority.CRITICAL, AgentPriority.HIGH] else 1
            )
            
            tasks.append(task)
        
        return tasks
    
    async def _execute_coordination_plan(
        self, 
        request: AgentCoordinationRequest, 
        execution_plan: Dict[str, Any]
    ) -> CoordinationResult:
        """Execute the coordination plan and gather results."""
        
        tasks = execution_plan["tasks"]
        strategy = execution_plan["strategy"]
        dependency_graph = execution_plan["dependency_graph"]
        
        # Initialize result
        result = CoordinationResult(
            request_id=request.request_id,
            status=ExecutionStatus.EXECUTING
        )
        
        # Execute tasks based on strategy
        if strategy == CoordinationStrategy.PARALLEL:
            await self._execute_parallel_tasks(tasks, result)
        
        elif strategy == CoordinationStrategy.SEQUENTIAL:
            await self._execute_sequential_tasks(tasks, dependency_graph, result)
        
        elif strategy == CoordinationStrategy.CONDITIONAL:
            await self._execute_conditional_tasks(tasks, dependency_graph, result)
        
        else:  # ADAPTIVE or other strategies
            await self._execute_adaptive_tasks(tasks, dependency_graph, result, request)
        
        # Synthesize results from all agents
        await self._synthesize_agent_results(result, request)
        
        # Determine final status
        if len(result.successful_agents) == 0:
            result.status = ExecutionStatus.FAILED
        elif len(result.failed_agents) > 0 and not request.allow_partial_results:
            result.status = ExecutionStatus.PARTIAL
        else:
            result.status = ExecutionStatus.COMPLETED
        
        return result
    
    async def _execute_parallel_tasks(self, tasks: Dict[str, AgentTask], result: CoordinationResult) -> None:
        """Execute all tasks in parallel."""
        
        # Create semaphore to limit concurrent executions
        semaphore = asyncio.Semaphore(self.max_concurrent_agents)
        
        # Execute all tasks concurrently
        task_coroutines = [
            self._execute_single_task_with_semaphore(task, semaphore, result)
            for task in tasks.values()
        ]
        
        await asyncio.gather(*task_coroutines, return_exceptions=True)
    
    async def _execute_sequential_tasks(
        self, 
        tasks: Dict[str, AgentTask], 
        dependency_graph: Dict[str, List[str]], 
        result: CoordinationResult
    ) -> None:
        """Execute tasks in dependency order."""
        
        completed_tasks = set()
        remaining_tasks = set(tasks.keys())
        
        while remaining_tasks:
            # Find tasks that are ready to execute
            ready_tasks = [
                task_id for task_id in remaining_tasks
                if tasks[task_id].is_ready_to_execute(completed_tasks)
            ]
            
            if not ready_tasks:
                # Circular dependency or all remaining tasks failed
                break
            
            # Execute ready tasks (can be parallel if no dependencies between them)
            ready_coroutines = [
                self._execute_single_task(tasks[task_id], result)
                for task_id in ready_tasks
            ]
            
            results = await asyncio.gather(*ready_coroutines, return_exceptions=True)
            
            # Update completed and remaining tasks
            for i, task_id in enumerate(ready_tasks):
                if not isinstance(results[i], Exception):
                    completed_tasks.add(task_id)
                remaining_tasks.remove(task_id)
    
    async def _execute_adaptive_tasks(
        self, 
        tasks: Dict[str, AgentTask], 
        dependency_graph: Dict[str, List[str]], 
        result: CoordinationResult,
        request: AgentCoordinationRequest
    ) -> None:
        """Execute tasks with adaptive strategy based on intermediate results."""
        
        # Start with critical tasks in parallel
        critical_tasks = [task for task in tasks.values() if task.priority == AgentPriority.CRITICAL]
        high_priority_tasks = [task for task in tasks.values() if task.priority == AgentPriority.HIGH]
        
        # Execute critical tasks first
        if critical_tasks:
            await self._execute_parallel_task_list(critical_tasks, result)
        
        # Analyze critical results and decide on next steps
        if len(result.successful_agents) == 0:
            # Critical tasks failed, try alternative approach or fail
            await self._handle_critical_failure(tasks, result, request)
            return
        
        # Execute high priority tasks
        if high_priority_tasks:
            await self._execute_parallel_task_list(high_priority_tasks, result)
        
        # Execute remaining tasks based on available time and resources
        remaining_tasks = [
            task for task in tasks.values() 
            if task.status == ExecutionStatus.PENDING and task.priority in [AgentPriority.MEDIUM, AgentPriority.LOW]
        ]
        
        if remaining_tasks and self._has_time_for_additional_tasks(result):
            await self._execute_parallel_task_list(remaining_tasks, result)
    
    async def _execute_single_task_with_semaphore(
        self, 
        task: AgentTask, 
        semaphore: asyncio.Semaphore, 
        result: CoordinationResult
    ) -> None:
        """Execute a single task with semaphore for concurrency control."""
        
        async with semaphore:
            await self._execute_single_task(task, result)
    
    async def _execute_single_task(self, task: AgentTask, result: CoordinationResult) -> None:
        """Execute a single agent task."""
        
        task.status = ExecutionStatus.EXECUTING
        task.started_at = datetime.utcnow()
        
        try:
            # Simulate agent execution (in production, this would call the actual agent)
            agent_result = await self._call_agent(task.agent_name, task.input_data, task.timeout_seconds)
            
            task.completed_at = datetime.utcnow()
            task.execution_time = (task.completed_at - task.started_at).total_seconds()
            task.output_data = agent_result
            task.status = ExecutionStatus.COMPLETED
            task.confidence_score = agent_result.get("confidence", 0.8)
            
            # Update coordination result
            result.agent_results[task.agent_name] = agent_result
            result.successful_agents.append(task.agent_name)
            result.tasks_completed += 1
            
            # Add data sources
            if "data_sources" in agent_result:
                result.data_sources.extend(agent_result["data_sources"])
            
            if self.logger:
                self.logger.debug(f"Task completed successfully: {task.task_id} ({task.execution_time:.2f}s)")
        
        except asyncio.TimeoutError:
            task.status = ExecutionStatus.TIMEOUT
            task.error_message = f"Task timed out after {task.timeout_seconds} seconds"
            result.failed_agents.append(task.agent_name)
            result.tasks_failed += 1
            result.warnings.append(f"{task.agent_name}: Task timed out")
            
            if self.logger:
                self.logger.warning(f"Task timed out: {task.task_id}")
        
        except Exception as e:
            task.status = ExecutionStatus.FAILED
            task.error_message = str(e)
            result.failed_agents.append(task.agent_name)
            result.tasks_failed += 1
            result.warnings.append(f"{task.agent_name}: {str(e)}")
            
            if self.logger:
                self.logger.error(f"Task failed: {task.task_id} - {e}")
        
        # Update agent statistics
        self._update_agent_stats(task.agent_name, task.status == ExecutionStatus.COMPLETED, task.execution_time)
    
    async def _call_agent(self, agent_name: str, input_data: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
        """Call a specific agent (simulated for this implementation)."""
        
        # Simulate agent processing time
        processing_time = self.available_agents[agent_name]["typical_execution_time"]
        await asyncio.sleep(min(processing_time / 10, 2))  # Reduced for simulation
        
        # Simulate agent response based on agent capabilities
        agent_info = self.available_agents[agent_name]
        
        # Generate mock response based on agent type
        if agent_name == "listing_watcher":
            return self._generate_listing_watcher_response(input_data)
        elif agent_name == "suburb_signal":
            return self._generate_suburb_signal_response(input_data)
        elif agent_name == "buyer_matchmaker":
            return self._generate_buyer_matchmaker_response(input_data)
        elif agent_name == "seller_strategy":
            return self._generate_seller_strategy_response(input_data)
        elif agent_name == "off_market_radar":
            return self._generate_off_market_radar_response(input_data)
        else:
            return {
                "success": True,
                "data": {"message": f"Response from {agent_name}"},
                "confidence": agent_info["reliability_score"],
                "data_sources": [f"{agent_name}_api"]
            }
    
    def _generate_listing_watcher_response(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock response from listing watcher agent."""
        return {
            "success": True,
            "data": {
                "recent_listings": [
                    {"address": "123 Sample St", "price": 1250000, "type": "house"},
                    {"address": "456 Example Ave", "price": 950000, "type": "unit"}
                ],
                "market_activity": "strong",
                "listing_count": 45
            },
            "confidence": 0.88,
            "data_sources": ["Domain API", "REA Data"]
        }
    
    def _generate_suburb_signal_response(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock response from suburb signal agent."""
        return {
            "success": True,
            "data": {
                "price_trends": {"direction": "upward", "change_percent": 3.2},
                "market_indicators": {"buyer_demand": "high", "supply_level": "moderate"},
                "growth_projection": 6.5
            },
            "confidence": 0.91,
            "data_sources": ["Market Analysis", "Sales Data"]
        }
    
    def _generate_buyer_matchmaker_response(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock response from buyer matchmaker agent."""
        return {
            "success": True,
            "data": {
                "matched_properties": [
                    {"address": "789 Match St", "match_score": 0.94, "price": 1180000},
                    {"address": "321 Perfect Ave", "match_score": 0.87, "price": 1050000}
                ],
                "buyer_insights": {"budget_fit": "good", "preference_alignment": "high"}
            },
            "confidence": 0.83,
            "data_sources": ["Buyer Database", "Property Listings"]
        }
    
    def _generate_seller_strategy_response(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock response from seller strategy agent."""
        return {
            "success": True,
            "data": {
                "pricing_recommendation": {"min_price": 1200000, "optimal_price": 1275000, "max_price": 1350000},
                "market_timing": {"optimal_timing": "current", "seasonal_factor": "favorable"},
                "strategy_points": ["Competitive pricing", "Professional presentation", "Strategic timing"]
            },
            "confidence": 0.86,
            "data_sources": ["Comparable Sales", "Market Analysis"]
        }
    
    def _generate_off_market_radar_response(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock response from off-market radar agent."""
        return {
            "success": True,
            "data": {
                "off_market_opportunities": [
                    {"address": "555 Private St", "status": "pre_market", "estimated_price": 1400000},
                    {"address": "777 Exclusive Ave", "status": "distressed", "estimated_price": 980000}
                ],
                "opportunity_score": 7.5
            },
            "confidence": 0.75,
            "data_sources": ["Off-Market Networks", "Distress Indicators"]
        }
    
    async def _synthesize_agent_results(self, result: CoordinationResult, request: AgentCoordinationRequest) -> None:
        """Synthesize results from multiple agents into coherent output."""
        
        if not result.agent_results:
            return
        
        # Calculate overall confidence and data quality scores
        confidence_scores = []
        data_quality_scores = []
        
        for agent_name, agent_result in result.agent_results.items():
            if agent_result.get("success"):
                confidence_scores.append(agent_result.get("confidence", 0.8))
                
                # Estimate data quality based on agent reputation
                agent_info = self.available_agents.get(agent_name, {})
                data_quality_scores.append(agent_info.get("data_quality_score", 0.8))
        
        # Calculate weighted averages
        if confidence_scores:
            result.confidence_score = sum(confidence_scores) / len(confidence_scores)
        
        if data_quality_scores:
            result.data_quality_score = sum(data_quality_scores) / len(data_quality_scores)
        
        # Combine data from multiple agents
        combined_data = {}
        
        # Aggregate data based on request type
        if request.primary_intent:
            if request.primary_intent.intent_type in [IntentType.MARKET_UPDATE, IntentType.SUBURB_ANALYSIS]:
                combined_data = self._synthesize_market_analysis_data(result.agent_results)
            
            elif request.primary_intent.intent_type == IntentType.BUYER_MATCHING:
                combined_data = self._synthesize_buyer_matching_data(result.agent_results)
            
            elif request.primary_intent.intent_type == IntentType.SELLER_STRATEGY:
                combined_data = self._synthesize_seller_strategy_data(result.agent_results)
            
            else:
                combined_data = self._synthesize_general_data(result.agent_results)
        
        else:
            combined_data = self._synthesize_general_data(result.agent_results)
        
        result.combined_data = combined_data
    
    def _synthesize_market_analysis_data(self, agent_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesize market analysis data from multiple agents."""
        
        combined = {
            "market_overview": {},
            "price_analysis": {},
            "activity_metrics": {},
            "insights": []
        }
        
        # Combine data from listing watcher
        if "listing_watcher" in agent_results:
            listing_data = agent_results["listing_watcher"].get("data", {})
            combined["activity_metrics"].update({
                "recent_listings": listing_data.get("recent_listings", []),
                "listing_count": listing_data.get("listing_count", 0),
                "market_activity": listing_data.get("market_activity", "unknown")
            })
        
        # Combine data from suburb signal
        if "suburb_signal" in agent_results:
            signal_data = agent_results["suburb_signal"].get("data", {})
            combined["price_analysis"].update(signal_data.get("price_trends", {}))
            combined["market_overview"].update(signal_data.get("market_indicators", {}))
            
            if "growth_projection" in signal_data:
                combined["insights"].append(f"Projected growth: {signal_data['growth_projection']}%")
        
        return combined
    
    def _synthesize_buyer_matching_data(self, agent_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesize buyer matching data from multiple agents."""
        
        combined = {
            "property_matches": [],
            "market_context": {},
            "recommendations": []
        }
        
        # Get matches from buyer matchmaker
        if "buyer_matchmaker" in agent_results:
            buyer_data = agent_results["buyer_matchmaker"].get("data", {})
            combined["property_matches"] = buyer_data.get("matched_properties", [])
            combined["buyer_insights"] = buyer_data.get("buyer_insights", {})
        
        # Add market context from other agents
        if "suburb_signal" in agent_results:
            signal_data = agent_results["suburb_signal"].get("data", {})
            combined["market_context"] = signal_data
        
        return combined
    
    def _synthesize_seller_strategy_data(self, agent_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesize seller strategy data from multiple agents."""
        
        combined = {
            "pricing_strategy": {},
            "market_positioning": {},
            "strategic_recommendations": []
        }
        
        # Get strategy from seller strategy agent
        if "seller_strategy" in agent_results:
            strategy_data = agent_results["seller_strategy"].get("data", {})
            combined["pricing_strategy"] = strategy_data.get("pricing_recommendation", {})
            combined["strategic_recommendations"] = strategy_data.get("strategy_points", [])
        
        # Add market context
        if "suburb_signal" in agent_results:
            signal_data = agent_results["suburb_signal"].get("data", {})
            combined["market_positioning"] = signal_data
        
        return combined
    
    def _synthesize_general_data(self, agent_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesize general data from multiple agents."""
        
        combined = {}
        
        for agent_name, agent_result in agent_results.items():
            if agent_result.get("success"):
                combined[agent_name] = agent_result.get("data", {})
        
        return combined
    
    # Helper methods for planning and selection
    
    def _get_required_capabilities(self, intent: QueryIntent) -> List[str]:
        """Get required capabilities based on the query intent."""
        
        if not intent:
            return []
        
        capability_mapping = {
            IntentType.LISTING_SEARCH: ["property_search", "listing_data"],
            IntentType.MARKET_UPDATE: ["market_analysis", "trend_analysis"],
            IntentType.SUBURB_ANALYSIS: ["market_analysis", "suburb_data"],
            IntentType.BUYER_MATCHING: ["buyer_matching", "property_recommendations"],
            IntentType.SELLER_STRATEGY: ["pricing_analysis", "sale_strategy"],
            IntentType.INVESTMENT_ANALYSIS: ["market_analysis", "pricing_analysis"],
            IntentType.OFF_MARKET_OPPORTUNITIES: ["off_market_opportunities"]
        }
        
        return capability_mapping.get(intent.intent_type, [])
    
    def _should_include_optional_agent(self, agent_name: str, request: AgentCoordinationRequest) -> bool:
        """Determine if an optional agent should be included."""
        
        agent_stats = self.orchestration_stats["agent_success_rates"].get(agent_name, {})
        success_rate = agent_stats.get("success_rate", 1.0)
        
        # Include if success rate is good and not too many agents already selected
        return success_rate > 0.8 and len(request.required_agents) + len(request.optional_agents) <= 4
    
    async def _auto_select_agents(self, request: AgentCoordinationRequest, current_agents: List[str]) -> List[str]:
        """Auto-select additional agents based on intent analysis."""
        
        additional_agents = []
        
        if not request.primary_intent:
            return additional_agents
        
        # Intent-based auto-selection
        if request.primary_intent.intent_type in [IntentType.MARKET_UPDATE, IntentType.SUBURB_ANALYSIS]:
            if "listing_watcher" not in current_agents:
                additional_agents.append("listing_watcher")
            if "suburb_signal" not in current_agents:
                additional_agents.append("suburb_signal")
        
        elif request.primary_intent.intent_type == IntentType.BUYER_MATCHING:
            if "buyer_matchmaker" not in current_agents:
                additional_agents.append("buyer_matchmaker")
            if "listing_watcher" not in current_agents:
                additional_agents.append("listing_watcher")
        
        # Filter to only include available agents
        return [agent for agent in additional_agents if agent in self.available_agents]
    
    def _determine_task_priority(self, agent_name: str, request: AgentCoordinationRequest) -> AgentPriority:
        """Determine the priority for a specific agent task."""
        
        if agent_name in request.required_agents:
            return AgentPriority.CRITICAL
        
        # Determine priority based on agent capabilities and request
        agent_info = self.available_agents[agent_name]
        reliability = agent_info["reliability_score"]
        
        if reliability > 0.9:
            return AgentPriority.HIGH
        elif reliability > 0.8:
            return AgentPriority.MEDIUM
        else:
            return AgentPriority.LOW
    
    async def _create_agent_input_data(self, agent_name: str, request: AgentCoordinationRequest) -> Dict[str, Any]:
        """Create input data specific to an agent."""
        
        base_data = {
            "request_id": request.request_id,
            "priority": request.priority,
            "context": request.analysis_parameters
        }
        
        # Add intent-specific data
        if request.primary_intent:
            base_data["intent"] = request.primary_intent.to_dict()
            base_data["entities"] = request.primary_intent.entities
        
        return base_data
    
    def _calculate_agent_timeout(self, agent_name: str, request: AgentCoordinationRequest) -> int:
        """Calculate appropriate timeout for an agent."""
        
        base_timeout = self.available_agents[agent_name]["typical_execution_time"]
        
        # Adjust based on request complexity and priority
        if request.custom_analysis:
            base_timeout *= 1.5
        
        if request.priority == "high":
            base_timeout *= 0.8  # Shorter timeout for high priority
        elif request.priority == "low":
            base_timeout *= 1.3  # Longer timeout for low priority
        
        return max(int(base_timeout), 30)  # Minimum 30 seconds
    
    async def _determine_execution_strategy(self, request: AgentCoordinationRequest, tasks: List[AgentTask]) -> CoordinationStrategy:
        """Determine the optimal execution strategy."""
        
        if request.strategy != CoordinationStrategy.ADAPTIVE:
            return request.strategy
        
        # Adaptive strategy selection
        critical_tasks = [t for t in tasks if t.priority == AgentPriority.CRITICAL]
        
        if len(tasks) <= 2:
            return CoordinationStrategy.PARALLEL
        elif len(critical_tasks) > 0 and len(tasks) > 4:
            return CoordinationStrategy.HIERARCHICAL
        elif request.timeout_seconds < 60:
            return CoordinationStrategy.PARALLEL
        else:
            return CoordinationStrategy.SEQUENTIAL
    
    async def _build_dependency_graph(self, tasks: List[AgentTask], strategy: CoordinationStrategy) -> Dict[str, List[str]]:
        """Build dependency graph for task execution."""
        
        dependency_graph = {}
        
        if strategy == CoordinationStrategy.HIERARCHICAL:
            # Create hierarchical dependencies
            critical_tasks = [t for t in tasks if t.priority == AgentPriority.CRITICAL]
            high_tasks = [t for t in tasks if t.priority == AgentPriority.HIGH]
            other_tasks = [t for t in tasks if t.priority not in [AgentPriority.CRITICAL, AgentPriority.HIGH]]
            
            # High priority tasks depend on critical tasks
            for high_task in high_tasks:
                high_task.depends_on = [t.task_id for t in critical_tasks]
            
            # Other tasks depend on high priority tasks
            for other_task in other_tasks:
                other_task.depends_on = [t.task_id for t in high_tasks]
        
        # Build graph representation
        for task in tasks:
            dependency_graph[task.task_id] = task.depends_on
        
        return dependency_graph
    
    def _estimate_execution_time(self, tasks: List[AgentTask], strategy: CoordinationStrategy) -> float:
        """Estimate total execution time for the coordination."""
        
        if strategy == CoordinationStrategy.PARALLEL:
            # Maximum of all task times
            return max((self.available_agents[task.agent_name]["typical_execution_time"] for task in tasks), default=30)
        
        elif strategy == CoordinationStrategy.SEQUENTIAL:
            # Sum of all task times
            return sum(self.available_agents[task.agent_name]["typical_execution_time"] for task in tasks)
        
        else:
            # Estimate based on priority levels
            critical_time = max((
                self.available_agents[task.agent_name]["typical_execution_time"] 
                for task in tasks if task.priority == AgentPriority.CRITICAL
            ), default=0)
            
            other_time = max((
                self.available_agents[task.agent_name]["typical_execution_time"] 
                for task in tasks if task.priority != AgentPriority.CRITICAL
            ), default=0)
            
            return critical_time + other_time * 0.6  # Overlap assumption
    
    # Utility methods
    
    async def _execute_parallel_task_list(self, tasks: List[AgentTask], result: CoordinationResult) -> None:
        """Execute a list of tasks in parallel."""
        
        semaphore = asyncio.Semaphore(min(len(tasks), self.max_concurrent_agents))
        task_coroutines = [
            self._execute_single_task_with_semaphore(task, semaphore, result)
            for task in tasks
        ]
        
        await asyncio.gather(*task_coroutines, return_exceptions=True)
    
    async def _handle_critical_failure(
        self, 
        tasks: Dict[str, AgentTask], 
        result: CoordinationResult, 
        request: AgentCoordinationRequest
    ) -> None:
        """Handle failure of critical tasks."""
        
        # Try to retry failed critical tasks
        critical_failed_tasks = [
            task for task in tasks.values() 
            if task.priority == AgentPriority.CRITICAL and task.status == ExecutionStatus.FAILED and task.can_retry()
        ]
        
        if critical_failed_tasks:
            # Retry critical tasks
            for task in critical_failed_tasks:
                task.retry_count += 1
                task.status = ExecutionStatus.PENDING
            
            await self._execute_parallel_task_list(critical_failed_tasks, result)
    
    def _has_time_for_additional_tasks(self, result: CoordinationResult) -> bool:
        """Check if there's time to execute additional tasks."""
        
        # Simple heuristic: if we've used less than 60% of available time
        # In practice, this would be more sophisticated
        return len(result.successful_agents) > 0
    
    async def _cancel_coordination(self, coordination_id: str) -> None:
        """Cancel an active coordination."""
        
        if coordination_id in self.active_coordinations:
            coordination = self.active_coordinations[coordination_id]
            coordination["status"] = ExecutionStatus.FAILED
            # In practice, you'd cancel running tasks here
            del self.active_coordinations[coordination_id]
    
    def _update_orchestration_stats(
        self, 
        request: AgentCoordinationRequest, 
        result: CoordinationResult, 
        execution_time: float
    ) -> None:
        """Update orchestration statistics."""
        
        if result.is_successful():
            self.orchestration_stats["successful_coordinations"] += 1
        else:
            self.orchestration_stats["failed_coordinations"] += 1
        
        # Update average execution time
        total_coordinations = self.orchestration_stats["total_coordinations"]
        current_avg = self.orchestration_stats["avg_execution_time"]
        self.orchestration_stats["avg_execution_time"] = (
            (current_avg * (total_coordinations - 1) + execution_time) / total_coordinations
        )
        
        # Update average agents per coordination
        agents_used = len(result.successful_agents) + len(result.failed_agents)
        current_avg_agents = self.orchestration_stats["avg_agents_per_coordination"]
        self.orchestration_stats["avg_agents_per_coordination"] = (
            (current_avg_agents * (total_coordinations - 1) + agents_used) / total_coordinations
        )
        
        # Track agent combinations
        agent_combination = tuple(sorted(request.required_agents + request.optional_agents))
        self.orchestration_stats["common_agent_combinations"][agent_combination] += 1
    
    def _update_agent_stats(self, agent_name: str, success: bool, execution_time: float) -> None:
        """Update statistics for a specific agent."""
        
        if agent_name not in self.orchestration_stats["agent_success_rates"]:
            self.orchestration_stats["agent_success_rates"][agent_name] = {
                "executions": 0,
                "successes": 0,
                "failures": 0,
                "avg_execution_time": 0.0,
                "success_rate": 1.0
            }
        
        stats = self.orchestration_stats["agent_success_rates"][agent_name]
        stats["executions"] += 1
        
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
        
        # Update success rate
        stats["success_rate"] = stats["successes"] / stats["executions"]
        
        # Update average execution time
        current_avg = stats["avg_execution_time"]
        executions = stats["executions"]
        stats["avg_execution_time"] = (
            (current_avg * (executions - 1) + execution_time) / executions
        )
    
    def get_orchestration_stats(self) -> Dict[str, Any]:
        """Get current orchestration statistics."""
        
        success_rate = 0.0
        if self.orchestration_stats["total_coordinations"] > 0:
            success_rate = (
                self.orchestration_stats["successful_coordinations"] / 
                self.orchestration_stats["total_coordinations"]
            ) * 100
        
        return {
            **self.orchestration_stats,
            "success_rate": success_rate,
            "active_coordinations": len(self.active_coordinations),
            "available_agents": list(self.available_agents.keys())
        }
    
    def __repr__(self) -> str:
        return f"<MultiAgentOrchestrator(agents={len(self.available_agents)}, active={len(self.active_coordinations)})>"