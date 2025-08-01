"""
ReAgent Sydney - LangGraph State Management

Defines the state structures used throughout the LangGraph orchestration system.
"""

from typing import Dict, List, Optional, Any, TypedDict, Annotated
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(str, Enum):
    """Individual agent status."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentResult:
    """Result from an individual agent execution."""
    agent_name: str
    status: AgentStatus
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass 
class WorkflowMetrics:
    """Workflow execution metrics."""
    total_agents: int = 0
    completed_agents: int = 0
    failed_agents: int = 0
    execution_time: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class ReAgentState(TypedDict):
    """
    Core state structure for ReAgent Sydney LangGraph workflows.
    
    This state is passed between all nodes in the workflow and maintains
    the complete execution context.
    """
    
    # Core Workflow State
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime
    
    # Messages (LangGraph standard)
    messages: Annotated[List[BaseMessage], "The conversation messages"]
    
    # Input/Output Data
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    
    # Agent Results
    agent_results: Dict[str, AgentResult]
    
    # Current Execution Context
    current_agent: Optional[str]
    next_agents: List[str]
    completed_agents: List[str]
    failed_agents: List[str]
    
    # Data Pipeline State
    properties: List[Dict[str, Any]]
    buyer_profiles: List[Dict[str, Any]]
    matches: List[Dict[str, Any]]
    market_insights: Dict[str, Any]
    
    # Configuration
    config: Dict[str, Any]
    
    # Error Handling
    errors: List[Dict[str, Any]]
    retry_count: int
    
    # Metrics
    metrics: WorkflowMetrics


class WorkflowState(TypedDict):
    """
    Extended state for specific workflow types.
    """
    
    # Inherits all ReAgentState fields
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    
    # Workflow-specific data
    workflow_type: str
    trigger_source: str
    priority: str
    
    # Scheduling
    scheduled_at: Optional[datetime]
    timeout_at: Optional[datetime]
    
    # Dependencies
    depends_on: List[str]
    dependent_workflows: List[str]


# Predefined workflow state templates
DEFAULT_REAGENT_STATE: ReAgentState = {
    "workflow_id": "",
    "workflow_name": "",
    "status": WorkflowStatus.PENDING,
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
    "messages": [],
    "input_data": {},
    "output_data": {},
    "agent_results": {},
    "current_agent": None,
    "next_agents": [],
    "completed_agents": [],
    "failed_agents": [],
    "properties": [],
    "buyer_profiles": [],
    "matches": [],
    "market_insights": {},
    "config": {},
    "errors": [],
    "retry_count": 0,
    "metrics": WorkflowMetrics()
}


def create_initial_state(
    workflow_id: str,
    workflow_name: str,
    input_data: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None
) -> ReAgentState:
    """
    Create an initial state for a new workflow execution.
    
    Args:
        workflow_id: Unique identifier for the workflow
        workflow_name: Human-readable name for the workflow
        input_data: Initial input data for the workflow
        config: Configuration parameters for the workflow
    
    Returns:
        Initialized ReAgentState
    """
    state = DEFAULT_REAGENT_STATE.copy()
    state.update({
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "input_data": input_data or {},
        "config": config or {},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "messages": [HumanMessage(content=f"Starting workflow: {workflow_name}")]
    })
    
    return state


def update_agent_result(
    state: ReAgentState,
    agent_name: str,
    result: AgentResult
) -> ReAgentState:
    """
    Update state with an agent execution result.
    
    Args:
        state: Current workflow state
        agent_name: Name of the agent that executed
        result: Result from the agent execution
    
    Returns:
        Updated state
    """
    # Update agent results
    state["agent_results"][agent_name] = result
    
    # Update agent tracking lists
    if result.status == AgentStatus.COMPLETED:
        if agent_name not in state["completed_agents"]:
            state["completed_agents"].append(agent_name)
            
        # Remove from failed agents if it was there
        if agent_name in state["failed_agents"]:
            state["failed_agents"].remove(agent_name)
            
    elif result.status == AgentStatus.FAILED:
        if agent_name not in state["failed_agents"]:
            state["failed_agents"].append(agent_name)
            
        # Add error to state
        state["errors"].append({
            "agent": agent_name,
            "error": result.error,
            "timestamp": result.timestamp
        })
    
    # Update workflow status based on agent results
    total_agents = len(state["agent_results"])
    completed_agents = len(state["completed_agents"])
    failed_agents = len(state["failed_agents"])
    
    if failed_agents > 0 and completed_agents + failed_agents == total_agents:
        state["status"] = WorkflowStatus.FAILED
    elif completed_agents == total_agents:
        state["status"] = WorkflowStatus.COMPLETED
    else:
        state["status"] = WorkflowStatus.RUNNING
    
    # Update timestamp
    state["updated_at"] = datetime.utcnow()
    
    # Add result to messages
    if result.status == AgentStatus.COMPLETED:
        state["messages"].append(
            AIMessage(content=f"Agent {agent_name} completed successfully")
        )
    elif result.status == AgentStatus.FAILED:
        state["messages"].append(
            AIMessage(content=f"Agent {agent_name} failed: {result.error}")
        )
    
    return state


def get_next_agents(
    state: ReAgentState,
    workflow_graph: Dict[str, List[str]]
) -> List[str]:
    """
    Determine the next agents to execute based on completed agents and workflow graph.
    
    Args:
        state: Current workflow state
        workflow_graph: Dictionary mapping agent names to their dependencies
    
    Returns:
        List of agent names ready to execute
    """
    completed = set(state["completed_agents"])
    failed = set(state["failed_agents"])
    next_agents = []
    
    for agent, dependencies in workflow_graph.items():
        # Skip if already completed or failed
        if agent in completed or agent in failed:
            continue
        
        # Check if all dependencies are completed
        if all(dep in completed for dep in dependencies):
            next_agents.append(agent)
    
    return next_agents