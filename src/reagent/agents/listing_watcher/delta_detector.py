"""
ReAgent Sydney - Property Delta Detection Service

Efficient delta detection for property listings to identify new listings
and changes to existing properties.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from decimal import Decimal
import structlog

from src.core.database.engine import get_db_session
from src.core.cache.redis_client import get_cache_manager
from src.data.models.property_models import Property


logger = structlog.get_logger(__name__)


class PropertyDeltaDetector:
    """
    High-performance delta detection service for property listings.
    
    Features:
    - Redis-based caching for fast lookups
    - Hash-based change detection
    - Detailed change tracking
    - Batch processing support
    """
    
    # Fields to monitor for changes
    CHANGE_TRACKING_FIELDS = [
        "price", "price_display", "title", "description", "listing_status",
        "bedrooms", "bathrooms", "car_spaces", "features", "image_urls",
        "auction_date", "agent_info"
    ]
    
    # Fields that should trigger immediate notifications
    CRITICAL_CHANGE_FIELDS = [
        "price", "listing_status", "auction_date"
    ]
    
    def __init__(self, cache_ttl: int = 86400 * 7):  # 1 week
        """
        Initialize delta detector.
        
        Args:
            cache_ttl: Cache TTL in seconds (default 1 week)
        """
        self.cache_ttl = cache_ttl
        self.cache_manager = get_cache_manager()
        
        self.cache_keys = {
            "listing_hash": "delta_detector:listing_hash:{listing_id}",
            "listing_data": "delta_detector:listing_data:{listing_id}",
            "known_listings": "delta_detector:known_listings",
            "last_scan": "delta_detector:last_scan"
        }
    
    async def initialize(self) -> None:
        """Initialize the delta detector."""
        try:
            # Load known listings from database into cache
            await self._rebuild_listing_cache()
            
            logger.info("Delta detector initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize delta detector: {e}")
            raise
    
    async def detect_changes(
        self, 
        listing_id: str, 
        current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect changes in a property listing.
        
        Args:
            listing_id: Unique listing identifier
            current_data: Current property data
            
        Returns:
            Delta detection result with change details
        """
        try:
            # Check if this is a new listing
            is_new = not await self._is_known_listing(listing_id)
            
            if is_new:
                # Cache the new listing
                await self._cache_listing_data(listing_id, current_data)
                
                return {
                    "is_new": True,
                    "has_changes": False,
                    "changes": {},
                    "listing_id": listing_id,
                    "detected_at": datetime.utcnow().isoformat()
                }
            
            # Get cached data for comparison
            cached_data = await self._get_cached_listing_data(listing_id)
            
            if not cached_data:
                # Treat as new if no cached data
                await self._cache_listing_data(listing_id, current_data)
                return {
                    "is_new": True,
                    "has_changes": False,
                    "changes": {},
                    "listing_id": listing_id,
                    "detected_at": datetime.utcnow().isoformat()
                }
            
            # Detect changes
            changes = self._compare_listing_data(cached_data, current_data)
            has_changes = len(changes) > 0
            
            if has_changes:
                # Update cache with new data
                await self._cache_listing_data(listing_id, current_data)
                
                # Check for critical changes
                has_critical_changes = any(
                    field in changes for field in self.CRITICAL_CHANGE_FIELDS
                )
                
                logger.info(
                    "Property changes detected",
                    listing_id=listing_id,
                    changes=list(changes.keys()),
                    critical=has_critical_changes
                )
            
            return {
                "is_new": False,
                "has_changes": has_changes,
                "changes": changes,
                "has_critical_changes": has_changes and has_critical_changes,
                "listing_id": listing_id,
                "detected_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(
                "Delta detection failed",
                listing_id=listing_id,
                error=str(e)
            )
            # Return safe default
            return {
                "is_new": False,
                "has_changes": False,
                "changes": {},
                "error": str(e),
                "listing_id": listing_id,
                "detected_at": datetime.utcnow().isoformat()
            }
    
    async def batch_detect_changes(
        self, 
        listings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Batch process multiple listings for delta detection.
        
        Args:
            listings: List of property data dictionaries
            
        Returns:
            List of delta detection results
        """
        results = []
        
        # Pre-fetch all cached data in a single operation
        listing_ids = [listing.get("listing_id") for listing in listings]
        cached_data_batch = await self._batch_get_cached_data(listing_ids)
        
        for listing in listings:
            listing_id = listing.get("listing_id")
            if not listing_id:
                continue
            
            cached_data = cached_data_batch.get(listing_id)
            
            # Process delta detection
            if not cached_data:
                # New listing
                await self._cache_listing_data(listing_id, listing)
                result = {
                    "is_new": True,
                    "has_changes": False,
                    "changes": {},
                    "listing_id": listing_id,
                    "detected_at": datetime.utcnow().isoformat()
                }
            else:
                # Check for changes
                changes = self._compare_listing_data(cached_data, listing)
                has_changes = len(changes) > 0
                
                if has_changes:
                    await self._cache_listing_data(listing_id, listing)
                
                result = {
                    "is_new": False,
                    "has_changes": has_changes,
                    "changes": changes,
                    "listing_id": listing_id,
                    "detected_at": datetime.utcnow().isoformat()
                }
            
            results.append(result)
        
        logger.info(
            "Batch delta detection completed",
            total_listings=len(listings),
            new_listings=sum(1 for r in results if r["is_new"]),
            changed_listings=sum(1 for r in results if r["has_changes"])
        )
        
        return results
    
    def _compare_listing_data(
        self, 
        cached_data: Dict[str, Any], 
        current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare cached and current listing data to detect changes.
        
        Args:
            cached_data: Previously cached listing data
            current_data: Current listing data
            
        Returns:
            Dictionary of detected changes
        """
        changes = {}
        
        for field in self.CHANGE_TRACKING_FIELDS:
            cached_value = cached_data.get(field)
            current_value = current_data.get(field)
            
            # Handle None values
            if cached_value is None and current_value is None:
                continue
            
            # Convert Decimal to string for comparison
            if isinstance(cached_value, Decimal):
                cached_value = str(cached_value)
            if isinstance(current_value, Decimal):
                current_value = str(current_value)
            
            # Handle list comparisons
            if isinstance(cached_value, list) and isinstance(current_value, list):
                if set(cached_value) != set(current_value):
                    changes[field] = {
                        "old_value": cached_value,
                        "new_value": current_value,
                        "change_type": "list_modification"
                    }
            
            # Handle other value types
            elif cached_value != current_value:
                changes[field] = {
                    "old_value": cached_value,
                    "new_value": current_value,
                    "change_type": self._get_change_type(cached_value, current_value)
                }
        
        return changes
    
    def _get_change_type(self, old_value: Any, new_value: Any) -> str:
        """Determine the type of change that occurred."""
        if old_value is None:
            return "addition"
        elif new_value is None:
            return "removal"
        elif isinstance(old_value, (int, float, Decimal)) and isinstance(new_value, (int, float, Decimal)):
            return "price_increase" if float(new_value) > float(old_value) else "price_decrease"
        else:
            return "modification"
    
    async def _is_known_listing(self, listing_id: str) -> bool:
        """Check if a listing is already known."""
        known_listings = await self.cache_manager.get(
            self.cache_keys["known_listings"]
        ) or set()
        
        return listing_id in known_listings
    
    async def _cache_listing_data(
        self, 
        listing_id: str, 
        listing_data: Dict[str, Any]
    ) -> None:
        """Cache listing data and hash for delta detection."""
        # Create a hash of the tracking fields
        tracking_data = {
            field: listing_data.get(field) 
            for field in self.CHANGE_TRACKING_FIELDS
        }
        
        # Convert to JSON string for hashing
        tracking_json = json.dumps(tracking_data, sort_keys=True, default=str)
        data_hash = hashlib.sha256(tracking_json.encode()).hexdigest()
        
        # Cache the hash
        await self.cache_manager.set(
            self.cache_keys["listing_hash"].format(listing_id=listing_id),
            data_hash,
            ttl=self.cache_ttl
        )
        
        # Cache the data
        await self.cache_manager.set(
            self.cache_keys["listing_data"].format(listing_id=listing_id),
            tracking_data,
            ttl=self.cache_ttl
        )
        
        # Add to known listings set
        known_listings = await self.cache_manager.get(
            self.cache_keys["known_listings"]
        ) or set()
        
        known_listings.add(listing_id)
        
        await self.cache_manager.set(
            self.cache_keys["known_listings"],
            known_listings,
            ttl=self.cache_ttl
        )
    
    async def _get_cached_listing_data(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Get cached listing data."""
        return await self.cache_manager.get(
            self.cache_keys["listing_data"].format(listing_id=listing_id)
        )
    
    async def _batch_get_cached_data(
        self, 
        listing_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Batch get cached data for multiple listings."""
        cache_keys = [
            self.cache_keys["listing_data"].format(listing_id=listing_id)
            for listing_id in listing_ids
        ]
        
        # Use Redis pipeline for batch get
        cached_values = await self.cache_manager.mget(cache_keys)
        
        result = {}
        for i, listing_id in enumerate(listing_ids):
            if cached_values[i]:
                result[listing_id] = cached_values[i]
        
        return result
    
    async def _rebuild_listing_cache(self) -> None:
        """Rebuild the listing cache from database."""
        try:
            async with get_db_session() as session:
                # Get all active listings
                result = await session.execute(
                    """
                    SELECT listing_id, title, price, price_display, listing_status,
                           bedrooms, bathrooms, car_spaces, features, image_urls,
                           auction_date, updated_at
                    FROM properties 
                    WHERE listing_status = 'active'
                      AND deleted_at IS NULL
                    """
                )
                
                properties = result.fetchall()
                known_listings = set()
                
                for prop in properties:
                    listing_id = prop.listing_id
                    known_listings.add(listing_id)
                    
                    # Create tracking data
                    tracking_data = {
                        field: getattr(prop, field, None)
                        for field in self.CHANGE_TRACKING_FIELDS
                        if hasattr(prop, field)
                    }
                    
                    # Cache the data
                    await self.cache_manager.set(
                        self.cache_keys["listing_data"].format(listing_id=listing_id),
                        tracking_data,
                        ttl=self.cache_ttl
                    )
                
                # Cache known listings set
                await self.cache_manager.set(
                    self.cache_keys["known_listings"],
                    known_listings,
                    ttl=self.cache_ttl
                )
                
                logger.info(
                    "Listing cache rebuilt",
                    cached_listings=len(known_listings)
                )
                
        except Exception as e:
            logger.error(f"Failed to rebuild listing cache: {e}")
            raise
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get delta detector statistics."""
        try:
            known_listings = await self.cache_manager.get(
                self.cache_keys["known_listings"]
            ) or set()
            
            last_scan = await self.cache_manager.get(
                self.cache_keys["last_scan"]
            )
            
            return {
                "known_listings_count": len(known_listings),
                "last_scan_time": last_scan,
                "cache_ttl_seconds": self.cache_ttl,
                "tracked_fields": self.CHANGE_TRACKING_FIELDS,
                "critical_fields": self.CRITICAL_CHANGE_FIELDS
            }
            
        except Exception as e:
            logger.error(f"Failed to get delta detector statistics: {e}")
            return {
                "error": str(e),
                "status": "unhealthy"
            }
    
    async def clear_cache(self) -> None:
        """Clear all delta detector caches."""
        try:
            # Clear known listings
            await self.cache_manager.delete(self.cache_keys["known_listings"])
            
            # Clear all listing data (requires pattern matching)
            pattern = self.cache_keys["listing_data"].format(listing_id="*")
            keys = await self.cache_manager.keys(pattern)
            
            if keys:
                await self.cache_manager.delete(*keys)
            
            # Clear hash data
            pattern = self.cache_keys["listing_hash"].format(listing_id="*")
            keys = await self.cache_manager.keys(pattern)
            
            if keys:
                await self.cache_manager.delete(*keys)
            
            logger.info("Delta detector cache cleared")
            
        except Exception as e:
            logger.error(f"Failed to clear delta detector cache: {e}")
            raise