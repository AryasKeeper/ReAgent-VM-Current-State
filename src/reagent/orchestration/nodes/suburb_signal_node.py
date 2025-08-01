"""
ReAgent Sydney - Suburb Signal LangGraph Node

LangGraph node implementation for the Suburb Signal Agent.
Analyzes micro-trends and market signals by suburb/postcode.
"""

from typing import Dict, Any, List
from datetime import datetime

from .base_node import BaseReAgentNode
from ..state import ReAgentState


class SuburbSignalNode(BaseReAgentNode):
    """
    LangGraph node for Suburb Signal Agent.
    
    Responsibilities:
    - Analyze suburb-level market trends
    - Generate micro-market insights
    - Track postcode-specific indicators
    - Provide location intelligence for other agents
    """
    
    def __init__(self):
        super().__init__("Suburb Signal Agent")

    async def _execute_agent_logic(self, state: ReAgentState) -> Dict[str, Any]:
        """Execute suburb signal analysis logic."""
        
        # Get properties from previous agents
        properties = state.get("properties", [])
        
        # Extract unique suburbs for analysis
        suburbs = set()
        for prop in properties:
            suburb = prop.get("suburb")
            if suburb:
                suburbs.add(suburb.upper())
        
        # Analyze each suburb
        suburb_insights = {}
        for suburb in suburbs:
            suburb_properties = [p for p in properties if p.get("suburb", "").upper() == suburb]
            suburb_insights[suburb] = await self._analyze_suburb(suburb, suburb_properties)
        
        result = {
            "suburb_insights": suburb_insights,
            "market_signals": await self._generate_market_signals(suburb_insights),
            "trend_analysis": await self._analyze_trends(suburb_insights),
            "statistics": {
                "suburbs_analyzed": len(suburbs),
                "total_properties": len(properties),
                "execution_time": 0
            }
        }
        
        # Update state market insights
        if "market_insights" not in state:
            state["market_insights"] = {}
        state["market_insights"]["suburb_signals"] = result
        
        return result

    async def _analyze_suburb(self, suburb: str, properties: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a specific suburb."""
        
        if not properties:
            return {"status": "no_data", "property_count": 0}
        
        # Basic statistics
        prices = [p.get("price", 0) for p in properties if p.get("price")]
        property_types = [p.get("property_type") for p in properties if p.get("property_type")]
        
        analysis = {
            "property_count": len(properties),
            "avg_price": sum(prices) / len(prices) if prices else 0,
            "price_range": {"min": min(prices), "max": max(prices)} if prices else {},
            "dominant_property_type": max(set(property_types), key=property_types.count) if property_types else None,
            "market_activity": "active" if len(properties) > 5 else "moderate" if len(properties) > 2 else "low"
        }
        
        return analysis

    async def _generate_market_signals(self, suburb_insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate market signals from suburb analysis."""
        
        signals = []
        
        for suburb, data in suburb_insights.items():
            if data.get("market_activity") == "active" and data.get("property_count", 0) > 10:
                signals.append({
                    "type": "high_activity",
                    "suburb": suburb,
                    "strength": "strong",
                    "description": f"High market activity detected in {suburb}"
                })
        
        return signals

    async def _analyze_trends(self, suburb_insights: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trends across suburbs."""
        
        active_suburbs = [
            suburb for suburb, data in suburb_insights.items() 
            if data.get("market_activity") == "active"
        ]
        
        return {
            "active_suburb_count": len(active_suburbs),
            "total_suburbs": len(suburb_insights),
            "activity_ratio": len(active_suburbs) / len(suburb_insights) if suburb_insights else 0
        }

    def __repr__(self) -> str:
        return f"<SuburbSignalNode()>"