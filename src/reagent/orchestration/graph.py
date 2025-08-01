"""
ReAgent Sydney - LangGraph Workflow Graph

Defines the DAG structure and orchestration logic for the 6 core agents:
1. Listing Watcher AU
2. Suburb Signal Agent  
3. Buyer Matchmaker AU
4. Seller Strategy Agent
5. Off-Market Radar AU
6. Agent Whisperer
"""

from typing import Dict, List, Optional, Any, Callable, Literal
from datetime import datetime
import uuid

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .state import ReAgentState, WorkflowStatus, AgentStatus, AgentResult, create_initial_state, update_agent_result
from .nodes import (
    ListingWatcherNode,
    SuburbSignalNode, 
    BuyerMatchmakerNode,
    SellerStrategyNode,
    OffMarketRadarNode,
    AgentWhispererNode,
    RouterNode,
    AggregatorNode
)
from .checkpoints import PostgreSQLCheckpointer
from ..core.cache.redis_client import get_cache_manager
from ..core.vector_db.client import get_weaviate_client
from ..utils.logging import get_logger
from ..utils.monitoring.metrics import get_metrics_client


logger = get_logger(__name__)


class ReAgentWorkflowType:
    """Predefined workflow types for ReAgent Sydney."""
    
    # Core workflows
    PROPERTY_MONITORING = "property_monitoring"
    BUYER_MATCHING = "buyer_matching"  
    MARKET_ANALYSIS = "market_analysis"
    SELLER_STRATEGY = "seller_strategy"
    OFF_MARKET_DISCOVERY = "off_market_discovery"
    
    # Composite workflows
    FULL_PIPELINE = "full_pipeline"
    DAILY_INTELLIGENCE = "daily_intelligence"
    ALERT_PROCESSING = "alert_processing"


class ReAgentWorkflowGraph:
    """
    Production-ready LangGraph workflow orchestrator for ReAgent Sydney.
    
    Features:
    - 6 core agent nodes with intelligent routing
    - PostgreSQL checkpointing for state persistence  
    - Redis caching for performance optimization
    - Weaviate vector operations integration
    - Prometheus monitoring and alerting
    - Error handling and recovery mechanisms
    """
    
    def __init__(
        self,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        enable_monitoring: bool = True
    ):
        self.checkpointer = checkpointer
        self.enable_monitoring = enable_monitoring
        
        # Initialize services
        self.cache_manager = get_cache_manager()
        self.weaviate_client = get_weaviate_client()
        self.metrics_client = get_metrics_client() if enable_monitoring else None
        
        # Initialize nodes
        self._initialize_nodes()
        
        # Build graphs for different workflow types
        self.graphs = self._build_workflow_graphs()
        
        logger.info("ReAgent workflow graph initialized successfully")

    def _initialize_nodes(self) -> None:
        """Initialize all agent nodes."""
        self.nodes = {
            "listing_watcher": ListingWatcherNode(),
            "suburb_signal": SuburbSignalNode(),
            "buyer_matchmaker": BuyerMatchmakerNode(),
            "seller_strategy": SellerStrategyNode(),
            "off_market_radar": OffMarketRadarNode(),
            "agent_whisperer": AgentWhispererNode(),
            "router": RouterNode(),
            "aggregator": AggregatorNode()
        }

    def _build_workflow_graphs(self) -> Dict[str, StateGraph]:
        """Build different workflow graph configurations."""
        graphs = {}
        
        # Full pipeline workflow (all 6 agents)
        graphs[ReAgentWorkflowType.FULL_PIPELINE] = self._build_full_pipeline_graph()
        
        # Property monitoring workflow
        graphs[ReAgentWorkflowType.PROPERTY_MONITORING] = self._build_property_monitoring_graph()
        
        # Buyer matching workflow
        graphs[ReAgentWorkflowType.BUYER_MATCHING] = self._build_buyer_matching_graph()
        
        # Market analysis workflow
        graphs[ReAgentWorkflowType.MARKET_ANALYSIS] = self._build_market_analysis_graph()
        
        # Off-market discovery workflow
        graphs[ReAgentWorkflowType.OFF_MARKET_DISCOVERY] = self._build_off_market_discovery_graph()
        
        return graphs

    def _build_full_pipeline_graph(self) -> StateGraph:
        """
        Build the complete ReAgent pipeline workflow.
        
        Flow:
        START -> Listing Watcher -> Suburb Signal -> Router -> [Buyer Matching | Seller Strategy | Off-Market] -> Agent Whisperer -> END
        """
        graph = StateGraph(ReAgentState)
        
        # Add nodes
        graph.add_node("listing_watcher", self.nodes["listing_watcher"])
        graph.add_node("suburb_signal", self.nodes["suburb_signal"])
        graph.add_node("router", self.nodes["router"])
        graph.add_node("buyer_matchmaker", self.nodes["buyer_matchmaker"])
        graph.add_node("seller_strategy", self.nodes["seller_strategy"])
        graph.add_node("off_market_radar", self.nodes["off_market_radar"])
        graph.add_node("agent_whisperer", self.nodes["agent_whisperer"])
        graph.add_node("aggregator", self.nodes["aggregator"])
        
        # Define edges
        graph.add_edge(START, "listing_watcher")
        graph.add_edge("listing_watcher", "suburb_signal")
        graph.add_edge("suburb_signal", "router")
        
        # Conditional routing based on workflow requirements
        graph.add_conditional_edges(
            "router",
            self._route_to_specialized_agents,
            {
                "buyer_matching": "buyer_matchmaker",
                "seller_strategy": "seller_strategy", 
                "off_market": "off_market_radar",
                "all": ["buyer_matchmaker", "seller_strategy", "off_market_radar"]
            }
        )
        
        # All specialized agents flow to aggregator
        graph.add_edge("buyer_matchmaker", "aggregator")
        graph.add_edge("seller_strategy", "aggregator")
        graph.add_edge("off_market_radar", "aggregator")
        
        # Final processing
        graph.add_edge("aggregator", "agent_whisperer")
        graph.add_edge("agent_whisperer", END)
        
        return graph.compile(checkpointer=self.checkpointer)

    def _build_property_monitoring_graph(self) -> StateGraph:
        """Build property monitoring focused workflow."""
        graph = StateGraph(ReAgentState)
        
        graph.add_node("listing_watcher", self.nodes["listing_watcher"])
        graph.add_node("suburb_signal", self.nodes["suburb_signal"])
        graph.add_node("agent_whisperer", self.nodes["agent_whisperer"])
        
        graph.add_edge(START, "listing_watcher")
        graph.add_edge("listing_watcher", "suburb_signal") 
        graph.add_edge("suburb_signal", "agent_whisperer")
        graph.add_edge("agent_whisperer", END)
        
        return graph.compile(checkpointer=self.checkpointer)

    def _build_buyer_matching_graph(self) -> StateGraph:
        """Build buyer matching focused workflow."""
        graph = StateGraph(ReAgentState)
        
        graph.add_node("listing_watcher", self.nodes["listing_watcher"])
        graph.add_node("buyer_matchmaker", self.nodes["buyer_matchmaker"])
        graph.add_node("agent_whisperer", self.nodes["agent_whisperer"])
        
        graph.add_edge(START, "listing_watcher")
        graph.add_edge("listing_watcher", "buyer_matchmaker")
        graph.add_edge("buyer_matchmaker", "agent_whisperer")
        graph.add_edge("agent_whisperer", END)
        
        return graph.compile(checkpointer=self.checkpointer)

    def _build_market_analysis_graph(self) -> StateGraph:
        """Build market analysis focused workflow."""
        graph = StateGraph(ReAgentState)
        
        graph.add_node("listing_watcher", self.nodes["listing_watcher"])
        graph.add_node("suburb_signal", self.nodes["suburb_signal"])
        graph.add_node("seller_strategy", self.nodes["seller_strategy"])
        graph.add_node("agent_whisperer", self.nodes["agent_whisperer"])
        
        graph.add_edge(START, "listing_watcher")
        graph.add_edge("listing_watcher", "suburb_signal")
        graph.add_edge("suburb_signal", "seller_strategy")
        graph.add_edge("seller_strategy", "agent_whisperer")
        graph.add_edge("agent_whisperer", END)
        
        return graph.compile(checkpointer=self.checkpointer)

    def _build_off_market_discovery_graph(self) -> StateGraph:
        """Build off-market discovery focused workflow."""
        graph = StateGraph(ReAgentState)
        
        graph.add_node("listing_watcher", self.nodes["listing_watcher"])
        graph.add_node("off_market_radar", self.nodes["off_market_radar"])
        graph.add_node("agent_whisperer", self.nodes["agent_whisperer"])
        
        graph.add_edge(START, "listing_watcher")
        graph.add_edge("listing_watcher", "off_market_radar")
        graph.add_edge("off_market_radar", "agent_whisperer")
        graph.add_edge("agent_whisperer", END)
        
        return graph.compile(checkpointer=self.checkpointer)

    def _route_to_specialized_agents(self, state: ReAgentState) -> str:
        """
        Intelligent routing logic to determine which specialized agents to run.
        
        Args:
            state: Current workflow state
            
        Returns:
            Routing decision string
        """
        # Check workflow configuration
        config = state.get("config", {})
        workflow_type = config.get("workflow_type", "full_pipeline")
        
        # Route based on input data and configuration
        if workflow_type == ReAgentWorkflowType.BUYER_MATCHING:
            return "buyer_matching"
        elif workflow_type == ReAgentWorkflowType.SELLER_STRATEGY:
            return "seller_strategy"
        elif workflow_type == ReAgentWorkflowType.OFF_MARKET_DISCOVERY:
            return "off_market"
        else:
            # For full pipeline, run all specialized agents
            return "all"

    async def execute_workflow(
        self,
        workflow_type: str,
        input_data: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow with specified type and input.
        
        Args:
            workflow_type: Type of workflow to execute
            input_data: Input data for the workflow
            config: Configuration parameters
            thread_id: Optional thread ID for state persistence
            
        Returns:
            Workflow execution result
        """
        if workflow_type not in self.graphs:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
        
        # Generate IDs
        workflow_id = str(uuid.uuid4())
        if not thread_id:
            thread_id = f"reagent_{workflow_type}_{workflow_id}"
        
        # Create initial state
        initial_state = create_initial_state(
            workflow_id=workflow_id,
            workflow_name=f"ReAgent {workflow_type.replace('_', ' ').title()}",
            input_data=input_data,
            config={**(config or {}), "workflow_type": workflow_type}
        )
        
        # Set up runnable config
        runnable_config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": workflow_type
            }
        }
        
        try:
            logger.info(f"Starting workflow {workflow_type} with ID {workflow_id}")
            
            # Record workflow start metrics
            if self.metrics_client:
                self.metrics_client.increment("reagent.workflow.started", tags=[f"type:{workflow_type}"])
            
            # Execute the workflow graph
            graph = self.graphs[workflow_type]
            final_state = await graph.ainvoke(initial_state, config=runnable_config)
            
            # Record completion metrics
            if self.metrics_client:
                self.metrics_client.increment("reagent.workflow.completed", tags=[f"type:{workflow_type}"])
                
                # Record execution time if available
                if "metrics" in final_state and hasattr(final_state["metrics"], "execution_time"):
                    self.metrics_client.histogram(
                        "reagent.workflow.execution_time",
                        final_state["metrics"].execution_time,
                        tags=[f"type:{workflow_type}"]
                    )
            
            logger.info(f"Workflow {workflow_type} completed successfully")
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                "thread_id": thread_id,
                "workflow_type": workflow_type,
                "status": final_state["status"],
                "output_data": final_state["output_data"],
                "agent_results": final_state["agent_results"],
                "metrics": final_state.get("metrics", {}),
                "execution_time": (final_state["updated_at"] - final_state["created_at"]).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Workflow {workflow_type} failed: {e}", exc_info=True)
            
            # Record failure metrics
            if self.metrics_client:
                self.metrics_client.increment("reagent.workflow.failed", tags=[f"type:{workflow_type}"])
            
            return {
                "success": False,
                "workflow_id": workflow_id,
                "thread_id": thread_id,
                "workflow_type": workflow_type,
                "error": str(e)
            }

    async def get_workflow_status(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a workflow."""
        if isinstance(self.checkpointer, PostgreSQLCheckpointer):
            return await self.checkpointer.get_workflow_status(thread_id)
        return None

    async def list_active_workflows(self) -> List[Dict[str, Any]]:
        """List all currently active workflows."""
        if isinstance(self.checkpointer, PostgreSQLCheckpointer):
            return await self.checkpointer.get_active_workflows()
        return []

    def get_available_workflows(self) -> List[str]:
        """Get list of available workflow types."""
        return list(self.graphs.keys())

    async def cleanup_old_workflows(self, older_than_days: int = 30) -> int:
        """Cleanup old workflow checkpoints."""
        if isinstance(self.checkpointer, PostgreSQLCheckpointer):
            return await self.checkpointer.cleanup_old_checkpoints(older_than_days)
        return 0

    def __repr__(self) -> str:
        return f"<ReAgentWorkflowGraph(workflows={len(self.graphs)}, checkpointer={type(self.checkpointer).__name__})>"