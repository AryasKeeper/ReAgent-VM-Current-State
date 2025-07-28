"""
ReAgent Sydney - Agent Whisperer

Natural language interface and report generation system that serves as the primary
communication layer between real estate agents and the ReAgent Sydney multi-agent system.

Core Responsibilities:
- Process natural language queries from real estate agents
- Generate comprehensive market reports and analysis documents
- Coordinate with all other ReAgent agents for comprehensive intelligence
- Provide intuitive, conversational access to market data
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import re
from dataclasses import dataclass, field

from langchain.tools import Tool
from langchain.schema import BaseMessage

from ..base import BaseReAgentAgent, AgentConfig, AgentRole, AgentPriority
from .nlp_processor import NaturalLanguageProcessor, QueryIntent, IntentClassification
from .report_generator import ReportGenerator, ReportTemplate, ReportType
from .conversation_manager import ConversationManager, ConversationContext
from .multi_agent_orchestrator import MultiAgentOrchestrator, AgentCoordinationRequest
from .tools import WhispererToolKit


class ResponseType(str, Enum):
    """Types of responses the Agent Whisperer can provide."""
    DIRECT_ANSWER = "direct_answer"
    REPORT = "report"
    CLARIFICATION = "clarification" 
    ERROR = "error"
    GUIDANCE = "guidance"


class QueryComplexity(str, Enum):
    """Complexity levels for incoming queries."""
    SIMPLE = "simple"          # Single agent, quick response
    MODERATE = "moderate"      # Multiple data points, basic coordination
    COMPLEX = "complex"        # Multi-agent orchestration required
    ADVANCED = "advanced"      # Custom analysis and reporting


@dataclass
class WhispererResponse:
    """Structured response from the Agent Whisperer."""
    
    response_type: ResponseType
    content: str
    query_intent: Optional[QueryIntent] = None
    confidence_score: float = 0.0
    execution_time: float = 0.0
    
    # Additional data
    report_data: Optional[Dict[str, Any]] = None
    follow_up_suggestions: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    
    # Context for conversation continuity
    conversation_context: Optional[Dict[str, Any]] = None
    requires_follow_up: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary for API serialization."""
        return {
            "response_type": self.response_type.value,
            "content": self.content,
            "confidence_score": self.confidence_score,
            "execution_time": self.execution_time,
            "report_data": self.report_data,
            "follow_up_suggestions": self.follow_up_suggestions,
            "data_sources": self.data_sources,
            "requires_follow_up": self.requires_follow_up,
            "timestamp": datetime.utcnow().isoformat()
        }


class AgentWhispererAgent(BaseReAgentAgent):
    """
    The Agent Whisperer - Natural Language Interface for ReAgent Sydney.
    
    This agent serves as the friendly, intelligent interface that makes the power 
    of the ReAgent Sydney system accessible to real estate professionals through 
    natural conversation and beautiful, actionable reports.
    
    Key capabilities:
    - Natural language query understanding and processing
    - Multi-agent coordination for comprehensive market intelligence
    - Professional report generation for various real estate scenarios
    - Context-aware conversation management
    - User guidance and query optimization suggestions
    """
    
    def __init__(self):
        config = AgentConfig(
            name="Agent Whisperer",
            role=AgentRole.COMMUNICATOR,
            description="Natural language interface and report generation system for ReAgent Sydney",
            version="1.0.0",
            max_execution_time=120,  # 2 minutes for complex queries
            max_retries=2,
            priority=AgentPriority.HIGH,
            required_services=["database", "cache"],
            required_tools=["nlp_processor", "report_generator", "conversation_manager"],
            custom_settings={
                "max_conversation_history": 50,
                "default_response_timeout": 30,
                "enable_proactive_suggestions": True,
                "confidence_threshold": 0.7,
                "max_multi_agent_coordination": 5
            }
        )
        
        super().__init__(config)
        
        # Core components
        self.nlp_processor: Optional[NaturalLanguageProcessor] = None
        self.report_generator: Optional[ReportGenerator] = None
        self.conversation_manager: Optional[ConversationManager] = None
        self.multi_agent_orchestrator: Optional[MultiAgentOrchestrator] = None
        self.tool_kit: Optional[WhispererToolKit] = None
        
        # Performance tracking
        self.query_stats = {
            "total_queries": 0,
            "successful_responses": 0,
            "reports_generated": 0,
            "avg_response_time": 0.0,
            "avg_confidence_score": 0.0
        }
        
        # Conversation state
        self.active_conversations: Dict[str, ConversationContext] = {}
        
    async def _initialize_agent(self) -> None:
        """Initialize Agent Whisperer components and dependencies."""
        
        self.logger.info("Initializing Agent Whisperer components...")
        
        # Initialize NLP processor
        self.nlp_processor = NaturalLanguageProcessor(
            confidence_threshold=self.config.custom_settings.get("confidence_threshold", 0.7)
        )
        await self.nlp_processor.initialize()
        
        # Initialize report generator
        self.report_generator = ReportGenerator(
            cache_manager=self.cache_manager,
            logger=self.logger
        )
        await self.report_generator.initialize()
        
        # Initialize conversation manager
        self.conversation_manager = ConversationManager(
            max_history=self.config.custom_settings.get("max_conversation_history", 50),
            cache_manager=self.cache_manager
        )
        await self.conversation_manager.initialize()
        
        # Initialize multi-agent orchestrator
        self.multi_agent_orchestrator = MultiAgentOrchestrator(
            max_concurrent_agents=self.config.custom_settings.get("max_multi_agent_coordination", 5),
            logger=self.logger
        )
        await self.multi_agent_orchestrator.initialize()
        
        # Initialize tool kit
        self.tool_kit = WhispererToolKit(
            nlp_processor=self.nlp_processor,
            report_generator=self.report_generator,
            orchestrator=self.multi_agent_orchestrator
        )
        
        self.logger.info("Agent Whisperer initialization completed successfully")
    
    async def _cleanup_agent(self) -> None:
        """Cleanup Agent Whisperer resources."""
        
        # Save any active conversation contexts
        if self.active_conversations:
            await self._save_conversation_contexts()
        
        # Cleanup components
        if self.multi_agent_orchestrator:
            await self.multi_agent_orchestrator.shutdown()
        
        if self.conversation_manager:
            await self.conversation_manager.cleanup()
            
        if self.nlp_processor:
            await self.nlp_processor.cleanup()
            
        if self.report_generator:
            await self.report_generator.cleanup()
    
    async def _execute_agent_logic(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution logic for processing natural language queries and generating responses.
        """
        
        start_time = datetime.utcnow()
        
        # Extract query and user context
        user_query = input_data.get("query", "")
        user_id = input_data.get("user_id", "anonymous")
        conversation_id = input_data.get("conversation_id")
        query_context = input_data.get("context", {})
        
        if not user_query.strip():
            return {
                "success": False,
                "error": "No query provided",
                "response": WhispererResponse(
                    response_type=ResponseType.ERROR,
                    content="Please provide a query to process.",
                    confidence_score=0.0
                ).to_dict()
            }
        
        try:
            # Update statistics
            self.query_stats["total_queries"] += 1
            
            # Get or create conversation context
            if conversation_id:
                conversation_context = await self.conversation_manager.get_conversation(
                    conversation_id, user_id
                )
            else:
                conversation_context = await self.conversation_manager.start_conversation(user_id)
                conversation_id = conversation_context.conversation_id
            
            # Process natural language query
            self.logger.info(f"Processing query from user {user_id}: {user_query[:100]}...")
            
            query_intent = await self.nlp_processor.parse_user_query(
                query=user_query,
                context=conversation_context.get_context_dict(),
                user_context=query_context
            )
            
            # Log the parsed intent for debugging
            self.logger.debug(f"Parsed query intent: {query_intent}")
            
            # Determine query complexity and routing
            complexity = self._assess_query_complexity(query_intent)
            
            # Generate response based on complexity and intent
            if complexity == QueryComplexity.SIMPLE:
                response = await self._handle_simple_query(query_intent, conversation_context)
            elif complexity == QueryComplexity.MODERATE:
                response = await self._handle_moderate_query(query_intent, conversation_context)
            elif complexity == QueryComplexity.COMPLEX:
                response = await self._handle_complex_query(query_intent, conversation_context)
            else:  # ADVANCED
                response = await self._handle_advanced_query(query_intent, conversation_context)
            
            # Update conversation context
            await self.conversation_manager.add_interaction(
                conversation_id=conversation_id,
                user_message=user_query,
                agent_response=response.content,
                intent=query_intent,
                metadata={
                    "complexity": complexity.value,
                    "confidence": response.confidence_score,
                    "execution_time": response.execution_time
                }
            )
            
            # Update performance metrics
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            response.execution_time = execution_time
            
            self._update_query_stats(response, execution_time)
            
            # Log successful completion
            self.logger.info(
                f"Query processed successfully - Intent: {query_intent.intent_type}, "
                f"Confidence: {response.confidence_score:.2f}, Time: {execution_time:.2f}s"
            )
            
            return {
                "success": True,
                "conversation_id": conversation_id,
                "response": response.to_dict(),
                "query_metadata": {
                    "intent": query_intent.to_dict() if hasattr(query_intent, 'to_dict') else str(query_intent),
                    "complexity": complexity.value,
                    "processing_time": execution_time
                }
            }
            
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_message = f"Failed to process query: {str(e)}"
            
            self.logger.error(error_message, exc_info=True)
            
            # Create error response  
            error_response = WhispererResponse(
                response_type=ResponseType.ERROR,
                content=self._generate_friendly_error_message(str(e)),
                confidence_score=0.0,
                execution_time=execution_time,
                follow_up_suggestions=[
                    "Try rephrasing your question",
                    "Ask about a specific suburb or property type",
                    "Request market analysis for a particular area"
                ]
            )
            
            return {
                "success": False,
                "error": str(e),
                "conversation_id": conversation_id if 'conversation_id' in locals() else None,
                "response": error_response.to_dict()
            }
    
    async def _initialize_tools(self) -> List[Tool]:
        """Initialize specialized tools for the Agent Whisperer."""
        
        # Tools will be created after components are initialized
        # This is called before _initialize_agent, so we return empty list here
        return []
    
    def _get_agent_goal(self) -> str:
        """Get agent goal for CrewAI configuration."""
        return (
            "Serve as the intelligent, friendly interface between real estate professionals "
            "and the ReAgent Sydney multi-agent system. Process natural language queries, "
            "coordinate with specialist agents, and generate comprehensive, actionable reports "
            "that help agents make better decisions and serve their clients more effectively."
        )
    
    def _get_agent_backstory(self) -> str:
        """Get agent backstory for CrewAI configuration."""
        return (
            "You are the Agent Whisperer, the conversational heart of ReAgent Sydney. "
            "With deep knowledge of the Australian real estate market and access to "
            "a team of specialist agents, you translate complex market intelligence "
            "into clear, actionable insights. You understand that real estate agents "
            "are busy professionals who need quick, accurate information to serve "
            "their clients effectively. Your responses are always professional, "
            "clear, and focused on helping agents succeed in their business."
        )
    
    def _assess_query_complexity(self, query_intent: QueryIntent) -> QueryComplexity:
        """Assess the complexity of a query to determine processing approach."""
        
        # Simple queries - single data point, direct lookup
        if query_intent.intent_type in ["price_lookup", "basic_property_info", "greeting", "help"]:
            return QueryComplexity.SIMPLE
        
        # Moderate queries - multiple data points, basic analysis
        elif query_intent.intent_type in [
            "suburb_analysis", "recent_sales", "listing_search", "market_update"
        ]:
            return QueryComplexity.MODERATE
        
        # Complex queries - multi-agent coordination required
        elif query_intent.intent_type in [
            "buyer_matching", "seller_strategy", "comparative_analysis", "investment_analysis"
        ]:
            return QueryComplexity.COMPLEX
        
        # Advanced queries - custom reporting and deep analysis
        else:
            return QueryComplexity.ADVANCED
    
    async def _handle_simple_query(
        self, 
        query_intent: QueryIntent, 
        conversation_context: ConversationContext
    ) -> WhispererResponse:
        """Handle simple queries that require minimal processing."""
        
        self.logger.debug(f"Handling simple query: {query_intent.intent_type}")
        
        # Handle different types of simple queries
        if query_intent.intent_type == "greeting":
            return WhispererResponse(
                response_type=ResponseType.DIRECT_ANSWER,
                content=self._generate_greeting_response(conversation_context),
                confidence_score=1.0,
                follow_up_suggestions=[
                    "Ask about market conditions in a specific suburb",
                    "Search for properties matching specific criteria", 
                    "Get pricing analysis for a property"
                ]
            )
        
        elif query_intent.intent_type == "help":
            return WhispererResponse(
                response_type=ResponseType.GUIDANCE,
                content=self._generate_help_response(),
                confidence_score=1.0,
                follow_up_suggestions=[
                    "Try: 'What's happening in the Bondi market?'",
                    "Try: 'Find 3BR homes under $2M in the Inner West'",
                    "Try: 'Generate a seller strategy report for 123 Main St'"
                ]
            )
        
        elif query_intent.intent_type == "price_lookup":
            # This would typically involve a quick database lookup
            suburb = query_intent.entities.get("suburb")
            property_type = query_intent.entities.get("property_type", "house")
            
            # Simulate quick price lookup (in real implementation, this would hit the database)
            return WhispererResponse(
                response_type=ResponseType.DIRECT_ANSWER,
                content=f"Median {property_type} price in {suburb}: $1,250,000 (last 3 months). "
                        f"This represents a 3.2% increase from the previous quarter.",
                confidence_score=0.9,
                data_sources=["Recent sales data", "Domain API"],
                follow_up_suggestions=[
                    f"Get detailed market analysis for {suburb}",
                    f"Compare {suburb} with nearby suburbs",
                    f"Find {property_type} listings in {suburb}"
                ]
            )
        
        else:
            # Default simple response
            return WhispererResponse(
                response_type=ResponseType.DIRECT_ANSWER,
                content="I understand your query, but I need a bit more information to provide the best answer. Could you be more specific?",
                confidence_score=0.5,
                requires_follow_up=True,
                follow_up_suggestions=[
                    "Specify a suburb or area of interest",
                    "Mention the type of property you're interested in",
                    "Let me know if you're buying, selling, or investing"
                ]
            )
    
    async def _handle_moderate_query(
        self, 
        query_intent: QueryIntent, 
        conversation_context: ConversationContext
    ) -> WhispererResponse:
        """Handle moderate complexity queries requiring some data aggregation."""
        
        self.logger.debug(f"Handling moderate query: {query_intent.intent_type}")
        
        # This would involve coordinating with 1-2 other agents
        coordination_request = AgentCoordinationRequest(
            primary_intent=query_intent,
            required_agents=self._determine_required_agents(query_intent),
            timeout_seconds=30,
            priority="medium"
        )
        
        # Execute coordination
        coordination_result = await self.multi_agent_orchestrator.coordinate_agents(
            coordination_request
        )
        
        # Process results into user-friendly response
        content = self._synthesize_moderate_response(coordination_result, query_intent)
        
        return WhispererResponse(
            response_type=ResponseType.DIRECT_ANSWER,
            content=content,
            confidence_score=coordination_result.get("confidence", 0.8),
            data_sources=coordination_result.get("data_sources", []),
            follow_up_suggestions=self._generate_follow_up_suggestions(query_intent)
        )
    
    async def _handle_complex_query(
        self, 
        query_intent: QueryIntent, 
        conversation_context: ConversationContext
    ) -> WhispererResponse:
        """Handle complex queries requiring multi-agent coordination."""
        
        self.logger.debug(f"Handling complex query: {query_intent.intent_type}")
        
        # Complex queries often result in reports
        if query_intent.intent_type in ["buyer_matching", "seller_strategy", "investment_analysis"]:
            
            # Generate comprehensive report
            report_type = self._map_intent_to_report_type(query_intent.intent_type)
            
            report = await self.report_generator.generate_report(
                report_type=report_type,
                parameters=query_intent.entities,
                context=conversation_context.get_context_dict()
            )
            
            self.query_stats["reports_generated"] += 1
            
            return WhispererResponse(
                response_type=ResponseType.REPORT,
                content=f"I've generated a comprehensive {report_type.value} report for you.",
                report_data=report,
                confidence_score=0.9,
                data_sources=report.get("data_sources", []),
                follow_up_suggestions=[
                    "Export this report to PDF",
                    "Get more details about specific recommendations",
                    "Schedule follow-up analysis"
                ]
            )
        
        else:
            # Multi-agent coordination for complex analysis
            coordination_request = AgentCoordinationRequest(
                primary_intent=query_intent,
                required_agents=self._determine_required_agents(query_intent),
                timeout_seconds=60,
                priority="high"
            )
            
            coordination_result = await self.multi_agent_orchestrator.coordinate_agents(
                coordination_request
            )
            
            content = self._synthesize_complex_response(coordination_result, query_intent)
            
            return WhispererResponse(
                response_type=ResponseType.DIRECT_ANSWER,
                content=content,
                confidence_score=coordination_result.get("confidence", 0.8),
                data_sources=coordination_result.get("data_sources", []),
                follow_up_suggestions=self._generate_follow_up_suggestions(query_intent)
            )
    
    async def _handle_advanced_query(
        self, 
        query_intent: QueryIntent, 
        conversation_context: ConversationContext
    ) -> WhispererResponse:
        """Handle advanced queries requiring custom analysis and reporting."""
        
        self.logger.debug(f"Handling advanced query: {query_intent.intent_type}")
        
        # Advanced queries always involve custom reports and full system coordination
        coordination_request = AgentCoordinationRequest(
            primary_intent=query_intent,
            required_agents=["listing_watcher", "suburb_signal", "buyer_matchmaker", "seller_strategy", "off_market_radar"],
            timeout_seconds=120,
            priority="high",
            custom_analysis=True
        )
        
        # Execute full system coordination
        coordination_result = await self.multi_agent_orchestrator.coordinate_agents(
            coordination_request
        )
        
        # Generate custom report based on results
        custom_report = await self.report_generator.generate_custom_report(
            title=f"Advanced Analysis: {query_intent.intent_type.replace('_', ' ').title()}",
            data=coordination_result,
            parameters=query_intent.entities,
            context=conversation_context.get_context_dict()
        )
        
        self.query_stats["reports_generated"] += 1
        
        return WhispererResponse(
            response_type=ResponseType.REPORT,
            content=f"I've completed your advanced analysis and generated a comprehensive custom report.",
            report_data=custom_report,
            confidence_score=coordination_result.get("confidence", 0.85),
            data_sources=coordination_result.get("data_sources", []),
            follow_up_suggestions=[
                "Dive deeper into specific findings",
                "Get updated analysis with latest data",
                "Export detailed report with visualizations"
            ]
        )
    
    def _determine_required_agents(self, query_intent: QueryIntent) -> List[str]:
        """Determine which agents are needed for a query."""
        
        agent_mapping = {
            "listing_search": ["listing_watcher"],
            "recent_sales": ["listing_watcher", "suburb_signal"],
            "suburb_analysis": ["suburb_signal", "listing_watcher"],
            "market_update": ["suburb_signal", "listing_watcher"],
            "buyer_matching": ["buyer_matchmaker", "listing_watcher"],
            "seller_strategy": ["seller_strategy", "suburb_signal"],
            "investment_analysis": ["suburb_signal", "seller_strategy", "off_market_radar"],
            "off_market_opportunities": ["off_market_radar", "listing_watcher"],
            "comparative_analysis": ["suburb_signal", "listing_watcher", "seller_strategy"]
        }
        
        return agent_mapping.get(query_intent.intent_type, ["listing_watcher"])
    
    def _map_intent_to_report_type(self, intent_type: str) -> ReportType:
        """Map query intent to report type."""
        
        mapping = {
            "buyer_matching": ReportType.BUYER_MATCHING,
            "seller_strategy": ReportType.SELLER_STRATEGY,
            "suburb_analysis": ReportType.MARKET_ANALYSIS,
            "investment_analysis": ReportType.INVESTMENT_ANALYSIS,
            "off_market_opportunities": ReportType.OFF_MARKET_SUMMARY
        }
        
        return mapping.get(intent_type, ReportType.MARKET_ANALYSIS)
    
    def _synthesize_moderate_response(
        self, 
        coordination_result: Dict[str, Any], 
        query_intent: QueryIntent
    ) -> str:
        """Synthesize a user-friendly response from coordination results."""
        
        # This would be more sophisticated in practice, potentially using
        # the NLP processor to generate natural language from structured data
        
        if coordination_result.get("success"):
            data = coordination_result.get("data", {})
            
            # Create a natural language summary
            summary_parts = []
            
            if "price_trends" in data:
                trends = data["price_trends"]
                summary_parts.append(f"Current market trends show {trends.get('direction', 'stable')} pricing")
            
            if "listing_count" in data:
                count = data["listing_count"]
                summary_parts.append(f"with {count} active listings in the area")
            
            if "recent_sales" in data:
                sales = data["recent_sales"]
                summary_parts.append(f"and {len(sales)} recent sales for comparison")
            
            return ". ".join(summary_parts) + "."
        
        else:
            return "I was able to gather some information, but encountered issues accessing all requested data. Please try your query again or be more specific."
    
    def _synthesize_complex_response(
        self, 
        coordination_result: Dict[str, Any], 
        query_intent: QueryIntent
    ) -> str:
        """Synthesize a comprehensive response from complex coordination results."""
        
        if coordination_result.get("success"):
            # Build a detailed narrative response
            return (
                f"Based on comprehensive analysis from multiple data sources, "
                f"I've gathered detailed insights about your {query_intent.intent_type.replace('_', ' ')} query. "
                f"The analysis includes current market conditions, recent transaction data, "
                f"and strategic recommendations tailored to your specific needs."
            )
        else:
            return (
                f"I encountered some challenges while conducting the comprehensive analysis. "
                f"However, I was able to gather partial information that may still be helpful. "
                f"Would you like me to try a different approach or focus on a specific aspect?"
            )
    
    def _generate_greeting_response(self, conversation_context: ConversationContext) -> str:
        """Generate a personalized greeting response."""
        
        if conversation_context.interaction_count == 0:
            return (
                "Hello! I'm your Agent Whisperer, here to help you navigate the Sydney real estate market. "
                "I can provide market analysis, find properties, generate reports, and coordinate with "
                "our specialist agents to give you comprehensive insights. What would you like to know?"
            )
        else:
            return (
                "Welcome back! I remember our previous conversations. "
                "How can I help you with your real estate intelligence needs today?"
            )
    
    def _generate_help_response(self) -> str:
        """Generate a helpful guidance response."""
        
        return (
            "I'm here to help you with comprehensive real estate intelligence for Sydney. Here's what I can do:\n\n"
            "📊 **Market Analysis**: Get detailed suburb reports, price trends, and market conditions\n"
            "🏠 **Property Search**: Find listings that match specific criteria\n"
            "💰 **Pricing Intelligence**: Get valuation insights and pricing strategies\n"
            "🎯 **Buyer Matching**: Connect properties with suitable buyers\n"
            "📈 **Investment Analysis**: Evaluate investment opportunities and risks\n"
            "🔍 **Off-Market Opportunities**: Discover hidden opportunities and upcoming listings\n"
            "📋 **Custom Reports**: Generate professional reports for your clients\n\n"
            "Just ask me naturally - for example: 'What's the market like in Bondi?' or "
            "'Find 3-bedroom houses under $2M in the Inner West'"
        )
    
    def _generate_follow_up_suggestions(self, query_intent: QueryIntent) -> List[str]:
        """Generate contextual follow-up suggestions."""
        
        suggestions_map = {
            "suburb_analysis": [
                "Compare this suburb with nearby areas",
                "Get investment potential analysis",
                "Find similar suburbs with better value"
            ],
            "listing_search": [
                "Set up alerts for new matching listings",
                "Get market analysis for this property type",
                "Find similar properties in nearby suburbs"
            ],
            "buyer_matching": [
                "Schedule property inspections",
                "Get detailed property reports",
                "Set up ongoing buyer alerts"
            ],
            "seller_strategy": [
                "Get auction timing recommendations",
                "Create property marketing plan",
                "Analyze competitor listings"
            ]
        }
        
        return suggestions_map.get(
            query_intent.intent_type, 
            [
                "Ask for more specific information",
                "Request a detailed report",
                "Get comparative analysis"
            ]
        )
    
    def _generate_friendly_error_message(self, error: str) -> str:
        """Generate a user-friendly error message."""
        
        error_lower = error.lower()
        
        if "timeout" in error_lower:
            return (
                "I'm taking a bit longer than usual to process your request. "
                "This might be due to high system load or complex data analysis. "
                "Please try again in a moment, or try a more specific query."
            )
        
        elif "not found" in error_lower or "no data" in error_lower:
            return (
                "I couldn't find specific data for your query. This might be because "
                "the area or criteria you mentioned isn't in our current dataset. "
                "Try a nearby suburb or broader search criteria."
            )
        
        elif "rate limit" in error_lower:
            return (
                "I'm currently experiencing high demand and need to slow down a bit. "
                "Please wait a moment before making another request."
            )
        
        else:
            return (
                "I encountered an unexpected issue while processing your request. "
                "This has been logged for our technical team. Please try rephrasing "
                "your question or contact support if the issue persists."
            )
    
    def _update_query_stats(self, response: WhispererResponse, execution_time: float) -> None:
        """Update internal query statistics."""
        
        if response.response_type != ResponseType.ERROR:
            self.query_stats["successful_responses"] += 1
        
        # Update average response time
        total_queries = self.query_stats["total_queries"]
        current_avg = self.query_stats["avg_response_time"]
        self.query_stats["avg_response_time"] = (
            (current_avg * (total_queries - 1) + execution_time) / total_queries
        )
        
        # Update average confidence score
        if response.confidence_score > 0:
            current_avg_confidence = self.query_stats["avg_confidence_score"]
            self.query_stats["avg_confidence_score"] = (
                (current_avg_confidence * (total_queries - 1) + response.confidence_score) / total_queries
            )
    
    async def _save_conversation_contexts(self) -> None:
        """Save active conversation contexts before shutdown."""
        
        for conversation_id, context in self.active_conversations.items():
            try:
                await self.conversation_manager.save_conversation(conversation_id, context)
            except Exception as e:
                self.logger.error(f"Failed to save conversation {conversation_id}: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics for the Agent Whisperer."""
        
        success_rate = 0.0
        if self.query_stats["total_queries"] > 0:
            success_rate = (
                self.query_stats["successful_responses"] / self.query_stats["total_queries"]
            ) * 100
        
        return {
            "query_stats": self.query_stats.copy(),
            "success_rate": success_rate,
            "active_conversations": len(self.active_conversations),
            "component_status": {
                "nlp_processor": self.nlp_processor is not None,
                "report_generator": self.report_generator is not None,
                "conversation_manager": self.conversation_manager is not None,
                "multi_agent_orchestrator": self.multi_agent_orchestrator is not None
            }
        }
    
    def __repr__(self) -> str:
        return f"<AgentWhispererAgent(queries={self.query_stats['total_queries']}, success_rate={self.query_stats['successful_responses']}/{self.query_stats['total_queries']})>"