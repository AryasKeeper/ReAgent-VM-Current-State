"""
ReAgent Sydney - Structured Logging

Comprehensive structured logging with JSON formatting, correlation IDs,
and integration with monitoring and alerting systems.
"""

import logging
import json
import uuid
import time
import traceback
from typing import Dict, Any, Optional
from contextlib import contextmanager
from contextvars import ContextVar
import structlog
from prometheus_client import Counter, Histogram

# Prometheus metrics for logging
log_messages_total = Counter(
    'log_messages_total',
    'Total log messages by level',
    ['level', 'service', 'agent']
)

log_processing_duration_seconds = Histogram(
    'log_processing_duration_seconds',
    'Time spent processing log messages',
    ['level', 'service']
)

# Context variables for correlation tracking
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
agent_context_var: ContextVar[Optional[str]] = ContextVar('agent_context', default=None)

class ReAgentLogProcessor:
    """Custom processor for ReAgent-specific log enrichment."""
    
    def __call__(self, logger, method_name, event_dict):
        # Add correlation ID
        correlation_id = correlation_id_var.get()
        if correlation_id:
            event_dict['correlation_id'] = correlation_id
            
        # Add request ID
        request_id = request_id_var.get()
        if request_id:
            event_dict['request_id'] = request_id
            
        # Add agent context
        agent_context = agent_context_var.get()
        if agent_context:
            event_dict['agent'] = agent_context
            
        # Add ReAgent-specific fields
        event_dict['service'] = 'reagent-sydney'
        event_dict['environment'] = 'production'
        event_dict['version'] = '1.0.0'
        
        # Record metrics
        level = event_dict.get('level', 'info')
        service = event_dict.get('service', 'unknown')
        agent = event_dict.get('agent', 'system')
        
        log_messages_total.labels(
            level=level,
            service=service,
            agent=agent
        ).inc()
        
        return event_dict

class PropertyContextProcessor:
    """Processor for property-related log context."""
    
    def __call__(self, logger, method_name, event_dict):
        # Extract property context if available
        if 'property_id' in event_dict:
            event_dict['context_type'] = 'property'
            
        if 'suburb' in event_dict:
            event_dict['location'] = event_dict['suburb']
            
        if 'buyer_id' in event_dict:
            event_dict['context_type'] = 'buyer'
            
        return event_dict

class PerformanceLogProcessor:
    """Processor for performance and timing information."""
    
    def __call__(self, logger, method_name, event_dict):
        # Add execution timing if available
        if 'duration' in event_dict:
            event_dict['performance'] = {
                'duration_ms': event_dict['duration'] * 1000,
                'duration_seconds': event_dict['duration']
            }
            
        # Add memory usage if available
        if 'memory_usage' in event_dict:
            event_dict['performance'] = event_dict.get('performance', {})
            event_dict['performance']['memory_mb'] = event_dict['memory_usage'] / 1024 / 1024
            
        return event_dict

class ErrorEnrichmentProcessor:
    """Processor for error context enrichment."""
    
    def __call__(self, logger, method_name, event_dict):
        # Enrich error logs with additional context
        if event_dict.get('level') in ['ERROR', 'error', 'CRITICAL', 'critical']:
            event_dict['error_context'] = True
            
            # Add stack trace if exception info is available
            if 'exc_info' in event_dict and event_dict['exc_info']:
                event_dict['stack_trace'] = traceback.format_exc()
                
            # Add error categorization
            error_msg = event_dict.get('event', '').lower()
            if 'timeout' in error_msg or 'connection' in error_msg:
                event_dict['error_category'] = 'network'
            elif 'database' in error_msg or 'sql' in error_msg:
                event_dict['error_category'] = 'database'
            elif 'api' in error_msg or 'rate limit' in error_msg:
                event_dict['error_category'] = 'external_api'
            elif 'agent' in error_msg or 'execution' in error_msg:
                event_dict['error_category'] = 'agent_execution'
            else:
                event_dict['error_category'] = 'application'
                
        return event_dict

def configure_structured_logging(
    level: str = "INFO",
    enable_json: bool = True,
    enable_console: bool = True
) -> structlog.BoundLogger:
    """Configure structured logging for ReAgent Sydney."""
    
    # Configure processors chain
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        ReAgentLogProcessor(),
        PropertyContextProcessor(),
        PerformanceLogProcessor(),
        ErrorEnrichmentProcessor(),
    ]
    
    if enable_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
        
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=None,  # Will use default (stderr)
        level=getattr(logging, level.upper()),
    )
    
    return structlog.get_logger()

class ReAgentLogger:
    """Enhanced logger for ReAgent with business context."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = structlog.get_logger(name)
        
    def with_context(self, **kwargs) -> 'ReAgentLogger':
        """Create a new logger with additional context."""
        new_logger = ReAgentLogger(self.name)
        new_logger.logger = self.logger.bind(**kwargs)
        return new_logger
        
    def with_property_context(self, property_id: str, suburb: str = None, 
                            property_type: str = None) -> 'ReAgentLogger':
        """Add property-specific context."""
        context = {'property_id': property_id}
        if suburb:
            context['suburb'] = suburb
        if property_type:
            context['property_type'] = property_type
        return self.with_context(**context)
        
    def with_buyer_context(self, buyer_id: str, preferences: Dict[str, Any] = None) -> 'ReAgentLogger':
        """Add buyer-specific context."""
        context = {'buyer_id': buyer_id}
        if preferences:
            context['buyer_preferences'] = preferences
        return self.with_context(**context)
        
    def with_agent_context(self, agent_name: str, execution_id: str = None) -> 'ReAgentLogger':
        """Add agent execution context."""
        context = {'agent_name': agent_name}
        if execution_id:
            context['execution_id'] = execution_id
        agent_context_var.set(agent_name)
        return self.with_context(**context)
        
    def with_api_context(self, api_name: str, endpoint: str = None, 
                        request_id: str = None) -> 'ReAgentLogger':
        """Add API call context."""
        context = {'api_name': api_name}
        if endpoint:
            context['api_endpoint'] = endpoint
        if request_id:
            context['api_request_id'] = request_id
        return self.with_context(**context)
        
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.logger.debug(message, **kwargs)
        
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.logger.info(message, **kwargs)
        
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.logger.warning(message, **kwargs)
        
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self.logger.error(message, **kwargs)
        
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        self.logger.critical(message, **kwargs)
        
    def log_property_processed(self, property_id: str, source: str, 
                             processing_time: float, status: str = "success"):
        """Log property processing event."""
        self.with_property_context(property_id).info(
            "Property processed",
            source=source,
            processing_time_ms=processing_time * 1000,
            status=status,
            event_type="property_processed"
        )
        
    def log_buyer_match_created(self, buyer_id: str, property_id: str, 
                              match_score: float, match_quality: str):
        """Log buyer match creation."""
        self.with_buyer_context(buyer_id).with_property_context(property_id).info(
            "Buyer match created",
            match_score=match_score,
            match_quality=match_quality,
            event_type="buyer_match_created"
        )
        
    def log_agent_execution(self, agent_name: str, execution_type: str,
                          duration: float, status: str, error: str = None):
        """Log agent execution event."""
        logger = self.with_agent_context(agent_name, str(uuid.uuid4()))
        
        if status == "success":
            logger.info(
                "Agent execution completed",
                execution_type=execution_type,
                duration_seconds=duration,
                status=status,
                event_type="agent_execution"
            )
        else:
            logger.error(
                "Agent execution failed",
                execution_type=execution_type,
                duration_seconds=duration,
                status=status,
                error=error,
                event_type="agent_execution"
            )
            
    def log_api_call(self, api_name: str, endpoint: str, duration: float,
                    status_code: int, error: str = None):
        """Log external API call."""
        logger = self.with_api_context(api_name, endpoint)
        
        if 200 <= status_code < 300:
            logger.info(
                "API call successful",
                duration_seconds=duration,
                status_code=status_code,
                event_type="api_call"
            )
        else:
            logger.warning(
                "API call failed",
                duration_seconds=duration,
                status_code=status_code,
                error=error,
                event_type="api_call"
            )

# Context managers for correlation tracking
@contextmanager
def correlation_context(correlation_id: str = None):
    """Context manager for correlation ID tracking."""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
        
    token = correlation_id_var.set(correlation_id)
    try:
        yield correlation_id
    finally:
        correlation_id_var.reset(token)

@contextmanager  
def request_context(request_id: str = None):
    """Context manager for request ID tracking."""
    if request_id is None:
        request_id = str(uuid.uuid4())
        
    token = request_id_var.set(request_id)
    try:
        yield request_id
    finally:
        request_id_var.reset(token)

@contextmanager
def agent_execution_context(agent_name: str, execution_id: str = None):
    """Context manager for agent execution tracking."""
    if execution_id is None:
        execution_id = str(uuid.uuid4())
        
    token = agent_context_var.set(f"{agent_name}:{execution_id}")
    try:
        yield execution_id
    finally:
        agent_context_var.reset(token)

# Utility functions
def get_logger(name: str) -> ReAgentLogger:
    """Get a ReAgent logger instance."""
    return ReAgentLogger(name)

def setup_logging_for_production():
    """Set up production logging configuration."""
    configure_structured_logging(
        level="INFO",
        enable_json=True,
        enable_console=False
    )

def setup_logging_for_development():
    """Set up development logging configuration."""
    configure_structured_logging(
        level="DEBUG",
        enable_json=False,
        enable_console=True
    )

# Pre-configured loggers for common components
api_logger = get_logger("reagent.api")
agent_logger = get_logger("reagent.agents")
database_logger = get_logger("reagent.database")
cache_logger = get_logger("reagent.cache")
external_api_logger = get_logger("reagent.external_apis")
monitoring_logger = get_logger("reagent.monitoring")
