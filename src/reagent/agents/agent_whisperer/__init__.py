"""
ReAgent Sydney - Agent Whisperer Module

The Agent Whisperer serves as the natural language interface and report generation
system for the ReAgent Sydney multi-agent real estate intelligence platform.

This module provides:
- Natural language query processing and understanding
- Multi-agent coordination for comprehensive market intelligence
- Professional report generation for various real estate scenarios
- Context-aware conversation management
- User preference learning and adaptation

Main Components:
- AgentWhispererAgent: Core agent class with CrewAI integration
- NaturalLanguageProcessor: Advanced NLP for query understanding
- ReportGenerator: Professional report creation system
- ConversationManager: Multi-turn conversation context management
- MultiAgentOrchestrator: Sophisticated agent coordination system
- WhispererToolKit: Specialized tools for system interaction
"""

from .agent import AgentWhispererAgent, WhispererResponse, ResponseType, QueryComplexity
from .nlp_processor import (
    NaturalLanguageProcessor, 
    QueryIntent, 
    IntentClassification,
    IntentType,
    EntityType,
    ExtractedEntity
)
from .report_generator import (
    ReportGenerator,
    GeneratedReport,
    ReportTemplate,
    ReportType,
    ReportFormat,
    ReportSection
)
from .conversation_manager import (
    ConversationManager,
    ConversationContext,
    ConversationInteraction,
    UserPreferences,
    TopicContext,
    ConversationState,
    InteractionType
)
from .multi_agent_orchestrator import (
    MultiAgentOrchestrator,
    AgentCoordinationRequest,
    CoordinationResult,
    AgentTask,
    CoordinationStrategy,
    ExecutionStatus
)
from .tools import WhispererToolKit

__all__ = [
    # Core agent
    "AgentWhispererAgent",
    "WhispererResponse", 
    "ResponseType",
    "QueryComplexity",
    
    # Natural language processing
    "NaturalLanguageProcessor",
    "QueryIntent",
    "IntentClassification", 
    "IntentType",
    "EntityType",
    "ExtractedEntity",
    
    # Report generation
    "ReportGenerator",
    "GeneratedReport",
    "ReportTemplate",
    "ReportType", 
    "ReportFormat",
    "ReportSection",
    
    # Conversation management
    "ConversationManager",
    "ConversationContext",
    "ConversationInteraction",
    "UserPreferences",
    "TopicContext",
    "ConversationState",
    "InteractionType",
    
    # Multi-agent orchestration
    "MultiAgentOrchestrator",
    "AgentCoordinationRequest",
    "CoordinationResult",
    "AgentTask",
    "CoordinationStrategy",
    "ExecutionStatus",
    
    # Tools
    "WhispererToolKit"
]

# Version information
__version__ = "1.0.0"
__author__ = "ReAgent Sydney Development Team"
__description__ = "Natural Language Interface and Report Generation System for ReAgent Sydney"