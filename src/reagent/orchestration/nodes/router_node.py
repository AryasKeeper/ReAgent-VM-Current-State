"""
ReAgent Sydney - Router LangGraph Node

Intelligent routing node that determines which specialized agents should execute
based on the workflow state and configuration.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_node import BaseReAgentNode
from ..state import ReAgentState


class RouterNode(BaseReAgentNode):
    """
    Intelligent router node for ReAgent workflows.
    
    Responsibilities:
    - Analyze workflow state and requirements
    - Determine which specialized agents should execute
    - Set execution priorities and dependencies
    - Configure agent-specific parameters
    - Handle conditional workflow branching
    """
    
    def __init__(self):
        super().__init__("Workflow Router")
        
        # Routing configuration
        self.agent_priorities = {
            "buyer_matchmaker": 1,
            "seller_strategy": 2,
            "off_market_radar": 3
        }

    async def _execute_agent_logic(self, state: ReAgentState) -> Dict[str, Any]:
        """
        Execute routing logic to determine next agents.
        
        Args:
            state: Current workflow state
            
        Returns:
            Routing decisions and agent configurations
        """
        # Get workflow configuration
        config = state.get("config", {})
        input_data = state.get("input_data", {})
        
        # Analyze current state
        properties = state.get("properties", [])
        workflow_type = config.get("workflow_type", "full_pipeline")
        
        # Determine routing strategy
        routing_decisions = await self._analyze_routing_requirements(
            state, properties, workflow_type, config, input_data
        )
        
        # Configure agent-specific parameters
        agent_configs = await self._configure_agent_parameters(
            routing_decisions, properties, config
        )
        
        # Set execution priorities
        execution_plan = self._create_execution_plan(routing_decisions, agent_configs)
        
        result = {
            "routing_decisions": routing_decisions,
            "agent_configurations": agent_configs,
            "execution_plan": execution_plan,
            "metadata": {
                "router_timestamp": datetime.utcnow().isoformat(),
                "workflow_type": workflow_type,
                "properties_count": len(properties),
                "routing_strategy": self._get_routing_strategy(workflow_type)
            }
        }
        
        # Update state with routing decisions
        state["next_agents"] = routing_decisions.get("agents_to_execute", [])
        
        self.logger.info(
            f"Routing completed: {len(routing_decisions.get('agents_to_execute', []))} agents selected for execution"
        )
        
        return result

    async def _analyze_routing_requirements(
        self,
        state: ReAgentState,
        properties: List[Dict[str, Any]],
        workflow_type: str,
        config: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze requirements to determine which agents should execute."""
        
        routing_decisions = {
            "agents_to_execute": [],
            "agents_to_skip": [],
            "routing_reasons": {},
            "conditional_execution": {}
        }
        
        # Base routing on workflow type
        if workflow_type == "full_pipeline":
            # Execute all specialized agents
            agents_to_execute = ["buyer_matchmaker", "seller_strategy", "off_market_radar"]
            
        elif workflow_type == "buyer_matching":
            agents_to_execute = ["buyer_matchmaker"]
            
        elif workflow_type == "seller_strategy":
            agents_to_execute = ["seller_strategy"]
            
        elif workflow_type == "off_market_discovery":
            agents_to_execute = ["off_market_radar"]
            
        elif workflow_type == "market_analysis":
            agents_to_execute = ["seller_strategy"]  # Market analysis is part of seller strategy
            
        else:
            # Default to buyer matching if unknown
            agents_to_execute = ["buyer_matchmaker"]
            routing_decisions["routing_reasons"]["default"] = f"Unknown workflow type '{workflow_type}', defaulting to buyer_matchmaker"
        
        # Apply conditional logic based on data availability
        if not properties:
            # No properties available, skip all agents that require property data
            agents_to_execute = []
            routing_decisions["routing_reasons"]["no_properties"] = "No properties available, skipping property-dependent agents"
        
        # Check for specific user requests
        user_requests = input_data.get("requested_agents", [])
        if user_requests:
            # Override with user-requested agents if they're valid
            valid_requests = [agent for agent in user_requests if agent in ["buyer_matchmaker", "seller_strategy", "off_market_radar"]]
            if valid_requests:
                agents_to_execute = valid_requests
                routing_decisions["routing_reasons"]["user_request"] = f"User requested specific agents: {valid_requests}"
        
        # Apply resource-based constraints
        max_concurrent_agents = config.get("max_concurrent_agents", 3)
        if len(agents_to_execute) > max_concurrent_agents:
            # Prioritize agents based on configuration
            prioritized = sorted(agents_to_execute, key=lambda x: self.agent_priorities.get(x, 999))
            agents_to_execute = prioritized[:max_concurrent_agents]
            routing_decisions["routing_reasons"]["resource_limit"] = f"Limited to {max_concurrent_agents} concurrent agents"
        
        # Check for agent-specific requirements
        final_agents = []
        for agent in agents_to_execute:
            if await self._check_agent_requirements(agent, state, properties):
                final_agents.append(agent)
            else:
                routing_decisions["agents_to_skip"].append(agent)
                routing_decisions["routing_reasons"][f"{agent}_skipped"] = f"Agent {agent} requirements not met"
        
        routing_decisions["agents_to_execute"] = final_agents
        
        return routing_decisions

    async def _check_agent_requirements(
        self, 
        agent_name: str, 
        state: ReAgentState, 
        properties: List[Dict[str, Any]]
    ) -> bool:
        """Check if an agent's requirements are met."""
        
        if agent_name == "buyer_matchmaker":
            # Requires properties and active buyers
            if not properties:
                return False
            
            # Check if there are active buyers (from cache or quick DB check)
            active_buyers_count = await self._cache_get("active_buyers_count")
            if active_buyers_count is not None and active_buyers_count == 0:
                return False
        
        elif agent_name == "seller_strategy":
            # Requires properties for analysis
            if not properties:
                return False
        
        elif agent_name == "off_market_radar":
            # Can run with or without current properties (looks for off-market opportunities)
            pass
        
        return True

    async def _configure_agent_parameters(
        self,
        routing_decisions: Dict[str, Any],
        properties: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Configure parameters for each agent to execute."""
        
        agent_configs = {}
        agents_to_execute = routing_decisions.get("agents_to_execute", [])
        
        for agent in agents_to_execute:
            if agent == "buyer_matchmaker":
                agent_configs[agent] = {
                    "min_match_score": config.get("buyer_match_min_score", 0.7),
                    "max_matches_per_buyer": config.get("max_matches_per_buyer", 10),
                    "prioritize_new_listings": True,
                    "enable_vector_search": True,
                    "notification_enabled": config.get("buyer_notifications_enabled", True)
                }
                
            elif agent == "seller_strategy":
                agent_configs[agent] = {
                    "include_pricing_analysis": True,
                    "include_market_timing": True,
                    "include_competitor_analysis": True,
                    "analysis_depth": config.get("seller_analysis_depth", "comprehensive"),
                    "suburb_focus": self._extract_unique_suburbs(properties)
                }
                
            elif agent == "off_market_radar":
                agent_configs[agent] = {
                    "include_expired_listings": True,
                    "include_council_da": True,
                    "include_distress_signals": True,
                    "days_back": config.get("off_market_days_back", 30),
                    "min_opportunity_score": config.get("off_market_min_score", 0.6)
                }
        
        return agent_configs

    def _create_execution_plan(
        self,
        routing_decisions: Dict[str, Any],
        agent_configs: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create execution plan with priorities and dependencies."""
        
        agents_to_execute = routing_decisions.get("agents_to_execute", [])
        
        execution_plan = {
            "sequential_execution": False,  # Most agents can run in parallel
            "agent_priorities": {},
            "dependencies": {},
            "estimated_execution_time": 0
        }
        
        # Set priorities (lower number = higher priority)
        for agent in agents_to_execute:
            execution_plan["agent_priorities"][agent] = self.agent_priorities.get(agent, 999)
        
        # Set dependencies (currently none between specialized agents)
        execution_plan["dependencies"] = {agent: [] for agent in agents_to_execute}
        
        # Estimate execution time based on agents selected
        time_estimates = {
            "buyer_matchmaker": 120,  # 2 minutes
            "seller_strategy": 180,   # 3 minutes
            "off_market_radar": 240   # 4 minutes
        }
        
        if len(agents_to_execute) <= 1:
            # Sequential execution
            execution_plan["estimated_execution_time"] = sum(
                time_estimates.get(agent, 60) for agent in agents_to_execute
            )
        else:
            # Parallel execution - take the longest
            execution_plan["estimated_execution_time"] = max(
                time_estimates.get(agent, 60) for agent in agents_to_execute
            ) if agents_to_execute else 0
        
        return execution_plan

    def _extract_unique_suburbs(self, properties: List[Dict[str, Any]]) -> List[str]:
        """Extract unique suburbs from properties for targeted analysis."""
        suburbs = set()
        for prop in properties:
            suburb = prop.get("suburb")
            if suburb:
                suburbs.add(suburb.upper())
        return list(suburbs)

    def _get_routing_strategy(self, workflow_type: str) -> str:
        """Get human-readable routing strategy description."""
        strategies = {
            "full_pipeline": "Execute all specialized agents in parallel",
            "buyer_matching": "Focus on buyer-property matching only",
            "seller_strategy": "Focus on seller strategy and market analysis",
            "off_market_discovery": "Focus on off-market opportunity discovery",
            "market_analysis": "Focus on market analysis and trends"
        }
        return strategies.get(workflow_type, "Default routing strategy")

    def __repr__(self) -> str:
        return f"<RouterNode(priorities={len(self.agent_priorities)})>"