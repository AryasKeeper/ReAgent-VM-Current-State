"""
ReAgent Sydney - Aggregator LangGraph Node

Aggregates results from multiple specialized agents and prepares final output
for the Agent Whisperer node.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import statistics

from .base_node import BaseReAgentNode
from ..state import ReAgentState, AgentStatus


class AggregatorNode(BaseReAgentNode):
    """
    Aggregator node for combining results from specialized agents.
    
    Responsibilities:
    - Collect results from buyer_matchmaker, seller_strategy, off_market_radar
    - Combine and deduplicate data across agents
    - Generate unified insights and recommendations
    - Prepare structured output for Agent Whisperer
    - Calculate cross-agent analytics and metrics
    """
    
    def __init__(self):
        super().__init__("Result Aggregator")

    async def _execute_agent_logic(self, state: ReAgentState) -> Dict[str, Any]:
        """
        Aggregate results from specialized agents.
        
        Args:
            state: Current workflow state with agent results
            
        Returns:
            Aggregated insights and recommendations
        """
        # Get agent results
        agent_results = state.get("agent_results", {})
        
        # Identify completed specialized agents
        specialized_agents = ["buyer_matchmaker", "seller_strategy", "off_market_radar"]
        completed_agents = [
            agent for agent in specialized_agents 
            if agent in agent_results and agent_results[agent].status == AgentStatus.COMPLETED
        ]
        
        if not completed_agents:
            self.logger.warning("No completed specialized agents found for aggregation")
            return {
                "aggregated_insights": {},
                "recommendations": [],
                "cross_agent_analytics": {},
                "summary": "No specialized agent results available for aggregation"
            }
        
        # Aggregate results from completed agents
        aggregated_data = await self._aggregate_agent_results(agent_results, completed_agents)
        
        # Generate cross-agent insights
        cross_insights = await self._generate_cross_agent_insights(aggregated_data, completed_agents)
        
        # Create unified recommendations
        recommendations = await self._create_unified_recommendations(aggregated_data, cross_insights)
        
        # Calculate performance analytics
        analytics = self._calculate_cross_agent_analytics(agent_results, completed_agents)
        
        # Generate executive summary
        summary = self._generate_executive_summary(aggregated_data, completed_agents)
        
        result = {
            "aggregated_insights": aggregated_data,
            "cross_agent_insights": cross_insights,
            "recommendations": recommendations,
            "cross_agent_analytics": analytics,
            "executive_summary": summary,
            "metadata": {
                "aggregation_timestamp": datetime.utcnow().isoformat(),
                "agents_aggregated": completed_agents,
                "total_agents": len(specialized_agents),
                "aggregation_success": True
            }
        }
        
        # Update workflow state with aggregated results
        state["output_data"] = result
        
        self.logger.info(f"Aggregation completed for {len(completed_agents)} agents: {', '.join(completed_agents)}")
        
        return result

    async def _aggregate_agent_results(
        self, 
        agent_results: Dict[str, Any], 
        completed_agents: List[str]
    ) -> Dict[str, Any]:
        """Aggregate data from completed agents."""
        
        aggregated = {
            "properties": [],
            "matches": [],
            "market_insights": {},
            "opportunities": [],
            "buyer_alerts": [],
            "seller_recommendations": [],
            "off_market_leads": []
        }
        
        for agent_name in completed_agents:
            agent_result = agent_results[agent_name]
            agent_data = agent_result.data
            
            if agent_name == "buyer_matchmaker":
                # Aggregate buyer matching results
                aggregated["matches"].extend(agent_data.get("matches", []))
                aggregated["buyer_alerts"].extend(agent_data.get("buyer_alerts", []))
                
                # Add buyer-specific insights
                match_insights = agent_data.get("match_insights", {})
                if match_insights:
                    aggregated["market_insights"]["buyer_demand"] = match_insights
            
            elif agent_name == "seller_strategy":
                # Aggregate seller strategy results
                aggregated["seller_recommendations"].extend(agent_data.get("recommendations", []))
                
                # Add market analysis insights
                market_analysis = agent_data.get("market_analysis", {})
                if market_analysis:
                    aggregated["market_insights"]["seller_market"] = market_analysis
                
                # Add pricing insights
                pricing_insights = agent_data.get("pricing_insights", {})
                if pricing_insights:
                    aggregated["market_insights"]["pricing"] = pricing_insights
            
            elif agent_name == "off_market_radar":
                # Aggregate off-market results
                aggregated["off_market_leads"].extend(agent_data.get("opportunities", []))
                
                # Add opportunity insights
                opportunity_insights = agent_data.get("opportunity_insights", {})
                if opportunity_insights:
                    aggregated["market_insights"]["off_market"] = opportunity_insights
        
        return aggregated

    async def _generate_cross_agent_insights(
        self, 
        aggregated_data: Dict[str, Any], 
        completed_agents: List[str]
    ) -> Dict[str, Any]:
        """Generate insights by comparing data across agents."""
        
        cross_insights = {}
        
        # Market temperature analysis
        if "buyer_matchmaker" in completed_agents and "seller_strategy" in completed_agents:
            cross_insights["market_temperature"] = self._analyze_market_temperature(aggregated_data)
        
        # Supply-demand dynamics
        if len(completed_agents) >= 2:
            cross_insights["supply_demand"] = self._analyze_supply_demand(aggregated_data)
        
        # Opportunity hotspots
        if "off_market_radar" in completed_agents:
            cross_insights["hotspots"] = self._identify_opportunity_hotspots(aggregated_data)
        
        # Price trend correlation
        if "seller_strategy" in completed_agents and aggregated_data.get("matches"):
            cross_insights["price_trends"] = self._analyze_price_trends(aggregated_data)
        
        return cross_insights

    def _analyze_market_temperature(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market temperature based on buyer demand and seller activity."""
        
        matches = data.get("matches", [])
        seller_recs = data.get("seller_recommendations", [])
        
        # Calculate buyer demand intensity
        if matches:
            avg_match_score = statistics.mean([m.get("match_score", 0) for m in matches])
            high_score_matches = len([m for m in matches if m.get("match_score", 0) > 0.8])
            demand_intensity = min(1.0, avg_match_score + (high_score_matches / len(matches)) * 0.3)
        else:
            demand_intensity = 0.0
        
        # Analyze seller market conditions
        seller_urgency_indicators = []
        for rec in seller_recs:
            if rec.get("urgency") == "high":
                seller_urgency_indicators.append(1.0)
            elif rec.get("urgency") == "medium":
                seller_urgency_indicators.append(0.6)
            else:
                seller_urgency_indicators.append(0.3)
        
        seller_pressure = statistics.mean(seller_urgency_indicators) if seller_urgency_indicators else 0.5
        
        # Calculate overall market temperature
        market_temp = (demand_intensity * 0.6) + (seller_pressure * 0.4)
        
        if market_temp > 0.8:
            temperature = "Hot"
            description = "High buyer demand with competitive seller market"
        elif market_temp > 0.6:
            temperature = "Warm"
            description = "Moderate activity with balanced supply/demand"
        elif market_temp > 0.4:
            temperature = "Cool"
            description = "Lower activity with buyer/seller equilibrium"
        else:
            temperature = "Cold"
            description = "Limited activity with potential buyer's market"
        
        return {
            "temperature": temperature,
            "score": round(market_temp, 2),
            "description": description,
            "demand_intensity": round(demand_intensity, 2),
            "seller_pressure": round(seller_pressure, 2)
        }

    def _analyze_supply_demand(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze supply and demand dynamics."""
        
        matches = data.get("matches", [])
        properties = data.get("properties", [])
        
        # Group by suburb for supply/demand analysis
        suburb_analysis = {}
        
        for match in matches:
            property_info = match.get("property_info", {})
            suburb = property_info.get("suburb", "Unknown")
            
            if suburb not in suburb_analysis:
                suburb_analysis[suburb] = {"demand": 0, "supply": 0}
            
            suburb_analysis[suburb]["demand"] += 1
        
        # Count supply by suburb
        for prop in properties:
            suburb = prop.get("suburb", "Unknown")
            if suburb not in suburb_analysis:
                suburb_analysis[suburb] = {"demand": 0, "supply": 0}
            suburb_analysis[suburb]["supply"] += 1
        
        # Calculate demand/supply ratios
        ratios = {}
        for suburb, data in suburb_analysis.items():
            if data["supply"] > 0:
                ratios[suburb] = data["demand"] / data["supply"]
            else:
                ratios[suburb] = data["demand"]  # Infinite demand if no supply
        
        # Find top demand suburbs
        top_demand = sorted(ratios.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "suburb_ratios": ratios,
            "top_demand_suburbs": [{"suburb": s, "ratio": round(r, 2)} for s, r in top_demand],
            "overall_demand_supply_ratio": round(statistics.mean(ratios.values()), 2) if ratios else 0
        }

    def _identify_opportunity_hotspots(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Identify geographic hotspots for opportunities."""
        
        off_market_leads = data.get("off_market_leads", [])
        matches = data.get("matches", [])
        
        # Count opportunities by location
        location_scores = {}
        
        # Score off-market opportunities
        for lead in off_market_leads:
            location = lead.get("suburb", "Unknown")
            score = lead.get("opportunity_score", 0.5)
            
            if location not in location_scores:
                location_scores[location] = []
            location_scores[location].append(score * 1.5)  # Weight off-market higher
        
        # Score buyer matches
        for match in matches:
            property_info = match.get("property_info", {})
            location = property_info.get("suburb", "Unknown")
            score = match.get("match_score", 0.5)
            
            if location not in location_scores:
                location_scores[location] = []
            location_scores[location].append(score)
        
        # Calculate average scores per location
        hotspots = {}
        for location, scores in location_scores.items():
            if scores:
                hotspots[location] = {
                    "avg_score": round(statistics.mean(scores), 2),
                    "opportunity_count": len(scores),
                    "max_score": round(max(scores), 2)
                }
        
        # Sort by average score
        top_hotspots = sorted(
            hotspots.items(), 
            key=lambda x: (x[1]["avg_score"], x[1]["opportunity_count"]), 
            reverse=True
        )[:10]
        
        return {
            "hotspots": dict(hotspots),
            "top_10_hotspots": [
                {"location": loc, **data} for loc, data in top_hotspots
            ]
        }

    def _analyze_price_trends(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze price trends across matched properties."""
        
        matches = data.get("matches", [])
        market_insights = data.get("market_insights", {})
        
        # Extract price data from matches
        price_data = []
        for match in matches:
            property_info = match.get("property_info", {})
            price = property_info.get("price")
            if price and isinstance(price, (int, float)):
                price_data.append({
                    "price": price,
                    "suburb": property_info.get("suburb"),
                    "property_type": property_info.get("property_type"),
                    "match_score": match.get("match_score", 0)
                })
        
        if not price_data:
            return {"trend": "insufficient_data", "message": "Not enough price data for trend analysis"}
        
        # Calculate basic price statistics
        prices = [p["price"] for p in price_data]
        
        return {
            "average_price": round(statistics.mean(prices), 2),
            "median_price": round(statistics.median(prices), 2),
            "price_range": {
                "min": min(prices),
                "max": max(prices)
            },
            "high_value_matches": len([p for p in price_data if p["match_score"] > 0.8]),
            "sample_size": len(price_data)
        }

    async def _create_unified_recommendations(
        self, 
        aggregated_data: Dict[str, Any], 
        cross_insights: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create unified recommendations across all agent results."""
        
        recommendations = []
        
        # High-priority buyer matches
        matches = aggregated_data.get("matches", [])
        high_priority_matches = [m for m in matches if m.get("match_score", 0) > 0.85]
        
        if high_priority_matches:
            recommendations.append({
                "type": "buyer_alert",
                "priority": "high",
                "title": f"{len(high_priority_matches)} High-Priority Buyer Matches Found",
                "description": "Exceptional property matches requiring immediate attention",
                "action": "Review and contact buyers immediately",
                "data": high_priority_matches[:5]  # Top 5
            })
        
        # Market temperature recommendations
        market_temp = cross_insights.get("market_temperature", {})
        if market_temp.get("temperature") == "Hot":
            recommendations.append({
                "type": "market_alert",
                "priority": "high",
                "title": "Hot Market Conditions Detected",
                "description": market_temp.get("description", ""),
                "action": "Prepare for fast-moving market conditions and competitive pricing",
                "data": market_temp
            })
        
        # Off-market opportunities
        off_market = aggregated_data.get("off_market_leads", [])
        high_value_opportunities = [o for o in off_market if o.get("opportunity_score", 0) > 0.8]
        
        if high_value_opportunities:
            recommendations.append({
                "type": "opportunity_alert",
                "priority": "medium",
                "title": f"{len(high_value_opportunities)} High-Value Off-Market Opportunities",
                "description": "Potential off-market deals with strong opportunity indicators",
                "action": "Investigate and contact property owners",
                "data": high_value_opportunities[:3]  # Top 3
            })
        
        # Hotspot recommendations
        hotspots = cross_insights.get("hotspots", {})
        top_hotspots = hotspots.get("top_10_hotspots", [])[:3]
        
        if top_hotspots:
            recommendations.append({
                "type": "geographic_insight",
                "priority": "medium",
                "title": "Top Geographic Hotspots",
                "description": "Areas with highest concentration of opportunities",
                "action": "Focus marketing and sourcing efforts in these areas",
                "data": top_hotspots
            })
        
        return recommendations

    def _calculate_cross_agent_analytics(
        self, 
        agent_results: Dict[str, Any], 
        completed_agents: List[str]
    ) -> Dict[str, Any]:
        """Calculate performance analytics across agents."""
        
        analytics = {
            "execution_performance": {},
            "data_quality": {},
            "coverage_analysis": {}
        }
        
        # Execution performance
        execution_times = []
        for agent in completed_agents:
            exec_time = agent_results[agent].execution_time
            execution_times.append(exec_time)
            analytics["execution_performance"][agent] = {
                "execution_time": round(exec_time, 2),
                "status": "completed"
            }
        
        if execution_times:
            analytics["execution_performance"]["summary"] = {
                "total_time": round(sum(execution_times), 2),
                "average_time": round(statistics.mean(execution_times), 2),
                "parallel_efficiency": round(max(execution_times) / sum(execution_times), 2)
            }
        
        # Data quality metrics
        for agent in completed_agents:
            agent_data = agent_results[agent].data
            
            if agent == "buyer_matchmaker":
                matches = agent_data.get("matches", [])
                analytics["data_quality"]["buyer_matchmaker"] = {
                    "matches_generated": len(matches),
                    "high_quality_matches": len([m for m in matches if m.get("match_score", 0) > 0.8]),
                    "avg_match_score": round(statistics.mean([m.get("match_score", 0) for m in matches]), 2) if matches else 0
                }
        
        return analytics

    def _generate_executive_summary(
        self, 
        aggregated_data: Dict[str, Any], 
        completed_agents: List[str]
    ) -> str:
        """Generate executive summary of all results."""
        
        summary_parts = []
        
        # Overview
        summary_parts.append(f"Workflow completed successfully with {len(completed_agents)} specialized agents.")
        
        # Key metrics
        matches_count = len(aggregated_data.get("matches", []))
        opportunities_count = len(aggregated_data.get("off_market_leads", []))
        recommendations_count = len(aggregated_data.get("seller_recommendations", []))
        
        metrics = []
        if matches_count > 0:
            metrics.append(f"{matches_count} buyer matches")
        if opportunities_count > 0:
            metrics.append(f"{opportunities_count} off-market opportunities")
        if recommendations_count > 0:
            metrics.append(f"{recommendations_count} seller recommendations")
        
        if metrics:
            summary_parts.append(f"Generated {', '.join(metrics)}.")
        
        # High-priority items
        high_priority_matches = len([m for m in aggregated_data.get("matches", []) if m.get("match_score", 0) > 0.85])
        if high_priority_matches > 0:
            summary_parts.append(f"⚠️ {high_priority_matches} high-priority matches require immediate attention.")
        
        return " ".join(summary_parts)

    def __repr__(self) -> str:
        return f"<AggregatorNode()>"