"""
Buyer Matchmaker AU - Utility Functions

Helper functions for property synchronization, schema setup, and performance monitoring.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from reagent_sydney.core.database.dependencies import get_db_session
from reagent_sydney.core.vector_db import get_weaviate_client, PropertySchema, BuyerProfileSchema
from reagent_sydney.core.vector_db.embeddings import PropertyVectorizer, BuyerProfileVectorizer
from reagent_sydney.data.models.property_models import Property
from reagent_sydney.data.models.buyer_models import Buyer, PropertyMatch

import structlog


class VectorDBManager:
    """Manages vector database operations for the Buyer Matchmaker."""
    
    def __init__(self):
        self.logger = structlog.get_logger("vector_db_manager")
        self.property_vectorizer = PropertyVectorizer()
        self.buyer_vectorizer = BuyerProfileVectorizer()
    
    async def setup_schemas(self) -> Dict[str, bool]:
        """Set up Weaviate schemas for properties and buyer profiles."""
        
        try:
            weaviate_client = await get_weaviate_client()
            
            # Create Property schema
            property_schema = PropertySchema.get_schema()
            property_result = await weaviate_client.create_schema(property_schema)
            
            # Create BuyerProfile schema
            buyer_schema = BuyerProfileSchema.get_schema()
            buyer_result = await weaviate_client.create_schema(buyer_schema)
            
            # Create PropertyMatch schema (for match history)
            from reagent_sydney.core.vector_db.schemas import PropertyMatchSchema
            match_schema = PropertyMatchSchema.get_schema()
            match_result = await weaviate_client.create_schema(match_schema)
            
            results = {
                "Property": property_result,
                "BuyerProfile": buyer_result,
                "PropertyMatch": match_result
            }
            
            self.logger.info("Vector database schemas setup completed", results=results)
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to setup vector database schemas: {e}")
            return {"error": str(e)}
    
    async def sync_properties_to_vector_db(
        self, 
        batch_size: int = 100,
        force_update: bool = False
    ) -> Dict[str, Any]:
        """Sync properties from PostgreSQL to Weaviate vector database."""
        
        try:
            weaviate_client = await get_weaviate_client()
            
            # Get properties that need syncing
            properties_to_sync = await self._get_properties_for_sync(force_update)
            
            if not properties_to_sync:
                return {
                    "status": "success",
                    "message": "No properties need syncing",
                    "properties_processed": 0
                }
            
            total_properties = len(properties_to_sync)
            processed = 0
            errors = []
            
            # Process in batches
            for i in range(0, total_properties, batch_size):
                batch = properties_to_sync[i:i + batch_size]
                
                try:
                    batch_result = await self._process_property_batch(batch, weaviate_client)
                    processed += batch_result["processed"]
                    errors.extend(batch_result["errors"])
                    
                    self.logger.info(f"Processed batch {i//batch_size + 1}: {batch_result['processed']}/{len(batch)} properties")
                    
                except Exception as e:
                    error_msg = f"Batch {i//batch_size + 1} failed: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
            
            return {
                "status": "completed",
                "properties_processed": processed,
                "total_properties": total_properties,
                "errors": errors,
                "success_rate": processed / total_properties if total_properties > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Property sync failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "properties_processed": 0
            }
    
    async def _get_properties_for_sync(self, force_update: bool = False) -> List[Property]:
        """Get properties that need to be synced to vector database."""
        
        async with get_db_session() as session:
            query = select(Property).options(
                selectinload(Property.agent),
                selectinload(Property.agency),
                selectinload(Property.market_metrics)
            )
            
            # Filter conditions
            conditions = [Property.listing_status == "active"]
            
            if not force_update:
                # Only sync properties updated in last 24 hours or without vector sync
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                conditions.append(
                    or_(
                        Property.updated_at >= cutoff_time,
                        Property.embedding_vector.is_(None)
                    )
                )
            
            result = await session.execute(query.where(and_(*conditions)))
            return result.scalars().all()
    
    async def _process_property_batch(
        self, 
        properties: List[Property], 
        weaviate_client
    ) -> Dict[str, Any]:
        """Process a batch of properties for vector storage."""
        
        processed = 0
        errors = []
        
        # Prepare batch data
        batch_objects = []
        batch_vectors = []
        
        for property_obj in properties:
            try:
                # Extract features and generate embedding
                features = self.property_vectorizer.extract_features(property_obj)
                vector, metadata = await self.property_vectorizer.generate_embedding(features)
                
                # Prepare object data for Weaviate
                object_data = self._prepare_property_object_data(property_obj, features, metadata)
                
                batch_objects.append(object_data)
                batch_vectors.append(vector)
                
            except Exception as e:
                error_msg = f"Failed to process property {property_obj.listing_id}: {str(e)}"
                errors.append(error_msg)
                self.logger.error(error_msg)
        
        # Insert batch into Weaviate
        if batch_objects:
            try:
                inserted_ids = await weaviate_client.batch_insert_objects(
                    class_name="Property",
                    objects=batch_objects,
                    vectors=batch_vectors
                )
                processed = len(inserted_ids)
                
                # Update PostgreSQL with sync timestamp
                await self._update_property_sync_timestamps(
                    [obj["listing_id"] for obj in batch_objects]
                )
                
            except Exception as e:
                error_msg = f"Batch insert failed: {str(e)}"
                errors.append(error_msg)
                self.logger.error(error_msg)
        
        return {
            "processed": processed,
            "errors": errors
        }
    
    def _prepare_property_object_data(
        self, 
        property_obj: Property, 
        features: Any, 
        metadata: Any
    ) -> Dict[str, Any]:
        """Prepare property data for Weaviate storage."""
        
        return {
            "listing_id": property_obj.listing_id,
            "title": property_obj.title or "",
            "description": property_obj.description or "",
            "property_type": property_obj.property_type or "house",
            "suburb": property_obj.suburb or "",
            "postcode": property_obj.postcode or "",
            "state": property_obj.state or "NSW",
            "bedrooms": property_obj.bedrooms or 0,
            "bathrooms": property_obj.bathrooms or 0,
            "car_spaces": property_obj.car_spaces or 0,
            "price": float(property_obj.price or 0),
            "price_display": property_obj.price_display or "",
            "land_size": property_obj.land_size or 0,
            "building_size": property_obj.building_size or 0,
            "listing_status": property_obj.listing_status or "active",
            "listing_type": property_obj.listing_type or "sale",
            "features": property_obj.features or [],
            "latitude": float(property_obj.latitude or 0),
            "longitude": float(property_obj.longitude or 0),
            "first_listed_date": property_obj.first_listed_date.isoformat() if property_obj.first_listed_date else None,
            "days_on_market": property_obj.days_on_market or 0,
            "agent_name": property_obj.agent.full_name if property_obj.agent else "",
            "agency_name": property_obj.agency.name if property_obj.agency else "",
            "source": property_obj.source or "unknown",
            "amenities": property_obj.amenities or {},
            "market_context": features.market_context,
            "embedding_metadata": metadata.__dict__
        }
    
    async def _update_property_sync_timestamps(self, listing_ids: List[str]) -> None:
        """Update property sync timestamps in PostgreSQL."""
        
        try:
            async with get_db_session() as session:
                from sqlalchemy import update
                
                await session.execute(
                    update(Property)
                    .where(Property.listing_id.in_(listing_ids))
                    .values(last_updated_source=datetime.utcnow())
                )
                await session.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to update sync timestamps: {e}")
    
    async def sync_buyer_profiles_to_vector_db(
        self, 
        buyer_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Sync buyer profiles to vector database."""
        
        try:
            weaviate_client = await get_weaviate_client()
            
            # Get buyers to sync
            buyers_to_sync = await self._get_buyers_for_sync(buyer_ids)
            
            if not buyers_to_sync:
                return {
                    "status": "success",
                    "message": "No buyer profiles need syncing",
                    "profiles_processed": 0
                }
            
            processed = 0
            errors = []
            
            for buyer in buyers_to_sync:
                try:
                    if not buyer.preferences:
                        continue
                    
                    # Generate buyer embedding
                    features = self.buyer_vectorizer.extract_features(buyer, buyer.preferences)
                    vector, metadata = await self.buyer_vectorizer.generate_embedding(features)
                    
                    # Prepare object data
                    object_data = self._prepare_buyer_object_data(buyer, features, metadata)
                    
                    # Insert or update in Weaviate
                    success = await weaviate_client.insert_object(
                        class_name="BuyerProfile",
                        properties=object_data,
                        vector=vector,
                        object_id=str(buyer.id)
                    )
                    
                    if success:
                        processed += 1
                    
                except Exception as e:
                    error_msg = f"Failed to sync buyer {buyer.id}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
            
            return {
                "status": "completed",
                "profiles_processed": processed,
                "total_buyers": len(buyers_to_sync),
                "errors": errors
            }
            
        except Exception as e:
            self.logger.error(f"Buyer profile sync failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "profiles_processed": 0
            }
    
    async def _get_buyers_for_sync(self, buyer_ids: Optional[List[str]] = None) -> List[Buyer]:
        """Get buyers that need vector profile sync."""
        
        async with get_db_session() as session:
            query = select(Buyer).options(
                selectinload(Buyer.preferences),
                selectinload(Buyer.property_interactions),
                selectinload(Buyer.search_history)
            )
            
            if buyer_ids:
                query = query.where(Buyer.id.in_(buyer_ids))
            else:
                # Only active buyers with preferences
                query = query.where(
                    and_(
                        Buyer.status == "active",
                        Buyer.preferences.has()
                    )
                )
            
            result = await session.execute(query)
            return result.scalars().all()
    
    def _prepare_buyer_object_data(
        self, 
        buyer: Buyer, 
        features: Any, 
        metadata: Any
    ) -> Dict[str, Any]:
        """Prepare buyer data for Weaviate storage."""
        
        prefs = buyer.preferences
        
        return {
            "buyer_id": str(buyer.id),
            "full_name": buyer.full_name,
            "buyer_type": buyer.buyer_type or "individual",
            "buying_urgency": buyer.buying_urgency or "medium",
            "max_price": float(prefs.max_price or 0),
            "min_price": float(prefs.min_price or 0),
            "budget_flexibility": float(prefs.budget_flexibility or 0.1),
            "property_types": prefs.property_types or [],
            "preferred_suburbs": prefs.preferred_suburbs or [],
            "excluded_suburbs": prefs.excluded_suburbs or [],
            "preferred_postcodes": prefs.preferred_postcodes or [],
            "min_bedrooms": prefs.min_bedrooms or 0,
            "max_bedrooms": prefs.max_bedrooms or 10,
            "min_bathrooms": prefs.min_bathrooms or 0,
            "min_car_spaces": prefs.min_car_spaces or 0,
            "min_land_size": prefs.min_land_size or 0,
            "min_building_size": prefs.min_building_size or 0,
            "required_features": prefs.required_features or [],
            "preferred_features": prefs.preferred_features or [],
            "excluded_features": prefs.excluded_features or [],
            "max_commute_time": prefs.max_commute_time or 60,
            "rental_yield_target": float(prefs.rental_yield_target or 0),
            "capital_growth_expectation": prefs.capital_growth_expectation or "medium",
            "created_at": buyer.created_at.isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "behavioral_data": features.interaction_patterns,
            "preference_weights": features.preference_weights,
            "embedding_metadata": metadata.__dict__
        }


class MatchStorageManager:
    """Manages storage and retrieval of property matches."""
    
    def __init__(self):
        self.logger = structlog.get_logger("match_storage_manager")
    
    async def store_buyer_matches(
        self, 
        buyer_id: str, 
        matches: List[Any]
    ) -> Dict[str, Any]:
        """Store property matches for a buyer in the database."""
        
        try:
            async with get_db_session() as session:
                # Clear existing new matches for this buyer
                from sqlalchemy import update
                await session.execute(
                    update(PropertyMatch)
                    .where(
                        and_(
                            PropertyMatch.buyer_id == buyer_id,
                            PropertyMatch.status == "new"
                        )
                    )
                    .values(status="superseded")
                )
                
                # Create new match records
                new_matches = []
                for match in matches:
                    property_match = PropertyMatch(
                        buyer_id=UUID(buyer_id),
                        property_id=UUID(match.property_id),
                        match_score=match.match_score,
                        match_rank=match.match_rank,
                        match_reasons=match.match_reasons,
                        match_concerns=match.match_concerns,
                        match_explanation=match.match_explanation,
                        status="new",
                        first_presented_date=datetime.utcnow(),
                        price_assessment=match.price_assessment,
                        estimated_value=match.estimated_value,
                        scoring_details=match.scoring_details
                    )
                    new_matches.append(property_match)
                
                # Bulk insert new matches
                session.add_all(new_matches)
                await session.commit()
                
                self.logger.info(f"Stored {len(new_matches)} matches for buyer {buyer_id}")
                
                return {
                    "status": "success",
                    "matches_stored": len(new_matches),
                    "buyer_id": buyer_id
                }
                
        except Exception as e:
            self.logger.error(f"Failed to store matches for buyer {buyer_id}: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "matches_stored": 0
            }
    
    async def get_buyer_matches(
        self, 
        buyer_id: str, 
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[PropertyMatch]:
        """Retrieve stored matches for a buyer."""
        
        try:
            async with get_db_session() as session:
                query = select(PropertyMatch).options(
                    selectinload(PropertyMatch.property),
                    selectinload(PropertyMatch.buyer)
                ).where(PropertyMatch.buyer_id == buyer_id)
                
                if status:
                    query = query.where(PropertyMatch.status == status)
                
                query = query.order_by(
                    PropertyMatch.match_rank.asc(),
                    PropertyMatch.match_score.desc()
                ).limit(limit)
                
                result = await session.execute(query)
                return result.scalars().all()
                
        except Exception as e:
            self.logger.error(f"Failed to get matches for buyer {buyer_id}: {e}")
            return []
    
    async def update_match_status(
        self, 
        match_id: str, 
        status: str, 
        feedback: Optional[str] = None
    ) -> bool:
        """Update match status and feedback."""
        
        try:
            async with get_db_session() as session:
                from sqlalchemy import update
                
                update_values = {
                    "status": status,
                    "last_interaction_date": datetime.utcnow()
                }
                
                if feedback:
                    update_values["buyer_feedback"] = feedback
                
                await session.execute(
                    update(PropertyMatch)
                    .where(PropertyMatch.id == match_id)
                    .values(**update_values)
                )
                await session.commit()
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to update match {match_id}: {e}")
            return False


class PerformanceMonitor:
    """Monitors matching performance and provides metrics."""
    
    def __init__(self):
        self.logger = structlog.get_logger("performance_monitor")
    
    async def get_matching_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get matching performance metrics."""
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            async with get_db_session() as session:
                # Total matches generated
                total_matches_result = await session.execute(
                    select(func.count(PropertyMatch.id))
                    .where(PropertyMatch.created_at >= cutoff_date)
                )
                total_matches = total_matches_result.scalar()
                
                # Buyer engagement metrics
                engagement_result = await session.execute(
                    select(
                        func.count(PropertyMatch.id.distinct()).label("total_matches"),
                        func.count(func.nullif(PropertyMatch.buyer_feedback, None)).label("feedback_count"),
                        func.avg(PropertyMatch.match_score).label("avg_score")
                    )
                    .where(PropertyMatch.created_at >= cutoff_date)
                )
                engagement_data = engagement_result.first()
                
                # Status distribution
                status_result = await session.execute(
                    select(
                        PropertyMatch.status,
                        func.count(PropertyMatch.id)
                    )
                    .where(PropertyMatch.created_at >= cutoff_date)
                    .group_by(PropertyMatch.status)
                )
                status_distribution = {row[0]: row[1] for row in status_result.fetchall()}
                
                # Top performing matches
                top_matches_result = await session.execute(
                    select(PropertyMatch)
                    .options(
                        selectinload(PropertyMatch.buyer),
                        selectinload(PropertyMatch.property)
                    )
                    .where(
                        and_(
                            PropertyMatch.created_at >= cutoff_date,
                            PropertyMatch.match_score >= 0.8,
                            PropertyMatch.status.in_(["interested", "contacted"])
                        )
                    )
                    .order_by(PropertyMatch.match_score.desc())
                    .limit(10)
                )
                top_matches = top_matches_result.scalars().all()
                
                return {
                    "period_days": days,
                    "total_matches": total_matches,
                    "avg_match_score": float(engagement_data.avg_score or 0),
                    "feedback_rate": (engagement_data.feedback_count / max(engagement_data.total_matches, 1)) * 100,
                    "status_distribution": status_distribution,
                    "engagement_metrics": {
                        "interested_rate": (status_distribution.get("interested", 0) / max(total_matches, 1)) * 100,
                        "contacted_rate": (status_distribution.get("contacted", 0) / max(total_matches, 1)) * 100,
                        "not_interested_rate": (status_distribution.get("not_interested", 0) / max(total_matches, 1)) * 100
                    },
                    "top_matches_count": len(top_matches),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get matching metrics: {e}")
            return {"error": str(e)}
    
    async def get_buyer_satisfaction_metrics(self, buyer_id: Optional[str] = None) -> Dict[str, Any]:
        """Get buyer satisfaction metrics."""
        
        try:
            async with get_db_session() as session:
                query = select(PropertyMatch)
                
                if buyer_id:
                    query = query.where(PropertyMatch.buyer_id == buyer_id)
                
                # Get recent matches with feedback
                query = query.where(
                    and_(
                        PropertyMatch.created_at >= datetime.utcnow() - timedelta(days=30),
                        PropertyMatch.buyer_feedback.isnot(None)
                    )
                )
                
                result = await session.execute(query)
                matches_with_feedback = result.scalars().all()
                
                if not matches_with_feedback:
                    return {"message": "No feedback data available"}
                
                # Analyze sentiment of feedback
                positive_feedback = 0
                neutral_feedback = 0
                negative_feedback = 0
                
                for match in matches_with_feedback:
                    feedback = (match.buyer_feedback or "").lower()
                    
                    if any(word in feedback for word in ["love", "perfect", "interested", "great", "excellent"]):
                        positive_feedback += 1
                    elif any(word in feedback for word in ["no", "not interested", "pass", "terrible", "bad"]):
                        negative_feedback += 1
                    else:
                        neutral_feedback += 1
                
                total_feedback = len(matches_with_feedback)
                avg_score = sum(match.match_score for match in matches_with_feedback) / total_feedback
                
                return {
                    "total_feedback": total_feedback,
                    "positive_feedback": positive_feedback,
                    "neutral_feedback": neutral_feedback,
                    "negative_feedback": negative_feedback,
                    "satisfaction_rate": (positive_feedback / total_feedback) * 100,
                    "avg_match_score": float(avg_score),
                    "buyer_id": buyer_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get satisfaction metrics: {e}")
            return {"error": str(e)}


# Global utility instances
vector_db_manager = VectorDBManager()
match_storage_manager = MatchStorageManager()
performance_monitor = PerformanceMonitor()


# Convenience functions
async def setup_vector_schemas() -> Dict[str, bool]:
    """Setup Weaviate schemas for buyer matchmaker."""
    return await vector_db_manager.setup_schemas()


async def sync_properties_to_vector_db(batch_size: int = 100, force_update: bool = False) -> Dict[str, Any]:
    """Sync properties to vector database."""
    return await vector_db_manager.sync_properties_to_vector_db(batch_size, force_update)


async def sync_buyer_profiles_to_vector_db(buyer_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Sync buyer profiles to vector database."""
    return await vector_db_manager.sync_buyer_profiles_to_vector_db(buyer_ids)


async def store_buyer_matches(buyer_id: str, matches: List[Any]) -> Dict[str, Any]:
    """Store buyer matches in database."""
    return await match_storage_manager.store_buyer_matches(buyer_id, matches)


async def get_matching_performance_metrics(days: int = 7) -> Dict[str, Any]:
    """Get matching performance metrics."""
    return await performance_monitor.get_matching_metrics(days)