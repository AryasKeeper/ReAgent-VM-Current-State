"""
External API Integration Services

Client implementations for Domain.com.au, RealEstate.com.au, CoreLogic,
and other external real estate data providers.
"""

from .domain_client import DomainAPIClient
from .realestate_client import RealEstateAPIClient

__all__ = [
    "DomainAPIClient",
    "RealEstateAPIClient"
]