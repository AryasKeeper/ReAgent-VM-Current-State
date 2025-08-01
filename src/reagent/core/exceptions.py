"""
ReAgent Sydney - Custom Exception Classes
Comprehensive exception hierarchy for production-ready error handling.
"""

from typing import Optional, Dict, Any


class ReAgentException(Exception):
    """Base exception class for all ReAgent errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.error_code = error_code
        
    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class DatabaseConnectionError(ReAgentException):
    """Raised when database connection fails."""
    
    def __init__(self, message: str = "Database connection failed", **kwargs):
        super().__init__(message, **kwargs)


class DatabaseQueryError(ReAgentException):
    """Raised when database query execution fails."""
    
    def __init__(self, message: str = "Database query failed", **kwargs):
        super().__init__(message, **kwargs)


class ExternalAPIError(ReAgentException):
    """Raised when external API calls fail."""
    
    def __init__(self, api_name: str, message: str = "External API call failed", status_code: Optional[int] = None, **kwargs):
        self.api_name = api_name
        self.status_code = status_code
        full_message = f"{api_name} API: {message}"
        if status_code:
            full_message += f" (HTTP {status_code})"
        super().__init__(full_message, **kwargs)


class APIRateLimitError(ExternalAPIError):
    """Raised when API rate limits are exceeded."""
    
    def __init__(self, api_name: str, retry_after: Optional[int] = None, **kwargs):
        message = f"Rate limit exceeded for {api_name}"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(api_name, message, status_code=429, **kwargs)
        self.retry_after = retry_after


class ValidationError(ReAgentException):
    """Raised when data validation fails."""
    
    def __init__(self, field: str, value: Any, message: str = "Validation failed", **kwargs):
        self.field = field
        self.value = value
        full_message = f"Validation failed for field '{field}': {message}"
        super().__init__(full_message, **kwargs)


class ConfigurationError(ReAgentException):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, config_key: str, message: str = "Configuration error", **kwargs):
        self.config_key = config_key
        full_message = f"Configuration error for '{config_key}': {message}"
        super().__init__(full_message, **kwargs)


class AgentExecutionError(ReAgentException):
    """Raised when agent execution fails."""
    
    def __init__(self, agent_name: str, message: str = "Agent execution failed", **kwargs):
        self.agent_name = agent_name
        full_message = f"Agent '{agent_name}': {message}"
        super().__init__(full_message, **kwargs)


class VectorSearchError(ReAgentException):
    """Raised when vector database operations fail."""
    
    def __init__(self, operation: str, message: str = "Vector search operation failed", **kwargs):
        self.operation = operation
        full_message = f"Vector {operation} operation: {message}"
        super().__init__(full_message, **kwargs)


class CacheError(ReAgentException):
    """Raised when cache operations fail."""
    
    def __init__(self, operation: str, key: Optional[str] = None, message: str = "Cache operation failed", **kwargs):
        self.operation = operation
        self.cache_key = key
        full_message = f"Cache {operation} operation"
        if key:
            full_message += f" for key '{key}'"
        full_message += f": {message}"
        super().__init__(full_message, **kwargs)


class AuthenticationError(ReAgentException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, **kwargs)


class AuthorizationError(ReAgentException):
    """Raised when authorization fails."""
    
    def __init__(self, resource: str, action: str, message: str = "Access denied", **kwargs):
        self.resource = resource
        self.action = action
        full_message = f"Access denied: Cannot {action} {resource}. {message}"
        super().__init__(full_message, **kwargs)


class DataIntegrityError(ReAgentException):
    """Raised when data integrity violations occur."""
    
    def __init__(self, constraint: str, message: str = "Data integrity violation", **kwargs):
        self.constraint = constraint
        full_message = f"Data integrity violation ({constraint}): {message}"
        super().__init__(full_message, **kwargs)


class PropertyDataError(ReAgentException):
    """Raised when property data processing fails."""
    
    def __init__(self, property_id: Optional[str] = None, message: str = "Property data error", **kwargs):
        self.property_id = property_id
        full_message = message
        if property_id:
            full_message = f"Property {property_id}: {message}"
        super().__init__(full_message, **kwargs)


class MarketDataError(ReAgentException):
    """Raised when market data processing fails."""
    
    def __init__(self, suburb: Optional[str] = None, message: str = "Market data error", **kwargs):
        self.suburb = suburb
        full_message = message
        if suburb:
            full_message = f"Market data for {suburb}: {message}"
        super().__init__(full_message, **kwargs)


class ComplianceError(ReAgentException):
    """Raised when compliance violations are detected."""
    
    def __init__(self, regulation: str, message: str = "Compliance violation", **kwargs):
        self.regulation = regulation
        full_message = f"Compliance violation ({regulation}): {message}"
        super().__init__(full_message, **kwargs)


class SecurityError(ReAgentException):
    """Raised when security violations are detected."""
    
    def __init__(self, threat_type: str, message: str = "Security violation", **kwargs):
        self.threat_type = threat_type
        full_message = f"Security violation ({threat_type}): {message}"
        super().__init__(full_message, **kwargs)


class ResourceNotFoundError(ReAgentException):
    """Raised when requested resources are not found."""
    
    def __init__(self, resource_type: str, identifier: str, **kwargs):
        self.resource_type = resource_type
        self.identifier = identifier
        message = f"{resource_type} not found: {identifier}"
        super().__init__(message, **kwargs)


class ConcurrencyError(ReAgentException):
    """Raised when concurrency issues occur."""
    
    def __init__(self, resource: str, message: str = "Concurrency conflict", **kwargs):
        self.resource = resource
        full_message = f"Concurrency error for {resource}: {message}"
        super().__init__(full_message, **kwargs)


class SystemUnavailableError(ReAgentException):
    """Raised when system components are unavailable."""
    
    def __init__(self, component: str, message: str = "System component unavailable", **kwargs):
        self.component = component
        full_message = f"System unavailable - {component}: {message}"
        super().__init__(full_message, **kwargs)


# Exception mapping for common error patterns
EXCEPTION_MAPPING = {
    'database': DatabaseConnectionError,
    'query': DatabaseQueryError,
    'api': ExternalAPIError,
    'validation': ValidationError,
    'config': ConfigurationError,
    'agent': AgentExecutionError,
    'vector': VectorSearchError,
    'cache': CacheError,
    'auth': AuthenticationError,
    'authz': AuthorizationError,
    'integrity': DataIntegrityError,
    'property': PropertyDataError,
    'market': MarketDataError,
    'compliance': ComplianceError,
    'security': SecurityError,
    'not_found': ResourceNotFoundError,
    'concurrency': ConcurrencyError,
    'unavailable': SystemUnavailableError,
}


def get_exception_for_context(context: str, **kwargs) -> ReAgentException:
    """Get appropriate exception class for given context."""
    exception_class = EXCEPTION_MAPPING.get(context, ReAgentException)
    return exception_class(**kwargs)
