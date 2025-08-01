"""
ReAgent Sydney - Business Metrics

Business-specific metrics for real estate intelligence tracking.
Focuses on property market insights, buyer behavior, and agent performance.
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from prometheus_client import Counter, Histogram, Gauge
from reagent.utils.logging import get_logger

# =================================================================
# PROPERTY MARKET METRICS
# =================================================================

# Property listing changes
listing_status_changes_total = Counter(
    'listing_status_changes_total',
    'Total property listing status changes',
    ['suburb', 'property_type', 'old_status', 'new_status']
)

listing_processing_duration_seconds = Histogram(
    'listing_processing_duration_seconds',
    'Time to process new property listings',
    ['source', 'property_type'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, float('inf')]
)

# Property price tracking
property_price_change_events_total = Counter(
    'property_price_change_events_total',
    'Total property price change events detected',
    ['suburb', 'property_type', 'change_direction']
)

property_price_variance = Histogram(
    'property_price_variance',
    'Property price change amounts in AUD',
    ['suburb', 'property_type'],
    buckets=[1000, 5000, 10000, 25000, 50000, 100000, 250000, 500000, float('inf')]
)

market_median_price = Gauge(
    'market_median_price_aud',
    'Median property price by suburb and type',
    ['suburb', 'property_type']
)

# Days on market tracking
days_on_market_histogram = Histogram(
    'days_on_market',
    'Distribution of days properties spend on market',
    ['suburb', 'property_type'],
    buckets=[7, 14, 30, 60, 90, 180, 365, float('inf')]
)

# =================================================================
# BUYER BEHAVIOR METRICS
# =================================================================

# Buyer matching and preferences
buyer_search_queries_total = Counter(
    'buyer_search_queries_total',
    'Total buyer search queries',
    ['query_type', 'suburb', 'property_type']
)

buyer_preference_updates_total = Counter(
    'buyer_preference_updates_total',  
    'Total buyer preference updates',
    ['update_type', 'buyer_segment']
)

buyer_inspection_bookings_total = Counter(
    'buyer_inspection_bookings_total',
    'Total inspection bookings generated',
    ['booking_source', 'property_type', 'suburb']
)

buyer_engagement_score = Gauge(
    'buyer_engagement_score',
    'Buyer engagement score (0-10)',
    ['buyer_id', 'engagement_type']
)

# Match quality metrics
match_accuracy_score = Gauge(
    'match_accuracy_score',
    'Buyer-property match accuracy (0-1)',
    ['match_algorithm', 'property_type']
)

match_conversion_rate = Gauge(
    'match_conversion_rate',
    'Rate of matches leading to inspections',
    ['suburb', 'property_type']
)

# =================================================================
# AGENT PERFORMANCE METRICS
# =================================================================

# Agent workflow metrics
agent_task_completion_rate = Gauge(
    'agent_task_completion_rate',
    'Agent task completion rate (0-1)',
    ['agent_name', 'task_type']
)

agent_recommendation_accuracy = Gauge(
    'agent_recommendation_accuracy',
    'Agent recommendation accuracy (0-1)',
    ['agent_name', 'recommendation_type']
)

agent_data_freshness_seconds = Gauge(
    'agent_data_freshness_seconds',
    'Age of data used by agents in seconds',
    ['agent_name', 'data_source']
)

# Multi-agent coordination
agent_collaboration_events_total = Counter(
    'agent_collaboration_events_total',
    'Total inter-agent collaboration events',
    ['initiating_agent', 'target_agent', 'collaboration_type']
)

workflow_handoff_duration_seconds = Histogram(
    'workflow_handoff_duration_seconds',
    'Time for workflow handoffs between agents',
    ['from_agent', 'to_agent'],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, float('inf')]
)

# =================================================================
# MARKET INTELLIGENCE METRICS
# =================================================================

# Suburb signal analysis
suburb_trend_accuracy = Gauge(
    'suburb_trend_accuracy',
    'Accuracy of suburb trend predictions',
    ['suburb', 'trend_type']
)

market_anomaly_detection_events = Counter(
    'market_anomaly_detection_events_total',
    'Market anomalies detected',
    ['anomaly_type', 'suburb', 'severity']
)

off_market_opportunities_found = Counter(
    'off_market_opportunities_found_total',
    'Off-market opportunities identified',
    ['opportunity_type', 'suburb', 'confidence_level']
)

council_da_applications_tracked = Counter(
    'council_da_applications_tracked_total',
    'Development applications tracked',
    ['council', 'application_type', 'status']
)

# Seller strategy metrics
pricing_recommendation_accuracy = Gauge(
    'pricing_recommendation_accuracy',
    'Accuracy of pricing recommendations',
    ['strategy_type', 'property_type']
)

market_timing_score = Gauge(
    'market_timing_score',
    'Market timing recommendation score (0-10)',
    ['suburb', 'property_type', 'season']
)

# =================================================================
# EXTERNAL DATA SOURCE METRICS
# =================================================================

# API usage and performance
api_quota_utilization = Gauge(
    'api_quota_utilization',
    'API quota utilization (0-1)',
    ['api_provider', 'quota_type']
)

api_data_freshness_minutes = Gauge(
    'api_data_freshness_minutes',
    'Age of data from external APIs in minutes',
    ['api_provider', 'data_type']
)

api_cost_tracking_aud = Counter(
    'api_cost_tracking_aud_total',
    'Total API costs in AUD',
    ['api_provider', 'cost_type']
)

# Data quality from external sources
external_data_quality_score = Gauge(
    'external_data_quality_score',
    'Quality score for external data (0-1)',
    ['data_source', 'data_type']
)

data_completeness_ratio = Gauge(
    'data_completeness_ratio',
    'Completeness ratio for property data (0-1)',
    ['data_source', 'field_category']
)

# =================================================================
# BUSINESS IMPACT METRICS
# =================================================================

# User satisfaction and engagement
user_satisfaction_score = Gauge(
    'user_satisfaction_score',
    'User satisfaction score (1-10)',
    ['user_type', 'feature_category']
)

user_retention_rate = Gauge(
    'user_retention_rate',
    'User retention rate (0-1)',
    ['user_segment', 'time_period']
)

feature_usage_frequency = Counter(
    'feature_usage_frequency_total',
    'Feature usage frequency',
    ['feature_name', 'user_type']
)

# Business outcomes
leads_generated_total = Counter(
    'leads_generated_total',
    'Total leads generated',
    ['lead_source', 'lead_quality', 'suburb']
)

conversion_funnel_progress = Counter(
    'conversion_funnel_progress_total',
    'Progress through conversion funnel',
    ['funnel_stage', 'user_segment']
)

revenue_impact_aud = Gauge(
    'revenue_impact_aud',
    'Revenue impact in AUD',
    ['impact_source', 'time_period']
)

# =================================================================
# BUSINESS METRICS UTILITIES
# =================================================================

@dataclass
class PropertyMarketUpdate:
    """Data class for property market updates."""
    suburb: str
    property_type: str
    median_price: float
    price_change_pct: float
    days_on_market_avg: float
    total_listings: int
    new_listings: int
    sold_listings: int

@dataclass
class BuyerBehaviorSnapshot:
    """Data class for buyer behavior snapshots."""
    total_active_buyers: int
    searches_per_day: int
    top_searched_suburbs: List[str]
    average_budget: float
    inspection_conversion_rate: float

class BusinessMetricsCollector:
    """Collector for business-specific metrics."""
    
    def __init__(self):
        self.last_collection_time = time.time()
        
    def update_property_market_metrics(self, market_data: PropertyMarketUpdate):
        """Update property market metrics."""
        # Update median price
        market_median_price.labels(
            suburb=market_data.suburb,
            property_type=market_data.property_type
        ).set(market_data.median_price)
        
        # Record days on market
        days_on_market_histogram.labels(
            suburb=market_data.suburb,
            property_type=market_data.property_type
        ).observe(market_data.days_on_market_avg)
        
        logger.info(
            "Updated property market metrics",
            suburb=market_data.suburb,
            property_type=market_data.property_type,
            median_price=market_data.median_price,
            total_listings=market_data.total_listings
        )
    
    def update_buyer_behavior_metrics(self, behavior_data: BuyerBehaviorSnapshot):
        """Update buyer behavior metrics."""
        # Update buyer profiles active
        from .metrics import buyer_profiles_active
        buyer_profiles_active.set(behavior_data.total_active_buyers)
        
        # Update conversion rate
        match_conversion_rate.labels(
            suburb="all",  # Aggregate across suburbs
            property_type="all"
        ).set(behavior_data.inspection_conversion_rate)
        
        logger.info(
            "Updated buyer behavior metrics",
            active_buyers=behavior_data.total_active_buyers,
            daily_searches=behavior_data.searches_per_day,
            conversion_rate=behavior_data.inspection_conversion_rate
        )
    
    def record_agent_performance(self, agent_name: str, task_type: str, 
                               completion_rate: float, accuracy: float):
        """Record agent performance metrics."""
        agent_task_completion_rate.labels(
            agent_name=agent_name,
            task_type=task_type
        ).set(completion_rate)
        
        agent_recommendation_accuracy.labels(
            agent_name=agent_name,
            recommendation_type=task_type
        ).set(accuracy)
        
        logger.info(
            "Updated agent performance metrics",
            agent_name=agent_name,
            task_type=task_type,
            completion_rate=completion_rate,
            accuracy=accuracy
        )
    
    def record_market_anomaly(self, anomaly_type: str, suburb: str, 
                            severity: str = "medium"):
        """Record a market anomaly detection."""
        market_anomaly_detection_events.labels(
            anomaly_type=anomaly_type,
            suburb=suburb,
            severity=severity
        ).inc()
        
        logger.warning(
            "Market anomaly detected",
            anomaly_type=anomaly_type,
            suburb=suburb,
            severity=severity
        )
    
    def record_off_market_opportunity(self, opportunity_type: str, 
                                    suburb: str, confidence: str = "medium"):
        """Record an off-market opportunity."""
        off_market_opportunities_found.labels(
            opportunity_type=opportunity_type,
            suburb=suburb,
            confidence_level=confidence
        ).inc()
        
        logger.info(
            "Off-market opportunity found",
            opportunity_type=opportunity_type,
            suburb=suburb,
            confidence=confidence
        )
    
    def update_api_quota_usage(self, api_provider: str, quota_type: str, 
                              utilization: float):
        """Update API quota utilization."""
        api_quota_utilization.labels(
            api_provider=api_provider,
            quota_type=quota_type
        ).set(utilization)
        
        # Alert if utilization is high
        if utilization > 0.9:
            logger.warning(
                "High API quota utilization",
                api_provider=api_provider,
                quota_type=quota_type,
                utilization=utilization
            )
    
    def get_business_health_summary(self) -> Dict[str, Any]:
        """Get a summary of key business health metrics."""
        current_time = time.time()
        
        # This would typically query the metrics backend
        return {
            "timestamp": current_time,
            "property_market": {
                "total_listings_tracked": "50000+",  # Would be actual value
                "price_updates_last_hour": "150",
                "market_coverage_suburbs": "200+"
            },
            "buyer_engagement": {
                "active_profiles": "1000+",
                "matches_created_today": "50",
                "inspection_conversion_rate": "15%"
            },
            "agent_performance": {
                "average_task_completion": "95%",
                "recommendation_accuracy": "85%",
                "data_freshness": "< 5 minutes"
            },
            "system_efficiency": {
                "api_quota_utilization": "< 80%",
                "processing_latency": "< 30 seconds",
                "error_rate": "< 1%"
            }
        }