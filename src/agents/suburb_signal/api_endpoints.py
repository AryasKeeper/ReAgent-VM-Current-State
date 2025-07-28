"""
RESTful API Endpoints for Suburb Signal Agent

Provides comprehensive HTTP API interface for market trend analysis, signal generation,
and real-time suburb intelligence with OpenAPI documentation.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, HTTPException, Query, Path, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import asyncio

from reagent_sydney.agents.suburb_signal.agent import SuburbSignalAgent
from reagent_sydney.agents.suburb_signal.analyzers import AnalysisPeriod, TrendDirection
from reagent_sydney.agents.suburb_signal.signals import SignalType, AlertPriority
from reagent_sydney.agents.suburb_signal.data_aggregator import AggregationPeriod


# Pydantic models for request/response validation

class SuburbAnalysisRequest(BaseModel):
    """Request model for suburb analysis."""
    
    suburbs: List[str] = Field(..., description="List of suburb names to analyze", max_items=50)
    analysis_types: List[str] = Field(
        default=["trend", "signals"],
        description="Types of analysis to perform",
        examples=[["trend", "volume", "comparative", "signals"]]
    )
    time_periods: List[str] = Field(
        default=["weekly"],
        description="Analysis time periods",
        examples=[["daily", "weekly", "monthly"]]
    )
    property_types: Optional[List[str]] = Field(
        None,
        description="Filter by property types",
        examples=[["house", "unit", "townhouse"]]
    )
    price_range: Optional[Dict[str, int]] = Field(
        None,
        description="Price range filter",
        examples=[{"min": 500000, "max": 2000000}]
    )
    include_forecasts: bool = Field(False, description="Include price forecasts")
    use_cache: bool = Field(True, description="Use cached data when available")
    
    @validator('suburbs')
    def validate_suburbs(cls, v):
        if not v:
            raise ValueError("At least one suburb must be specified")
        return v
    
    @validator('analysis_types')
    def validate_analysis_types(cls, v):
        valid_types = ["trend", "volume", "comparative", "signals", "forecasts"]
        invalid = [t for t in v if t not in valid_types]
        if invalid:
            raise ValueError(f"Invalid analysis types: {invalid}")
        return v


class SignalGenerationRequest(BaseModel):
    """Request model for signal generation."""
    
    suburbs: List[str] = Field(..., description="Suburbs to generate signals for", max_items=20)
    signal_types: Optional[List[str]] = Field(
        None,
        description="Types of signals to generate",
        examples=[["trend_change", "opportunity", "risk_warning"]]
    )
    min_confidence: float = Field(0.6, ge=0.0, le=1.0, description="Minimum signal confidence")
    min_strength: float = Field(0.4, ge=0.0, le=1.0, description="Minimum signal strength")


class ComparativeAnalysisRequest(BaseModel):
    """Request model for comparative analysis."""
    
    target_suburb: str = Field(..., description="Target suburb for comparison")
    comparison_group: str = Field(
        "sydney_metro",
        description="Comparison group",
        examples=["lga", "region", "sydney_metro"]
    )
    metrics: List[str] = Field(
        default=["price", "growth", "volume"],
        description="Metrics to compare"
    )


class MarketSummaryRequest(BaseModel):
    """Request model for market summary."""
    
    postcodes: Optional[List[str]] = Field(None, description="Filter by postcodes")
    lgas: Optional[List[str]] = Field(None, description="Filter by LGAs")
    property_types: Optional[List[str]] = Field(None, description="Filter by property types")
    date_range: Optional[Dict[str, str]] = Field(
        None,
        description="Date range for analysis",
        examples=[{"start": "2024-01-01", "end": "2024-12-31"}]
    )


class RankingRequest(BaseModel):
    """Request model for suburb rankings."""
    
    metric: str = Field(
        "composite",
        description="Ranking metric",
        examples=["price", "growth", "volume", "composite"]
    )
    period: str = Field(
        "monthly",
        description="Analysis period",
        examples=["daily", "weekly", "monthly", "quarterly"]
    )
    limit: int = Field(50, ge=1, le=200, description="Number of top suburbs to return")


class AlertManagementRequest(BaseModel):
    """Request model for alert management."""
    
    action: str = Field(..., description="Action to perform", examples=["get", "acknowledge", "resolve"])
    alert_id: Optional[str] = Field(None, description="Alert ID for specific actions")
    suburb: Optional[str] = Field(None, description="Filter alerts by suburb")
    priority: Optional[str] = Field(None, description="Filter alerts by priority")


# Response models

class TrendAnalysisResponse(BaseModel):
    """Response model for trend analysis."""
    
    suburb: str
    period: str
    direction: str
    strength: float
    confidence: float
    price_change_percent: Optional[float]
    current_price: Optional[float]
    volatility: Optional[float]


class MarketSignalResponse(BaseModel):
    """Response model for market signals."""
    
    signal_id: str
    suburb_name: str
    signal_type: str
    strength: float
    confidence: float
    title: str
    description: str
    implications: str
    created_at: datetime
    expires_at: Optional[datetime]


class MarketAlertResponse(BaseModel):
    """Response model for market alerts."""
    
    alert_id: str
    suburb_name: str
    alert_type: str
    priority: str
    title: str
    message: str
    created_at: datetime
    age_hours: float
    is_active: bool


class SuburbRankingResponse(BaseModel):
    """Response model for suburb rankings."""
    
    rank: int
    suburb: str
    postcode: Optional[str]
    score: float
    median_price: float
    growth_12m: float
    sales_volume: int
    percentile: float


class AnalysisResultsResponse(BaseModel):
    """Response model for analysis results."""
    
    request_id: str
    analysis_timestamp: datetime
    execution_time_seconds: float
    suburbs_analyzed: List[str]
    trend_analyses: Optional[Dict[str, Dict[str, TrendAnalysisResponse]]] = None
    signals: Optional[List[MarketSignalResponse]] = None
    alerts: Optional[List[MarketAlertResponse]] = None
    summary: Dict[str, Any]


# Create router
router = APIRouter(prefix="/api/v1/suburb-signal", tags=["Suburb Signal Agent"])

# Dependency to get agent instance
async def get_suburb_signal_agent() -> SuburbSignalAgent:
    """Get initialized Suburb Signal Agent."""
    agent = SuburbSignalAgent()
    await agent.initialize()
    return agent


@router.post(
    "/analyze",
    response_model=AnalysisResultsResponse,
    summary="Analyze Suburb Market Trends",
    description="""
    Perform comprehensive market analysis for specified Sydney suburbs.
    
    Supports multiple analysis types:
    - **trend**: Price trend analysis with MACD and momentum indicators
    - **volume**: Trading volume and market activity analysis  
    - **comparative**: Comparative performance vs peer suburbs
    - **signals**: Generate actionable market signals
    
    Analysis can be performed across multiple time periods simultaneously.
    Results include trend direction, strength, confidence scores, and generated signals.
    """
)
async def analyze_suburbs(
    request: SuburbAnalysisRequest,
    background_tasks: BackgroundTasks,
    agent: SuburbSignalAgent = Depends(get_suburb_signal_agent)
):
    """Analyze market trends for specified suburbs."""
    try:
        # Convert time periods to enum
        time_periods = [AnalysisPeriod(p) for p in request.time_periods]
        
        # Execute analysis
        results = await agent.analyze_suburbs(
            suburbs=request.suburbs,
            analysis_types=request.analysis_types,
            time_periods=time_periods,
            property_types=request.property_types,
            price_range=tuple(request.price_range.values()) if request.price_range else None,
            include_forecasts=request.include_forecasts,
            use_cache=request.use_cache
        )
        
        # Schedule background cache warming for related suburbs
        if len(request.suburbs) < 10:
            background_tasks.add_task(
                _warm_related_suburb_caches,
                agent,
                request.suburbs
            )
        
        # Format response
        response = AnalysisResultsResponse(
            request_id=results.request_id,
            analysis_timestamp=results.analysis_timestamp,
            execution_time_seconds=results.execution_time,
            suburbs_analyzed=results.suburbs_analyzed,
            summary=results.summary_stats or {}
        )
        
        # Add trend analyses
        if results.trend_analysis:
            response.trend_analyses = {}
            for suburb, trends in results.trend_analysis.items():
                response.trend_analyses[suburb] = {
                    period: TrendAnalysisResponse(
                        suburb=suburb,
                        period=period,
                        direction=trend.direction.value,
                        strength=trend.strength,
                        confidence=trend.confidence,
                        price_change_percent=trend.price_change_percent,
                        current_price=float(trend.current_price) if trend.current_price else None,
                        volatility=trend.volatility
                    )
                    for period, trend in trends.items()
                }
        
        # Add signals
        if results.signals:
            response.signals = [
                MarketSignalResponse(
                    signal_id=signal.signal_id,
                    suburb_name=signal.suburb_name,
                    signal_type=signal.signal_type.value,
                    strength=signal.strength,
                    confidence=signal.confidence,
                    title=signal.title,
                    description=signal.description,
                    implications=signal.implications,
                    created_at=signal.created_at,
                    expires_at=signal.expires_at
                )
                for signal in results.signals
            ]
        
        # Add alerts
        if results.alerts:
            response.alerts = [
                MarketAlertResponse(
                    alert_id=alert.alert_id,
                    suburb_name=alert.suburb_name,
                    alert_type=alert.alert_type.value,
                    priority=alert.priority.value,
                    title=alert.title,
                    message=alert.message,
                    created_at=alert.created_at,
                    age_hours=alert.age_hours,
                    is_active=alert.is_active
                )
                for alert in results.alerts
            ]
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post(
    "/signals",
    response_model=List[MarketSignalResponse],
    summary="Generate Market Signals",
    description="""
    Generate actionable market signals for specified suburbs.
    
    Signals include:
    - **Trend changes**: Direction reversals and momentum shifts
    - **Volume anomalies**: Unusual trading activity
    - **Price breakouts**: Significant price movements
    - **Opportunities**: Undervalued markets with growth potential
    - **Risk warnings**: Overheated or declining markets
    
    Each signal includes confidence scoring and actionable implications.
    """
)
async def generate_signals(
    request: SignalGenerationRequest,
    agent: SuburbSignalAgent = Depends(get_suburb_signal_agent)
):
    """Generate market signals for specified suburbs."""
    try:
        all_signals = []
        
        # Generate signals for each suburb
        for suburb in request.suburbs:
            signal_types = [SignalType(t) for t in request.signal_types] if request.signal_types else None
            signals = await agent.generate_signals_for_suburb(suburb, signal_types)
            
            # Filter by confidence and strength
            filtered_signals = [
                s for s in signals 
                if s.confidence >= request.min_confidence and s.strength >= request.min_strength
            ]
            
            all_signals.extend(filtered_signals)
        
        # Sort by strength * confidence
        all_signals.sort(key=lambda s: s.strength * s.confidence, reverse=True)
        
        # Convert to response format
        response_signals = [
            MarketSignalResponse(
                signal_id=signal.signal_id,
                suburb_name=signal.suburb_name,
                signal_type=signal.signal_type.value,
                strength=signal.strength,
                confidence=signal.confidence,
                title=signal.title,
                description=signal.description,
                implications=signal.implications,
                created_at=signal.created_at,
                expires_at=signal.expires_at
            )
            for signal in all_signals[:50]  # Limit to top 50 signals
        ]
        
        return response_signals
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal generation failed: {str(e)}")


@router.post(
    "/compare",
    summary="Compare Suburb Performance",
    description="""
    Perform comparative analysis of a target suburb against peer groups.
    
    Provides:
    - **Rankings**: Position relative to peer suburbs
    - **Percentiles**: Performance percentile scores
    - **Benchmarks**: Comparison against regional averages
    - **Scores**: Normalized performance metrics
    
    Comparison groups include LGA, region, or entire Sydney metro area.
    """
)
async def compare_suburb_performance(
    request: ComparativeAnalysisRequest,
    agent: SuburbSignalAgent = Depends(get_suburb_signal_agent)
):
    """Compare suburb performance against peers."""
    try:
        # Get comparative data
        comparative_data = await agent.data_aggregator.aggregate_comparative_metrics(
            suburbs=[request.target_suburb],
            comparison_group=request.comparison_group
        )
        
        if request.target_suburb not in comparative_data:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for suburb '{request.target_suburb}'"
            )
        
        data = comparative_data[request.target_suburb]
        
        response = {
            'suburb': request.target_suburb,
            'comparison_group': request.comparison_group,
            'rankings': {},
            'percentiles': {},
            'metrics': {},
            'total_suburbs': data.get('total_suburbs', 0)
        }
        
        # Add requested metrics
        for metric in request.metrics:
            if f'rank_{metric}' in data:
                response['rankings'][metric] = data[f'rank_{metric}']
            if f'percentile_{metric}' in data:
                response['percentiles'][metric] = data[f'percentile_{metric}']
        
        # Add raw metrics
        response['metrics'] = {
            'median_price': float(data.get('median_price', 0)),
            'growth_12m': data.get('price_growth_12m', 0.0),
            'sales_volume_30d': data.get('sales_volume_30d', 0)
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.get(
    "/rankings",
    response_model=List[SuburbRankingResponse],
    summary="Get Suburb Rankings",
    description="""
    Retrieve suburb rankings for specified metrics and time periods.
    
    Available metrics:
    - **price**: Median price rankings
    - **growth**: 12-month growth rate rankings  
    - **volume**: Sales volume rankings
    - **composite**: Weighted composite score rankings
    
    Rankings are updated regularly and cached for performance.
    """
)
async def get_suburb_rankings(
    metric: str = Query("composite", description="Ranking metric"),
    period: str = Query("monthly", description="Analysis period"),
    limit: int = Query(50, ge=1, le=200, description="Number of suburbs to return"),
    agent: SuburbSignalAgent = Depends(get_suburb_signal_agent)
):
    """Get suburb rankings for specified metric."""
    try:
        period_enum = AggregationPeriod(period)
        rankings = await agent.get_suburb_rankings(metric, period_enum, limit)
        
        response = [
            SuburbRankingResponse(
                rank=ranking['rank'],
                suburb=ranking['suburb'],
                postcode=ranking.get('postcode'),
                score=ranking['score'],
                median_price=ranking['median_price'],
                growth_12m=ranking['growth_12m'],
                sales_volume=ranking['sales_volume'],
                percentile=ranking['percentile']
            )
            for ranking in rankings
        ]
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rankings retrieval failed: {str(e)}")


@router.post(
    "/market-summary",
    summary="Generate Market Summary",
    description="""
    Generate comprehensive market summary statistics with optional filtering.
    
    Provides:
    - **Market overview**: Total suburbs, properties, median prices
    - **Top performers**: Highest ranking suburbs
    - **Market sentiment**: Overall market direction
    - **Active alerts**: Current market alerts count
    - **Growth trends**: Regional growth patterns
    
    Supports filtering by postcodes, LGAs, property types, and date ranges.
    """
)
async def generate_market_summary(
    request: MarketSummaryRequest,
    agent: SuburbSignalAgent = Depends(get_suburb_signal_agent)
):
    """Generate comprehensive market summary."""
    try:
        # Parse date range if provided
        filters = {}
        if request.postcodes:
            filters['postcodes'] = request.postcodes
        if request.lgas:
            filters['lgas'] = request.lgas
        if request.property_types:
            filters['property_types'] = request.property_types
        if request.date_range:
            try:
                start_date = datetime.fromisoformat(request.date_range['start'])
                end_date = datetime.fromisoformat(request.date_range['end'])
                filters['date_range'] = (start_date, end_date)
            except (KeyError, ValueError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid date range: {str(e)}")
        
        # Get market summary
        summary = await agent.get_market_summary(**filters)
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Market summary generation failed: {str(e)}")


@router.post(
    "/alerts",
    response_model=Dict[str, Any],
    summary="Manage Market Alerts",
    description="""
    Manage market alerts including retrieving, acknowledging, and resolving alerts.
    
    Available actions:
    - **get**: Retrieve active alerts with optional filtering
    - **acknowledge**: Mark alert as acknowledged
    - **resolve**: Mark alert as resolved
    
    Alerts are automatically generated from high-confidence market signals.
    """
)
async def manage_alerts(
    request: AlertManagementRequest,
    agent: SuburbSignalAgent = Depends(get_suburb_signal_agent)
):
    """Manage market alerts."""
    try:
        if request.action == "get":
            # Get active alerts
            priority_enum = AlertPriority(request.priority) if request.priority else None
            alerts = await agent.alert_manager.get_active_alerts(
                suburb=request.suburb,
                priority=priority_enum
            )
            
            response = {
                'action': 'get',
                'active_alerts': len(alerts),
                'alerts': [
                    MarketAlertResponse(
                        alert_id=alert.alert_id,
                        suburb_name=alert.suburb_name,
                        alert_type=alert.alert_type.value,
                        priority=alert.priority.value,
                        title=alert.title,
                        message=alert.message,
                        created_at=alert.created_at,
                        age_hours=alert.age_hours,
                        is_active=alert.is_active
                    )
                    for alert in alerts[:50]  # Limit to 50 alerts
                ]
            }
            
        elif request.action == "acknowledge":
            if not request.alert_id:
                raise HTTPException(status_code=400, detail="alert_id required for acknowledge action")
            
            success = await agent.alert_manager.acknowledge_alert(request.alert_id)
            response = {
                'action': 'acknowledge',
                'alert_id': request.alert_id,
                'success': success
            }
            
        elif request.action == "resolve":
            if not request.alert_id:
                raise HTTPException(status_code=400, detail="alert_id required for resolve action")
            
            success = await agent.alert_manager.resolve_alert(request.alert_id)
            response = {
                'action': 'resolve',
                'alert_id': request.alert_id,
                'success': success
            }
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Alert management failed: {str(e)}")


@router.get(
    "/suburbs/{suburb}/trend",
    summary="Get Suburb Trend Analysis",
    description="""
    Get detailed trend analysis for a specific suburb.
    
    Returns comprehensive trend metrics including:
    - Price trend direction and strength
    - MACD and momentum indicators
    - Volume patterns and anomalies
    - Confidence scores and data quality metrics
    
    Supports multiple time periods for multi-timeframe analysis.
    """
)
async def get_suburb_trend(
    suburb: str = Path(..., description="Suburb name"),
    periods: List[str] = Query(["weekly"], description="Analysis periods"),
    agent: SuburbSignalAgent = Depends(get_suburb_signal_agent)
):
    """Get trend analysis for specific suburb."""
    try:
        # Convert periods to enum
        time_periods = [AnalysisPeriod(p) for p in periods]
        
        # Analyze single suburb
        results = await agent.analyze_suburbs(
            suburbs=[suburb],
            analysis_types=["trend"],
            time_periods=time_periods
        )
        
        if suburb not in results.trend_analysis:
            raise HTTPException(
                status_code=404,
                detail=f"No trend data available for suburb '{suburb}'"
            )
        
        # Format response
        trends = results.trend_analysis[suburb]
        response = {
            'suburb': suburb,
            'analysis_timestamp': results.analysis_timestamp.isoformat(),
            'trends': {
                period: {
                    'direction': trend.direction.value,
                    'strength': trend.strength,
                    'confidence': trend.confidence,
                    'price_change_percent': trend.price_change_percent,
                    'current_price': float(trend.current_price) if trend.current_price else None,
                    'volatility': trend.volatility,
                    'macd': trend.macd,
                    'momentum': trend.momentum
                }
                for period, trend in trends.items()
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trend analysis failed: {str(e)}")


@router.get(
    "/health",
    summary="Agent Health Check",
    description="Check the health and status of the Suburb Signal Agent."
)
async def health_check(agent: SuburbSignalAgent = Depends(get_suburb_signal_agent)):
    """Health check for Suburb Signal Agent."""
    try:
        # Get cache statistics
        cache_stats = await agent.cache_manager.get_cache_stats()
        
        # Get analysis statistics
        analysis_stats = agent.analysis_stats
        
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'agent_version': agent.config.version,
            'cache_stats': {
                'overall_hit_rate': cache_stats.get('overall', {}).get('overall_hit_rate', 0),
                'total_requests': cache_stats.get('overall', {}).get('total_requests', 0),
                'cache_size_mb': cache_stats.get('overall', {}).get('cache_size_mb', 0)
            },
            'analysis_stats': {
                'total_analyses': analysis_stats['total_analyses'],
                'avg_execution_time': analysis_stats['avg_execution_time'],
                'suburbs_per_minute': analysis_stats['suburbs_per_minute']
            }
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                'status': 'unhealthy',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
        )


# Background task functions

async def _warm_related_suburb_caches(agent: SuburbSignalAgent, suburbs: List[str]):
    """Warm caches for suburbs related to the analyzed ones."""
    try:
        # This would identify related suburbs (same LGA, nearby postcodes, etc.)
        # and pre-warm their cache entries
        
        await asyncio.sleep(1)  # Placeholder for actual implementation
        agent.logger.info(f"Warmed caches for suburbs related to: {suburbs}")
        
    except Exception as e:
        agent.logger.error(f"Error warming related caches: {e}")


# Add router to main FastAPI app
def include_suburb_signal_routes(app):
    """Include Suburb Signal Agent routes in FastAPI app."""
    app.include_router(router)