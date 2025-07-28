"""
ReAgent Sydney - Core Package

Main package for the ReAgent Sydney multi-agent real estate intelligence system.
Provides core functionality, agents, APIs, and data models for real estate analysis.
"""

from .config.settings import settings, get_settings

__version__ = "0.1.0"
__all__ = ["settings", "get_settings"]