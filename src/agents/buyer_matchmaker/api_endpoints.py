"""
Buyer Matchmaker AU - API Endpoints

FastAPI endpoints for buyer matching operations, preference management,
and performance monitoring.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body
from pydantic import BaseModel, Field

from reagent_sydney.agents.buyer_matchmaker import (
    BuyerMatchmakerAgent, 
    setup_vector_schemas,
    sync_properties_to_vector_db,
    get_matching_performance_metrics
)
from reagent_sydney.core.database.dependencies import get_db_session
from reagent_sydney.data.models.buyer_models import Buyer, BuyerPreferences, PropertyMatch

import structlog


# Pydantic models for API requests/responses
class MatchRequest(BaseModel):
    """Request model for generating property matches."""
    
    buyer_ids: Optional[List[str]] = Field(None, description="Specific buyer IDs to match")
    force_refresh: bool = Field(False, description="Force refresh of cached matches")
    max_matches: int = Field(10, description="Maximum matches per buyer", ge=1, le=50)


class MatchResponse(BaseModel):
    """Response model for property matches."""
    
    success: bool
    buyer_id: str
    matches_count: int
    matches: List[Dict[str, Any]]
    execution_time_seconds: float
    cached: bool = False


class PreferencesUpdateRequest(BaseModel):
    """Request model for updating buyer preferences."""
    
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    property_types: Optional[List[str]] = None
    preferred_suburbs: Optional[List[str]] = None
    excluded_suburbs: Optional[List[str]] = None
    min_bedrooms: Optional[int] = None
    max_bedrooms: Optional[int] = None
    min_bathrooms: Optional[int] = None
    required_features: Optional[List[str]] = None
    preferred_features: Optional[List[str]] = None
    budget_flexibility: Optional[float] = Field(None, ge=0, le=1)


class FeedbackRequest(BaseModel):
    """Request model for recording buyer feedback."""
    
    feedback: str = Field(..., description="Buyer feedback text")
    interest_level: Optional[str] = Field(None, description="Interest level")
    notes: Optional[str] = Field(None, description="Additional notes")


class SyncRequest(BaseModel):
    """Request model for vector database synchronization."""
    
    batch_size: int = Field(100, description="Batch size for processing", ge=10, le=1000)
    force_update: bool = Field(False, description="Force update all properties")


# Router setup
router = APIRouter(prefix="/api/v1/buyer-matchmaker", tags=["Buyer Matchmaker"])
logger = structlog.get_logger("api.buyer_matchmaker")


@router.post("/matches", response_model=Dict[str, Any])
async def generate_matches(
    request: MatchRequest = Body(...),
    session = Depends(get_db_session)
):
    """
    Generate property matches for buyers using AI matching algorithms.
    
    - **buyer_ids**: Optional list of specific buyer IDs to match
    - **force_refresh**: Skip cache and generate fresh matches
    - **max_matches**: Maximum number of matches per buyer
    """
    try:
        # Initialize agent
        agent = BuyerMatchmakerAgent()
        await agent.initialize()
        
        # Execute matching
        result = await agent.execute({
            "operation": "generate_matches",
            "buyer_ids": request.buyer_ids or [],
            "force_refresh": request.force_refresh,
            "max_matches": request.max_matches
        })
        
        logger.info("Generated matches via API", 
                   buyer_count=result.get("buyers_processed", 0),
                   total_matches=result.get("total_matches_generated", 0))
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating matches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buyers/{buyer_id}/matches", response_model=Dict[str, Any])
async def get_buyer_matches(
    buyer_id: str = Path(..., description="Buyer UUID"),
    status: Optional[str] = Query(None, description="Filter by match status"),
    limit: int = Query(20, description="Maximum matches to return", ge=1, le=100),
    session = Depends(get_db_session)
):
    """
    Retrieve stored property matches for a specific buyer.
    
    - **buyer_id**: UUID of the buyer
    - **status**: Optional status filter (new, viewed, interested, not_interested)
    - **limit**: Maximum number of matches to return
    """
    try:
        from reagent_sydney.agents.buyer_matchmaker.utils import match_storage_manager
        
        matches = await match_storage_manager.get_buyer_matches(buyer_id, status, limit)
        
        # Convert matches to API response format
        match_data = []
        for match in matches:
            match_info = {
                "match_id": str(match.id),
                "property_id": str(match.property_id),
                "match_score": float(match.match_score),
                "match_rank": match.match_rank,
                "status": match.status,
                "created_at": match.created_at.isoformat(),
                "match_reasons": match.match_reasons,
                "match_concerns": match.match_concerns,
                "price_assessment": match.price_assessment,
                "estimated_value": float(match.estimated_value) if match.estimated_value else None
            }
            
            # Add property details if available
            if match.property:
                match_info["property"] = {
                    "title": match.property.title,
                    "address": f"{match.property.address_line_1}, {match.property.suburb}",
                    "price": float(match.property.price) if match.property.price else None,
                    "price_display": match.property.price_display,
                    "bedrooms": match.property.bedrooms,
                    "bathrooms": match.property.bathrooms,
                    "property_type": match.property.property_type,
                    "image_urls": match.property.image_urls
                }
            
            match_data.append(match_info)
        
        return {
            "success": True,
            "buyer_id": buyer_id,
            "matches_count": len(match_data),
            "matches": match_data,
            "status_filter": status
        }
        
    except Exception as e:
        logger.error(f"Error retrieving matches for buyer {buyer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/buyers/{buyer_id}/preferences", response_model=Dict[str, Any])
async def update_buyer_preferences(
    buyer_id: str = Path(..., description="Buyer UUID"),
    request: PreferencesUpdateRequest = Body(...),
    session = Depends(get_db_session)
):
    """
    Update buyer preferences and regenerate their matching profile.
    
    - **buyer_id**: UUID of the buyer
    - **request**: Updated preference values
    """
    try:
        # Initialize agent
        agent = BuyerMatchmakerAgent()
        await agent.initialize()
        
        # Convert request to dict, excluding None values
        preferences = {
            k: v for k, v in request.dict().items() 
            if v is not None
        }
        
        result = await agent.execute({
            "operation": "update_buyer_profile",
            "buyer_id": buyer_id,
            "preferences": preferences
        })
        
        logger.info(f"Updated preferences for buyer {buyer_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error updating preferences for buyer {buyer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/matches/{match_id}/feedback", response_model=Dict[str, Any])
async def record_match_feedback(
    match_id: str = Path(..., description="Match UUID"),
    request: FeedbackRequest = Body(...),
    session = Depends(get_db_session)
):
    """
    Record buyer feedback on a property match for learning and improvement.
    
    - **match_id**: UUID of the property match
    - **request**: Feedback details
    """
    try:
        # Initialize agent
        agent = BuyerMatchmakerAgent()
        await agent.initialize()
        
        result = await agent.execute({
            "operation": "record_feedback",
            "match_id": match_id,
            "feedback": request.feedback,
            "interest_level": request.interest_level,
            "notes": request.notes
        })
        
        logger.info(f"Recorded feedback for match {match_id}: {request.feedback}")
        return result
        
    except Exception as e:
        logger.error(f"Error recording feedback for match {match_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/matches/{match_id}/explanation", response_model=Dict[str, Any])
async def get_match_explanation(
    match_id: str = Path(..., description="Match UUID"),
    session = Depends(get_db_session)
):
    """
    Get detailed explanation for why a property was matched to a buyer.
    
    - **match_id**: UUID of the property match
    """
    try:
        # Initialize agent
        agent = BuyerMatchmakerAgent()
        await agent.initialize()
        
        result = await agent.execute({
            "operation": "get_match_explanation",
            "match_id": match_id
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting explanation for match {match_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buyers/{buyer_id}/behavior-analysis", response_model=Dict[str, Any])
async def analyze_buyer_behavior(
    buyer_id: str = Path(..., description="Buyer UUID"),
    analysis_days: int = Query(30, description="Days to analyze", ge=1, le=365),
    session = Depends(get_db_session)
):
    """
    Analyze buyer behavior patterns to improve matching recommendations.
    
    - **buyer_id**: UUID of the buyer
    - **analysis_days**: Number of days to analyze
    """
    try:
        from reagent_sydney.agents.buyer_matchmaker.tools import BuyerBehaviorAnalysisTool
        
        tool = BuyerBehaviorAnalysisTool()
        analysis = await tool.run(buyer_id, analysis_days)
        
        return {
            "success": True,
            "buyer_id": buyer_id,
            "analysis_period_days": analysis_days,
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Error analyzing behavior for buyer {buyer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/properties", response_model=Dict[str, Any])
async def sync_properties(
    request: SyncRequest = Body(SyncRequest()),
    session = Depends(get_db_session)
):
    """
    Synchronize properties from PostgreSQL to Weaviate vector database.
    
    - **batch_size**: Number of properties to process in each batch
    - **force_update**: Force update all properties regardless of last sync
    """
    try:
        result = await sync_properties_to_vector_db(
            batch_size=request.batch_size,
            force_update=request.force_update
        )
        
        logger.info("Property sync completed via API", 
                   properties_processed=result.get("properties_processed", 0))
        
        return {
            "success": True,
            "operation": "property_sync",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error syncing properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/buyer-profiles", response_model=Dict[str, Any])
async def sync_buyer_profiles(
    buyer_ids: Optional[List[str]] = Body(None, description="Specific buyer IDs to sync"),
    session = Depends(get_db_session)
):
    """
    Synchronize buyer profiles to Weaviate vector database.
    
    - **buyer_ids**: Optional list of specific buyer IDs to sync
    """
    try:
        from reagent_sydney.agents.buyer_matchmaker.utils import sync_buyer_profiles_to_vector_db
        
        result = await sync_buyer_profiles_to_vector_db(buyer_ids)
        
        logger.info("Buyer profile sync completed via API",
                   profiles_processed=result.get("profiles_processed", 0))
        
        return {
            "success": True,
            "operation": "buyer_profile_sync",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error syncing buyer profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/metrics", response_model=Dict[str, Any])
async def get_performance_metrics(
    days: int = Query(7, description="Days to analyze", ge=1, le=90),
    session = Depends(get_db_session)
):
    """
    Get matching performance metrics and statistics.
    
    - **days**: Number of days to analyze (1-90)
    """
    try:
        metrics = await get_matching_performance_metrics(days)
        
        return {
            "success": True,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Comprehensive health check of the buyer matchmaker system.
    """
    try:
        # Initialize agent
        agent = BuyerMatchmakerAgent()
        await agent.initialize()
        
        health_data = await agent.execute({
            "operation": "health_check"
        })
        
        return health_data
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "agent_status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.post("/setup/schemas", response_model=Dict[str, Any])
async def setup_schemas():
    """
    Setup Weaviate vector database schemas for matching operations.
    This should be run once during initial deployment.
    """
    try:
        result = await setup_vector_schemas()
        
        logger.info("Vector database schemas setup completed via API")
        
        return {
            "success": True,
            "operation": "schema_setup",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error setting up schemas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buyers/{buyer_id}/alerts", response_model=Dict[str, Any])
async def get_buyer_alerts(
    buyer_id: str = Path(..., description="Buyer UUID"),
    session = Depends(get_db_session)
):
    """
    Get pending alerts for a buyer.
    
    - **buyer_id**: UUID of the buyer
    """
    try:
        from reagent_sydney.core.cache.redis_client import get_cache_manager
        
        cache_manager = get_cache_manager()
        
        # Get recent alerts
        alert_key = f"buyer_alerts:{buyer_id}:{datetime.utcnow().strftime('%Y%m%d%H')}"
        alerts = await cache_manager.get(alert_key)
        
        if not alerts:
            return {
                "success": True,
                "buyer_id": buyer_id,
                "alerts_count": 0,
                "alerts": []
            }
        
        return {
            "success": True,
            "buyer_id": buyer_id,
            "alerts_count": len(alerts.get("matches", [])),
            "alerts": alerts
        }
        
    except Exception as e:
        logger.error(f"Error getting alerts for buyer {buyer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/generate", response_model=Dict[str, Any])
async def generate_buyer_alerts(
    buyer_ids: Optional[List[str]] = Body(None, description="Specific buyer IDs"),
    alert_type: str = Body("new_matches", description="Type of alert to generate"),
    session = Depends(get_db_session)
):
    """
    Generate alerts for buyers about new matching properties.
    
    - **buyer_ids**: Optional list of specific buyer IDs
    - **alert_type**: Type of alert (new_matches, price_changes, etc.)
    """
    try:
        from reagent_sydney.agents.buyer_matchmaker.tools import BuyerAlertGenerationTool
        
        tool = BuyerAlertGenerationTool()
        
        if buyer_ids:
            results = []
            for buyer_id in buyer_ids:
                result = await tool.run(buyer_id, alert_type)
                results.append({"buyer_id": buyer_id, "result": result})
            
            return {
                "success": True,
                "operation": "generate_alerts",
                "alert_type": alert_type,
                "results": results
            }
        else:
            result = await tool.run(None, alert_type)
            return {
                "success": True,
                "operation": "generate_alerts",
                "alert_type": alert_type,
                "result": result
            }
        
    except Exception as e:
        logger.error(f"Error generating alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))