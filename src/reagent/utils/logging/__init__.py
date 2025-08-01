"""
Logging utilities

Comprehensive structured logging system for ReAgent Sydney including:
- JSON structured logging with correlation IDs
- Property and buyer context tracking
- Agent execution logging
- Performance metrics integration
- Error categorization and enrichment
"""

import logging
import structlog

from .structured_logger import (
    # Main logger class
    ReAgentLogger,
    get_logger as get_reagent_logger,
    
    # Configuration functions
    configure_structured_logging,
    setup_logging_for_production,
    setup_logging_for_development,
    
    # Context managers
    correlation_context,
    request_context,
    agent_execution_context,
    
    # Pre-configured loggers
    api_logger,
    agent_logger,
    database_logger,
    cache_logger,
    external_api_logger,
    monitoring_logger,
)

def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Get a structlog logger instance (backward compatibility).
    
    Args:
        name: Logger name (defaults to calling module)
        
    Returns:
        structlog.BoundLogger: Logger instance
    """
    return structlog.get_logger(name)

__all__ = [
    # Backward compatibility
    "get_logger",
    
    # Enhanced logger class
    "ReAgentLogger",
    "get_reagent_logger",
    
    # Configuration
    "configure_structured_logging",
    "setup_logging_for_production", 
    "setup_logging_for_development",
    
    # Context managers
    "correlation_context",
    "request_context",
    "agent_execution_context",
    
    # Pre-configured loggers
    "api_logger",
    "agent_logger", 
    "database_logger",
    "cache_logger",
    "external_api_logger",
    "monitoring_logger",
]