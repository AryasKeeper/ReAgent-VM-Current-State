"""
ReAgent - Vector Database Service

This service manages all interactions with the Weaviate vector database,
including schema setup and data synchronization from the primary database.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import select, and_, or_, update
from sqlalchemy.orm import selectinload

from reagent.core.database.dependencies import get_db_session
from reagent.core.vector_db import get_weaviate_client, PropertySchema, BuyerProfileSchema
from reagent.core.vector_db.embeddings import PropertyVectorizer, BuyerProfileVectorizer
from reagent.data.models.property_models import Property
from reagent.data.models.buyer_models import Buyer
from reagent.utils.logging import get_logger


class VectorDBService:
    """Manages vector database operations for properties and buyer profiles."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.property_vectorizer = PropertyVectorizer()
        self.buyer_vectorizer = BuyerProfileVectorizer()

    async def setup_schemas(self) -> Dict[str, bool]:
        """Set up Weaviate schemas for properties and buyer profiles."""
        try:
            weaviate_client = await get_weaviate_client()
            
            from reagent.core.vector_db.schemas import PropertyMatchSchema
            
            schemas = {
                "Property": PropertySchema.get_schema(),
                "BuyerProfile": BuyerProfileSchema.get_schema(),
                "PropertyMatch": PropertyMatchSchema.get_schema(),
            }
            
            results = {}
            for name, schema in schemas.items():
                results[name] = await weaviate_client.create_schema(schema)

            self.logger.info("Vector database schemas setup completed", results=results)
            return results

        except Exception as e:
            self.logger.error("Failed to setup vector database schemas", error=str(e))
            return {"error": str(e)}

    async def sync_properties_to_vector_db(
        self, batch_size: int = 100, force_update: bool = False
    ) -> Dict[str, Any]:
        """Sync properties from PostgreSQL to Weaviate vector database."""
        try:
            weaviate_client = await get_weaviate_client()
            properties_to_sync = await self._get_properties_for_sync(force_update)

            if not properties_to_sync:
                return {"status": "success", "message": "No properties need syncing", "properties_processed": 0}

            total_properties = len(properties_to_sync)
            processed_count = 0
            errors = []

            for i in range(0, total_properties, batch_size):
                batch = properties_to_sync[i:i + batch_size]
                try:
                    batch_result = await self._process_property_batch(batch, weaviate_client)
                    processed_count += batch_result["processed"]
                    errors.extend(batch_result["errors"])
                    self.logger.info(f"Processed batch {i//batch_size + 1}", processed=batch_result['processed'], total=len(batch))
                except Exception as e:
                    error_msg = f"Batch {i//batch_size + 1} failed: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)

            return {
                "status": "completed",
                "properties_processed": processed_count,
                "total_properties": total_properties,
                "errors": errors,
                "success_rate": processed_count / total_properties if total_properties > 0 else 0,
            }
        except Exception as e:
            self.logger.error("Property sync failed", error=str(e))
            return {"status": "failed", "error": str(e), "properties_processed": 0}

    async def _get_properties_for_sync(self, force_update: bool = False) -> List[Property]:
        """Get properties that need to be synced to the vector database."""
        async with get_db_session() as session:
            query = select(
                Property.listing_id,
                Property.title,
                Property.description,
                Property.property_type,
                Property.suburb,
                Property.postcode,
                Property.state,
                Property.bedrooms,
                Property.bathrooms,
                Property.car_spaces,
                Property.price,
                Property.price_display,
                Property.land_size,
                Property.building_size,
                Property.listing_status,
                Property.listing_type,
                Property.features,
                Property.latitude,
                Property.longitude,
                Property.first_listed_date,
                Property.days_on_market,
                Property.source,
                Property.amenities,
                Property.updated_at,
                Property.embedding_vector
            ).options(
                selectinload(Property.agent),
                selectinload(Property.agency),
                selectinload(Property.market_metrics),
            )

            conditions = [Property.listing_status == "active"]
            if not force_update:
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                conditions.append(or_(Property.updated_at >= cutoff_time, Property.embedding_vector.is_(None)))

            result = await session.execute(query.where(and_(*conditions)))
            return result.scalars().all()

    async def _process_property_batch(self, properties: List[Property], weaviate_client) -> Dict[str, Any]:
        """Process a batch of properties for vector storage."""
        processed = 0
        errors = []
        batch_objects = []
        batch_vectors = []

        for prop in properties:
            try:
                features = self.property_vectorizer.extract_features(prop)
                vector, metadata = await self.property_vectorizer.generate_embedding(features)
                object_data = self._prepare_property_object_data(prop, features, metadata)
                batch_objects.append(object_data)
                batch_vectors.append(vector)
            except Exception as e:
                error_msg = f"Failed to process property {prop.listing_id}: {str(e)}"
                errors.append(error_msg)
                self.logger.error(error_msg)

        if batch_objects:
            try:
                inserted_ids = await weaviate_client.batch_insert_objects(
                    class_name="Property", objects=batch_objects, vectors=batch_vectors
                )
                processed = len(inserted_ids)
                await self._update_property_sync_timestamps([obj["listing_id"] for obj in batch_objects])
            except Exception as e:
                error_msg = f"Batch insert failed: {str(e)}"
                errors.append(error_msg)
                self.logger.error(error_msg)

        return {"processed": processed, "errors": errors}

    def _prepare_property_object_data(self, prop: Property, features: Any, metadata: Any) -> Dict[str, Any]:
        """Prepare property data for Weaviate storage."""
        return {
            "listing_id": prop.listing_id,
            "title": prop.title or "",
            "description": prop.description or "",
            "property_type": prop.property_type or "house",
            "suburb": prop.suburb or "",
            "postcode": prop.postcode or "",
            "state": prop.state or "NSW",
            "bedrooms": prop.bedrooms or 0,
            "bathrooms": prop.bathrooms or 0,
            "car_spaces": prop.car_spaces or 0,
            "price": float(prop.price or 0),
            "price_display": prop.price_display or "",
            "land_size": prop.land_size or 0,
            "building_size": prop.building_size or 0,
            "listing_status": prop.listing_status or "active",
            "listing_type": prop.listing_type or "sale",
            "features": prop.features or [],
            "latitude": float(prop.latitude or 0),
            "longitude": float(prop.longitude or 0),
            "first_listed_date": prop.first_listed_date.isoformat() if prop.first_listed_date else None,
            "days_on_market": prop.days_on_market or 0,
            "agent_name": prop.agent.full_name if prop.agent else "",
            "agency_name": prop.agency.name if prop.agency else "",
            "source": prop.source or "unknown",
            "amenities": prop.amenities or {},
            "market_context": features.market_context,
            "embedding_metadata": metadata.__dict__,
        }

    async def _update_property_sync_timestamps(self, listing_ids: List[str]) -> None:
        """Update property sync timestamps in PostgreSQL."""
        try:
            async with get_db_session() as session:
                await session.execute(
                    update(Property)
                    .where(Property.listing_id.in_(listing_ids))
                    .values(last_updated_source=datetime.utcnow())
                )
                await session.commit()
        except Exception as e:
            self.logger.error("Failed to update sync timestamps", error=str(e))

    async def sync_buyer_profiles_to_vector_db(self, buyer_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Sync buyer profiles to vector database."""
        try:
            weaviate_client = await get_weaviate_client()
            buyers_to_sync = await self._get_buyers_for_sync(buyer_ids)

            if not buyers_to_sync:
                return {"status": "success", "message": "No buyer profiles need syncing", "profiles_processed": 0}

            processed_count = 0
            errors = []

            for buyer in buyers_to_sync:
                try:
                    if not buyer.preferences:
                        continue
                    
                    features = self.buyer_vectorizer.extract_features(buyer, buyer.preferences)
                    vector, metadata = await self.buyer_vectorizer.generate_embedding(features)
                    object_data = self._prepare_buyer_object_data(buyer, features, metadata)

                    if await weaviate_client.insert_object(
                        class_name="BuyerProfile", properties=object_data, vector=vector, object_id=str(buyer.id)
                    ):
                        processed_count += 1
                except Exception as e:
                    error_msg = f"Failed to sync buyer {buyer.id}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)

            return {
                "status": "completed",
                "profiles_processed": processed_count,
                "total_buyers": len(buyers_to_sync),
                "errors": errors,
            }
        except Exception as e:
            self.logger.error("Buyer profile sync failed", error=str(e))
            return {"status": "failed", "error": str(e), "profiles_processed": 0}

    async def _get_buyers_for_sync(self, buyer_ids: Optional[List[str]] = None) -> List[Buyer]:
        """Get buyers that need vector profile sync."""
        async with get_db_session() as session:
            query = select(
                Buyer.id,
                Buyer.full_name,
                Buyer.buyer_type,
                Buyer.buying_urgency,
                Buyer.status,
                Buyer.created_at
            ).options(
                selectinload(Buyer.preferences),
                selectinload(Buyer.property_interactions),
                selectinload(Buyer.search_history),
            )
            if buyer_ids:
                query = query.where(Buyer.id.in_(buyer_ids))
            else:
                query = query.where(and_(Buyer.status == "active", Buyer.preferences.has()))
            
            result = await session.execute(query)
            return result.scalars().all()

    def _prepare_buyer_object_data(self, buyer: Buyer, features: Any, metadata: Any) -> Dict[str, Any]:
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
            "embedding_metadata": metadata.__dict__,
        }

# Global service instance
vector_db_service = VectorDBService()

# Convenience functions
async def setup_vector_schemas() -> Dict[str, bool]:
    """Setup Weaviate schemas for buyer matchmaker."""
    return await vector_db_service.setup_schemas()

async def sync_properties_to_vector_db(batch_size: int = 100, force_update: bool = False) -> Dict[str, Any]:
    """Sync properties to vector database."""
    return await vector_db_service.sync_properties_to_vector_db(batch_size, force_update)

async def sync_buyer_profiles_to_vector_db(buyer_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Sync buyer profiles to vector database."""
    return await vector_db_service.sync_buyer_profiles_to_vector_db(buyer_ids)
