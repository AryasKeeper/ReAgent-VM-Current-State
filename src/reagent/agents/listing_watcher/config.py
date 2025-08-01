"""
ReAgent Sydney - Listing Watcher Configuration

Configuration settings specific to the Listing Watcher AU agent.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ScrapingMode(str, Enum):
    """Scraping mode options."""
    HOURLY = "hourly"
    CONTINUOUS = "continuous" 
    ON_DEMAND = "on_demand"
    DAILY = "daily"


class DataSource(str, Enum):
    """Supported data sources."""
    DOMAIN = "domain"
    REALESTATE = "realestate"
    BOTH = "both"


@dataclass
class SydneyPostcodes:
    """Sydney Metro postcode configurations."""
    
    # Core Sydney CBD and Inner suburbs (2000-2099)
    CBD_INNER = list(range(2000, 2100))
    
    # Eastern Suburbs (2020-2039, some 2100s)
    EASTERN = [
        2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030,
        2031, 2032, 2033, 2034, 2035, 2036, 2037, 2038, 2100, 2101,
        2102, 2103, 2104, 2105, 2106, 2107, 2108, 2109, 2110, 2111
    ]
    
    # Northern Beaches (2084-2107)
    NORTHERN_BEACHES = list(range(2084, 2108))
    
    # North Shore (2060-2084)
    NORTH_SHORE = list(range(2060, 2085))
    
    # Inner West (2040-2059)
    INNER_WEST = list(range(2040, 2060))
    
    # Southern Suburbs (2150-2234)
    SOUTHERN = list(range(2150, 2235))
    
    # Western Suburbs (2140-2179, 2740-2799)
    WESTERN = list(range(2140, 2180)) + list(range(2740, 2800))
    
    # South Western (2160-2189, 2560-2579)
    SOUTH_WESTERN = list(range(2160, 2190)) + list(range(2560, 2580))
    
    # Hills District (2120-2159)
    HILLS = list(range(2120, 2160))
    
    @classmethod
    def get_all_sydney_postcodes(cls) -> List[str]:
        """Get all Sydney metro postcodes as strings."""
        all_postcodes = (
            cls.CBD_INNER + cls.EASTERN + cls.NORTHERN_BEACHES + 
            cls.NORTH_SHORE + cls.INNER_WEST + cls.SOUTHERN + 
            cls.WESTERN + cls.SOUTH_WESTERN + cls.HILLS
        )
        return [str(pc) for pc in sorted(set(all_postcodes))]
    
    @classmethod
    def get_premium_postcodes(cls) -> List[str]:
        """Get premium suburb postcodes."""
        premium_postcodes = [
            2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030,  # Eastern beaches
            2061, 2062, 2063, 2064, 2065, 2066, 2067, 2068,  # North Shore premium
            2088, 2089, 2090, 2091, 2092, 2093, 2094, 2095,  # Northern Beaches premium
            2010, 2011, 2015, 2016, 2017, 2021, 2022         # Inner city premium
        ]
        return [str(pc) for pc in premium_postcodes]


@dataclass 
class ListingWatcherConfig:
    """Configuration for the Listing Watcher AU agent."""
    
    # Scraping Configuration
    scraping_mode: ScrapingMode = ScrapingMode.HOURLY
    scraping_interval_seconds: int = 3600  # 1 hour
    batch_size: int = 100
    max_concurrent_requests: int = 5
    
    # Data Sources
    primary_source: DataSource = DataSource.DOMAIN
    secondary_source: DataSource = DataSource.REALESTATE
    enable_cross_validation: bool = True
    
    # Geographic Scope
    target_postcodes: List[str] = field(
        default_factory=SydneyPostcodes.get_all_sydney_postcodes
    )
    focus_premium_areas: bool = True
    premium_postcodes: List[str] = field(
        default_factory=SydneyPostcodes.get_premium_postcodes
    )
    
    # Property Types
    target_property_types: List[str] = field(default_factory=lambda: [
        "House", "Unit", "Apartment", "Townhouse", "Villa", "Duplex", "Terrace"
    ])
    exclude_property_types: List[str] = field(default_factory=lambda: [
        "Land", "Rural", "Commercial", "Industrial"
    ])
    
    # Listing Types
    target_listing_types: List[str] = field(default_factory=lambda: [
        "sale", "auction"
    ])
    
    # Delta Detection Settings
    enable_delta_detection: bool = True
    delta_check_fields: List[str] = field(default_factory=lambda: [
        "price", "price_display", "title", "description", "listing_status",
        "bedrooms", "bathrooms", "car_spaces", "features", "image_urls",
        "auction_date"
    ])
    critical_change_fields: List[str] = field(default_factory=lambda: [
        "price", "listing_status", "auction_date"
    ])
    
    # Data Enrichment Settings
    enable_data_enrichment: bool = True
    enable_feature_extraction: bool = True
    enable_market_analysis: bool = True
    enable_geocoding: bool = False  # Disabled by default to avoid external API costs
    
    # Caching Settings
    cache_ttl_seconds: int = 3600  # 1 hour
    cache_search_results: bool = True
    cache_listing_details: bool = True
    cache_market_data: bool = True
    
    # Rate Limiting
    domain_max_calls_per_hour: int = 1000
    realestate_max_calls_per_hour: int = 500
    rate_limit_buffer: float = 0.1  # 10% buffer
    
    # Error Handling
    max_retries: int = 3
    retry_delay_seconds: int = 5
    backoff_multiplier: float = 2.0
    circuit_breaker_threshold: int = 5  # Failures before circuit breaks
    circuit_breaker_timeout: int = 300  # 5 minutes
    
    # Quality Control
    min_required_fields: List[str] = field(default_factory=lambda: [
        "listing_id", "source", "title", "suburb", "postcode", "property_type"
    ])
    price_validation_range: tuple = (50000, 100000000)  # $50K to $100M
    coordinate_validation_bounds: Dict[str, float] = field(default_factory=lambda: {
        "min_lat": -34.5, "max_lat": -33.0,  # Sydney bounds
        "min_lng": 150.5, "max_lng": 151.8
    })
    
    # Performance Settings
    max_listings_per_batch: int = 1000
    database_batch_size: int = 50
    async_task_timeout: int = 300  # 5 minutes
    
    # Monitoring and Alerting
    enable_performance_monitoring: bool = True
    enable_error_alerting: bool = True
    alert_on_api_failures: bool = True
    alert_on_data_quality_issues: bool = True
    performance_metrics_interval: int = 300  # 5 minutes
    
    # Development/Testing Settings
    dry_run_mode: bool = False
    test_mode_max_listings: int = 10
    enable_debug_logging: bool = False
    save_raw_api_responses: bool = False
    
    def get_active_postcodes(self) -> List[str]:
        """Get the active postcodes for scraping based on configuration."""
        if self.focus_premium_areas:
            return self.premium_postcodes
        return self.target_postcodes
    
    def get_rate_limit_for_source(self, source: str) -> int:
        """Get rate limit for a specific data source."""
        limits = {
            "domain": self.domain_max_calls_per_hour,
            "realestate": self.realestate_max_calls_per_hour
        }
        
        limit = limits.get(source.lower(), 1000)
        # Apply buffer
        return int(limit * (1 - self.rate_limit_buffer))
    
    def should_process_property_type(self, property_type: str) -> bool:
        """Check if a property type should be processed."""
        if not property_type:
            return False
        
        prop_type = property_type.lower().strip()
        
        # Check exclusion list first
        if any(excluded.lower() in prop_type for excluded in self.exclude_property_types):
            return False
        
        # Check inclusion list
        return any(target.lower() in prop_type for target in self.target_property_types)
    
    def get_scraping_schedule(self) -> Dict[str, Any]:
        """Get scraping schedule configuration."""
        if self.scraping_mode == ScrapingMode.HOURLY:
            return {
                "type": "interval",
                "interval_seconds": self.scraping_interval_seconds,
                "immediate_start": True
            }
        elif self.scraping_mode == ScrapingMode.DAILY:
            return {
                "type": "cron",
                "cron_expression": "0 6 * * *",  # 6 AM daily
                "timezone": "Australia/Sydney"
            }
        elif self.scraping_mode == ScrapingMode.CONTINUOUS:
            return {
                "type": "continuous",
                "batch_interval_seconds": 300,  # 5 minutes between batches
                "max_runtime_hours": 24
            }
        else:  # ON_DEMAND
            return {
                "type": "manual",
                "requires_trigger": True
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "scraping_mode": self.scraping_mode.value,
            "scraping_interval_seconds": self.scraping_interval_seconds,
            "batch_size": self.batch_size,
            "max_concurrent_requests": self.max_concurrent_requests,
            "primary_source": self.primary_source.value,
            "secondary_source": self.secondary_source.value,
            "enable_cross_validation": self.enable_cross_validation,
            "target_postcodes_count": len(self.target_postcodes),
            "target_property_types": self.target_property_types,
            "enable_delta_detection": self.enable_delta_detection,
            "enable_data_enrichment": self.enable_data_enrichment,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "max_retries": self.max_retries,
            "dry_run_mode": self.dry_run_mode
        }


# Default configuration instance
DEFAULT_CONFIG = ListingWatcherConfig()


def get_config() -> ListingWatcherConfig:
    """Get the default configuration instance."""
    return DEFAULT_CONFIG


def create_test_config() -> ListingWatcherConfig:
    """Create a configuration optimized for testing."""
    return ListingWatcherConfig(
        scraping_mode=ScrapingMode.ON_DEMAND,
        batch_size=10,
        max_concurrent_requests=2,
        target_postcodes=["2000", "2001", "2010"],  # Small subset
        dry_run_mode=True,
        test_mode_max_listings=10,
        enable_debug_logging=True,
        cache_ttl_seconds=300,  # 5 minutes
        max_retries=1
    )


def create_production_config() -> ListingWatcherConfig:
    """Create a configuration optimized for production."""
    return ListingWatcherConfig(
        scraping_mode=ScrapingMode.HOURLY,
        scraping_interval_seconds=3600,
        batch_size=200,
        max_concurrent_requests=10,
        enable_cross_validation=True,
        focus_premium_areas=False,  # Process all Sydney
        enable_data_enrichment=True,
        enable_performance_monitoring=True,
        enable_error_alerting=True,
        cache_ttl_seconds=1800,  # 30 minutes
        max_retries=3,
        dry_run_mode=False
    )