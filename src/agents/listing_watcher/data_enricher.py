"""
ReAgent Sydney - Property Data Enrichment Service

Enriches property listing data with additional information, geocoding,
market analysis, and feature extraction.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import structlog

from reagent_sydney.core.cache.redis_client import get_cache_manager
from reagent_sydney.config.settings import get_settings
from reagent_sydney.utils.validation import clean_property_description


logger = structlog.get_logger(__name__)


class PropertyDataEnricher:
    """
    Advanced property data enrichment service.
    
    Features:
    - Address standardization and geocoding
    - Feature extraction from descriptions
    - Market position analysis
    - Image and media processing
    - Search keyword generation
    """
    
    # Common property features to extract from descriptions
    PROPERTY_FEATURES = {
        # Parking
        "garage", "carport", "car_space", "parking", "off_street_parking",
        "secure_parking", "underground_parking", "tandem_parking",
        
        # Outdoor
        "balcony", "terrace", "courtyard", "garden", "pool", "spa", "deck",
        "entertaining_area", "outdoor_living", "alfresco", "bbq_area",
        
        # Interior
        "fireplace", "air_conditioning", "ducted_heating", "split_system",
        "built_in_robes", "walk_in_robe", "ensuite", "powder_room",
        "study", "office", "rumpus", "family_room", "formal_dining",
        
        # Security
        "security_system", "alarm", "intercom", "secure_building",
        "gated_community", "security_parking",
        
        # Views
        "city_views", "water_views", "harbour_views", "mountain_views",
        "park_views", "garden_views", "district_views",
        
        # Building features
        "lift", "elevator", "concierge", "gym", "swimming_pool",
        "tennis_court", "childrens_playground", "rooftop_terrace"
    }
    
    # Sydney suburb quality mapping (simplified)
    SUBURB_QUALITY_INDICATORS = {
        "premium": {
            "double_bay", "point_piper", "bellevue_hill", "woollahra",
            "mosman", "neutral_bay", "cremorne", "paddington", "surry_hills"
        },
        "high": {
            "bondi", "coogee", "manly", "chatswood", "north_sydney",
            "balmain", "leichhardt", "newtown", "glebe", "rozelle"
        },
        "medium": {
            "parramatta", "ryde", "hornsby", "bankstown", "liverpool",
            "penrith", "blacktown", "campbelltown", "sutherland"
        },
        "emerging": {
            "redfern", "waterloo", "zetland", "green_square", "alexandria",
            "marrickville", "st_peters", "tempe", "mascot"
        }
    }
    
    def __init__(self, cache_ttl: int = 86400):  # 24 hours
        """Initialize the data enricher."""
        self.cache_ttl = cache_ttl
        self.cache_manager = get_cache_manager()
        self.settings = get_settings()
        
        # Compile regex patterns for feature extraction
        self._compile_feature_patterns()
    
    async def initialize(self) -> None:
        """Initialize the data enricher."""
        try:
            logger.info("Property data enricher initialized")
        except Exception as e:
            logger.error(f"Failed to initialize data enricher: {e}")
            raise
    
    async def enrich_property_data(
        self, 
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enrich property data with additional information.
        
        Args:
            property_data: Raw property data
            
        Returns:
            Enriched property data
        """
        enriched_data = property_data.copy()
        
        try:
            # Clean and standardize description
            if enriched_data.get("description"):
                enriched_data["description"] = clean_property_description(
                    enriched_data["description"]
                )
            
            # Extract features from description
            extracted_features = await self._extract_features_from_description(
                enriched_data.get("description", ""),
                enriched_data.get("title", "")
            )
            
            # Merge with existing features
            existing_features = enriched_data.get("features", []) or []
            all_features = list(set(existing_features + extracted_features))
            enriched_data["features"] = all_features
            
            # Standardize address
            enriched_data = await self._standardize_address(enriched_data)
            
            # Generate search keywords
            enriched_data["search_keywords"] = self._generate_search_keywords(
                enriched_data
            )
            
            # Calculate market metrics
            enriched_data = await self._calculate_market_metrics(enriched_data)
            
            # Add suburb quality indicator
            enriched_data["suburb_quality"] = self._get_suburb_quality(
                enriched_data.get("suburb", "")
            )
            
            # Calculate days on market estimate
            if enriched_data.get("first_listed_date"):
                enriched_data["days_on_market"] = self._calculate_days_on_market(
                    enriched_data["first_listed_date"]
                )
            
            # Validate coordinates and get nearby amenities
            if enriched_data.get("latitude") and enriched_data.get("longitude"):
                enriched_data = await self._enrich_location_data(enriched_data)
            
            logger.debug(
                "Property data enriched",
                listing_id=enriched_data.get("listing_id"),
                features_count=len(all_features),
                keywords_count=len(enriched_data.get("search_keywords", []))
            )
            
            return enriched_data
            
        except Exception as e:
            logger.error(
                "Property data enrichment failed",
                listing_id=property_data.get("listing_id"),
                error=str(e)
            )
            # Return original data if enrichment fails
            return property_data
    
    async def _extract_features_from_description(
        self, 
        description: str, 
        title: str
    ) -> List[str]:
        """Extract property features from description and title text."""
        features = []
        combined_text = f"{title} {description}".lower()
        
        # Use compiled regex patterns for feature detection
        for feature, pattern in self.feature_patterns.items():
            if pattern.search(combined_text):
                features.append(feature.replace("_", " ").title())
        
        # Extract specific numeric features
        features.extend(self._extract_numeric_features(combined_text))
        
        # Extract view features
        features.extend(self._extract_view_features(combined_text))
        
        return list(set(features))  # Remove duplicates
    
    def _extract_numeric_features(self, text: str) -> List[str]:
        """Extract numeric features like room counts."""
        features = []
        
        # Car spaces
        car_matches = re.findall(r'(\d+)\s*car\s*(?:space|park|garage)', text)
        if car_matches:
            count = max(int(match) for match in car_matches)
            if count > 1:
                features.append(f"{count} Car Spaces")
        
        # Study/office rooms
        if re.search(r'study|office|home\s+office', text):
            features.append("Study/Office")
        
        # Multiple living areas
        living_areas = len(re.findall(r'living|lounge|family\s+room|rumpus', text))
        if living_areas > 1:
            features.append("Multiple Living Areas")
        
        return features
    
    def _extract_view_features(self, text: str) -> List[str]:
        """Extract view-related features."""
        features = []
        
        view_types = {
            "city": ["city", "cbd", "skyline"],
            "water": ["water", "harbour", "ocean", "beach", "bay"],
            "mountain": ["mountain", "hills", "blue mountains"],
            "park": ["park", "reserve", "garden", "green"]
        }
        
        for view_name, keywords in view_types.items():
            if any(f"{keyword}" in text and "view" in text for keyword in keywords):
                features.append(f"{view_name.title()} Views")
        
        return features
    
    async def _standardize_address(
        self, 
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Standardize and validate address information."""
        address = property_data.get("address_line_1", "")
        suburb = property_data.get("suburb", "")
        postcode = property_data.get("postcode", "")
        
        # Clean address components
        if address:
            # Remove unit numbers from main address for consistency
            address = re.sub(r'^(unit|u)\s*\d+[a-z]?\s*[/,]?\s*', '', address, flags=re.IGNORECASE)
            address = address.strip()
            property_data["address_line_1"] = address
        
        if suburb:
            # Standardize suburb name
            suburb = suburb.lower().replace(" ", "_")
            suburb = re.sub(r'[^a-z_]', '', suburb)
            property_data["suburb_normalized"] = suburb
        
        return property_data
    
    def _generate_search_keywords(self, property_data: Dict[str, Any]) -> List[str]:
        """Generate search optimization keywords."""
        keywords = []
        
        # Location keywords
        if property_data.get("suburb"):
            suburb = property_data["suburb"].lower()
            keywords.extend([
                suburb,
                f"{suburb}_property",
                f"{suburb}_real_estate",
                f"property_in_{suburb}"
            ])
        
        if property_data.get("postcode"):
            postcode = property_data["postcode"]
            keywords.extend([
                postcode,
                f"property_{postcode}",
                f"real_estate_{postcode}"
            ])
        
        # Property type keywords
        if property_data.get("property_type"):
            prop_type = property_data["property_type"].lower()
            keywords.extend([
                prop_type,
                f"{prop_type}_for_sale",
                f"{prop_type}_sydney"
            ])
        
        # Feature keywords
        features = property_data.get("features", [])
        for feature in features:
            feature_key = feature.lower().replace(" ", "_")
            keywords.append(feature_key)
        
        # Room configuration keywords
        bedrooms = property_data.get("bedrooms")
        bathrooms = property_data.get("bathrooms")
        
        if bedrooms and bathrooms:
            keywords.append(f"{bedrooms}bed_{bathrooms}bath")
            keywords.append(f"{bedrooms}br_{bathrooms}ba")
        
        # Price range keywords
        price = property_data.get("price")
        if price and isinstance(price, (int, float, Decimal)):
            price_val = float(price)
            if price_val < 500000:
                keywords.append("affordable")
            elif price_val < 1000000:
                keywords.append("mid_range")
            elif price_val < 2000000:
                keywords.append("premium")
            else:
                keywords.append("luxury")
        
        return list(set(keywords))  # Remove duplicates
    
    async def _calculate_market_metrics(
        self, 
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate market positioning metrics."""
        # Price per square meter
        if property_data.get("price") and property_data.get("building_size"):
            price = float(property_data["price"])
            size = float(property_data["building_size"])
            if size > 0:
                property_data["price_per_sqm"] = round(price / size, 2)
        
        # Estimate time to sell based on property characteristics
        property_data["estimated_time_to_sell"] = self._estimate_time_to_sell(
            property_data
        )
        
        return property_data
    
    def _estimate_time_to_sell(self, property_data: Dict[str, Any]) -> int:
        """Estimate time to sell in days based on property characteristics."""
        base_days = 45  # Base estimate
        
        # Adjust based on property type
        prop_type = property_data.get("property_type", "").lower()
        if prop_type in ["house", "terrace"]:
            base_days += 10
        elif prop_type in ["unit", "apartment"]:
            base_days -= 5
        
        # Adjust based on price range
        price = property_data.get("price")
        if price:
            price_val = float(price)
            if price_val > 2000000:  # Luxury market
                base_days += 20
            elif price_val < 500000:  # Affordable market
                base_days -= 10
        
        # Adjust based on suburb quality
        suburb_quality = property_data.get("suburb_quality", "medium")
        if suburb_quality == "premium":
            base_days += 15
        elif suburb_quality == "emerging":
            base_days -= 5
        
        # Adjust based on features
        features = property_data.get("features", [])
        high_value_features = [
            "pool", "garage", "city views", "water views", "air conditioning"
        ]
        
        feature_score = sum(
            1 for feature in features 
            if any(hvf in feature.lower() for hvf in high_value_features)
        )
        base_days -= feature_score * 3
        
        return max(base_days, 14)  # Minimum 2 weeks
    
    def _get_suburb_quality(self, suburb: str) -> str:
        """Get suburb quality indicator."""
        if not suburb:
            return "unknown"
        
        suburb_normalized = suburb.lower().replace(" ", "_")
        
        for quality, suburbs in self.SUBURB_QUALITY_INDICATORS.items():
            if suburb_normalized in suburbs:
                return quality
        
        return "medium"  # Default
    
    def _calculate_days_on_market(self, first_listed_date: datetime) -> int:
        """Calculate days on market."""
        if isinstance(first_listed_date, str):
            try:
                first_listed_date = datetime.fromisoformat(
                    first_listed_date.replace("Z", "+00:00")
                )
            except:
                return 0
        
        if not isinstance(first_listed_date, datetime):
            return 0
        
        days = (datetime.utcnow() - first_listed_date).days
        return max(days, 0)
    
    async def _enrich_location_data(
        self, 
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrich data with location-based information."""
        lat = property_data.get("latitude")
        lng = property_data.get("longitude")
        
        if not lat or not lng:
            return property_data
        
        # Calculate distance to CBD (Sydney CBD: -33.8688, 151.2093)
        cbd_lat, cbd_lng = -33.8688, 151.2093
        distance_to_cbd = self._calculate_distance_km(lat, lng, cbd_lat, cbd_lng)
        property_data["distance_to_cbd_km"] = round(distance_to_cbd, 1)
        
        # Add location convenience score
        if distance_to_cbd <= 5:
            property_data["location_convenience"] = "excellent"
        elif distance_to_cbd <= 15:
            property_data["location_convenience"] = "good"
        elif distance_to_cbd <= 30:
            property_data["location_convenience"] = "moderate"
        else:
            property_data["location_convenience"] = "fair"
        
        return property_data
    
    def _calculate_distance_km(
        self, 
        lat1: float, lng1: float, 
        lat2: float, lng2: float
    ) -> float:
        """Calculate distance between two points in kilometers (Haversine formula)."""
        import math
        
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lng / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _compile_feature_patterns(self) -> None:
        """Compile regex patterns for feature extraction."""
        self.feature_patterns = {}
        
        for feature in self.PROPERTY_FEATURES:
            # Create variations of the feature name
            variations = [
                feature,
                feature.replace("_", " "),
                feature.replace("_", "-"),
                feature.replace("_", "")
            ]
            
            # Create regex pattern
            pattern = r'\b(?:' + '|'.join(re.escape(var) for var in variations) + r')\b'
            self.feature_patterns[feature] = re.compile(pattern, re.IGNORECASE)
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get data enricher statistics."""
        return {
            "tracked_features": len(self.PROPERTY_FEATURES),
            "suburb_quality_levels": list(self.SUBURB_QUALITY_INDICATORS.keys()),
            "cache_ttl_seconds": self.cache_ttl,
            "status": "active"
        }