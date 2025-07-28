"""
Comparable Sales Analysis (CMA) Engine

Statistical analysis of recent sales to determine property valuation ranges
with confidence intervals and adjustment factors.
"""

import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal
import logging

from sqlalchemy import and_, func, text
from sqlalchemy.orm import Session

from reagent_sydney.core.database.dependencies import get_db_session
from reagent_sydney.data.models.property_models import Property, PropertyPriceHistory
from reagent_sydney.data.models.market_models import MarketTrend, SuburbStats


@dataclass
class PropertyComparable:
    """Comparable property data structure."""
    property_id: str
    address: str
    suburb: str
    postcode: str
    property_type: str
    bedrooms: int
    bathrooms: int
    car_spaces: int
    land_size: Optional[int]
    building_size: Optional[int]
    sale_price: Decimal
    sale_date: datetime
    days_on_market: int
    distance_km: float
    similarity_score: float
    adjustments: Dict[str, float]
    adjusted_price: Decimal


@dataclass
class CMAResult:
    """Comparable sales analysis result."""
    subject_property_id: str
    analysis_date: datetime
    comparables: List[PropertyComparable]
    price_range_low: Decimal
    price_range_high: Decimal
    estimated_value: Decimal
    confidence_interval_low: Decimal
    confidence_interval_high: Decimal
    confidence_level: float
    market_conditions_adjustment: float
    methodology_notes: str
    statistical_summary: Dict[str, Any]


class ComparableSalesAnalyzer:
    """
    Advanced Comparable Sales Analysis engine with statistical validation.
    
    Implements hedonic pricing model with geographic, temporal, and 
    property-specific adjustments to determine accurate property valuations.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Analysis parameters
        self.default_radius_km = 2.0
        self.max_radius_km = 5.0
        self.lookback_months = 6
        self.min_comparables = 3
        self.max_comparables = 12
        self.confidence_level = 0.95
        
        # Adjustment factors
        self.bedroom_adjustment_per_room = 0.15  # 15% per bedroom difference
        self.bathroom_adjustment_per_room = 0.08  # 8% per bathroom difference
        self.car_space_adjustment_per_space = 0.05  # 5% per car space difference
        self.land_size_adjustment_per_100sqm = 0.03  # 3% per 100sqm difference
        self.building_size_adjustment_per_100sqm = 0.08  # 8% per 100sqm difference
        
        # Time-based adjustments
        self.monthly_market_adjustment = 0.01  # 1% per month market movement
        self.max_time_adjustment = 0.20  # Maximum 20% time adjustment
        
        # Distance penalty
        self.distance_penalty_per_km = 0.02  # 2% penalty per km
        
    async def analyze_comparables(
        self, 
        property_data: Dict[str, Any],
        radius_km: float = None,
        lookback_months: int = None,
        min_comparables: int = None
    ) -> CMAResult:
        """
        Perform comprehensive comparable sales analysis.
        
        Args:
            property_data: Subject property information
            radius_km: Search radius in kilometers
            lookback_months: How far back to look for sales
            min_comparables: Minimum number of comparables required
            
        Returns:
            CMAResult with valuation range and confidence metrics
        """
        try:
            # Set parameters
            radius_km = radius_km or self.default_radius_km
            lookback_months = lookback_months or self.lookback_months
            min_comparables = min_comparables or self.min_comparables
            
            self.logger.info(f"Starting CMA for property {property_data.get('id')}")
            
            # Find comparable sales
            comparables = await self._find_comparable_sales(
                property_data, radius_km, lookback_months
            )
            
            if len(comparables) < min_comparables:
                # Expand search if insufficient comparables
                self.logger.warning(f"Only {len(comparables)} comparables found, expanding search")
                comparables = await self._expand_comparable_search(
                    property_data, radius_km, lookback_months
                )
            
            if len(comparables) < min_comparables:
                raise ValueError(f"Insufficient comparables found: {len(comparables)} < {min_comparables}")
            
            # Apply adjustments to comparables
            adjusted_comparables = await self._adjust_comparables(
                property_data, comparables
            )
            
            # Calculate valuation range and statistics
            valuation_result = self._calculate_valuation_range(adjusted_comparables)
            
            # Apply market conditions adjustment
            market_adjustment = await self._get_market_conditions_adjustment(
                property_data['suburb'], property_data['property_type']
            )
            
            # Build final result
            result = CMAResult(
                subject_property_id=property_data['id'],
                analysis_date=datetime.utcnow(),
                comparables=adjusted_comparables,
                price_range_low=valuation_result['range_low'] * (1 + market_adjustment),
                price_range_high=valuation_result['range_high'] * (1 + market_adjustment),
                estimated_value=valuation_result['estimated_value'] * (1 + market_adjustment),
                confidence_interval_low=valuation_result['ci_low'] * (1 + market_adjustment),
                confidence_interval_high=valuation_result['ci_high'] * (1 + market_adjustment),
                confidence_level=valuation_result['confidence_level'],
                market_conditions_adjustment=market_adjustment,
                methodology_notes=self._generate_methodology_notes(adjusted_comparables),
                statistical_summary=valuation_result['statistics']
            )
            
            self.logger.info(f"CMA completed: ${result.estimated_value:,.2f} "
                           f"(${result.price_range_low:,.2f} - ${result.price_range_high:,.2f})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"CMA analysis failed: {str(e)}")
            raise
    
    async def _find_comparable_sales(
        self, 
        subject_property: Dict[str, Any],
        radius_km: float,
        lookback_months: int
    ) -> List[Dict[str, Any]]:
        """Find comparable sales within specified criteria."""
        
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_months * 30)
        
        async with get_db_session() as session:
            # Build query for comparable sales
            query = session.query(Property).join(PropertyPriceHistory).filter(
                and_(
                    Property.suburb == subject_property['suburb'],
                    Property.property_type == subject_property['property_type'],
                    Property.listing_status == 'sold',
                    PropertyPriceHistory.price_type == 'sold',
                    PropertyPriceHistory.created_at >= cutoff_date
                )
            )
            
            # Add bedroom range filter (±1 bedroom)
            if subject_property.get('bedrooms'):
                query = query.filter(
                    Property.bedrooms.between(
                        max(1, subject_property['bedrooms'] - 1),
                        subject_property['bedrooms'] + 1
                    )
                )
            
            # Execute query
            properties = query.order_by(PropertyPriceHistory.created_at.desc()).all()
            
            # Calculate distances and filter by radius
            comparables = []
            subject_lat = float(subject_property.get('latitude', 0))
            subject_lon = float(subject_property.get('longitude', 0))
            
            for prop in properties:
                if not prop.latitude or not prop.longitude:
                    continue
                    
                distance = self._calculate_distance(
                    subject_lat, subject_lon, 
                    float(prop.latitude), float(prop.longitude)
                )
                
                if distance <= radius_km:
                    # Get most recent sale price
                    latest_sale = session.query(PropertyPriceHistory).filter(
                        and_(
                            PropertyPriceHistory.property_id == prop.id,
                            PropertyPriceHistory.price_type == 'sold'
                        )
                    ).order_by(PropertyPriceHistory.created_at.desc()).first()
                    
                    if latest_sale:
                        comparables.append({
                            'property_id': str(prop.id),
                            'address': f"{prop.address_line_1}, {prop.suburb}",
                            'suburb': prop.suburb,
                            'postcode': prop.postcode,
                            'property_type': prop.property_type,
                            'bedrooms': prop.bedrooms or 0,
                            'bathrooms': prop.bathrooms or 0,
                            'car_spaces': prop.car_spaces or 0,
                            'land_size': prop.land_size,
                            'building_size': prop.building_size,
                            'sale_price': latest_sale.price,
                            'sale_date': latest_sale.created_at,
                            'days_on_market': prop.days_on_market or 0,
                            'distance_km': distance
                        })
            
            return comparables[:self.max_comparables]
    
    async def _expand_comparable_search(
        self,
        subject_property: Dict[str, Any],
        initial_radius_km: float,
        lookback_months: int
    ) -> List[Dict[str, Any]]:
        """Expand search criteria to find more comparables."""
        
        # Try expanding radius first
        expanded_radius = min(initial_radius_km * 1.5, self.max_radius_km)
        comparables = await self._find_comparable_sales(
            subject_property, expanded_radius, lookback_months
        )
        
        if len(comparables) >= self.min_comparables:
            return comparables
        
        # Try expanding time window
        expanded_lookback = min(lookback_months * 2, 12)
        comparables = await self._find_comparable_sales(
            subject_property, expanded_radius, expanded_lookback
        )
        
        if len(comparables) >= self.min_comparables:
            return comparables
        
        # Try expanding property type (e.g., include similar types)
        if subject_property['property_type'].lower() == 'house':
            # Include villas, townhouses for houses
            expanded_property = subject_property.copy()
            async with get_db_session() as session:
                similar_types_query = session.query(Property).join(PropertyPriceHistory).filter(
                    and_(
                        Property.suburb == subject_property['suburb'],
                        Property.property_type.in_(['Villa', 'Townhouse', 'Duplex']),
                        Property.listing_status == 'sold',
                        PropertyPriceHistory.price_type == 'sold'
                    )
                )
                
                additional_props = similar_types_query.all()
                # Process these similar to the main search
                # ... (implementation similar to _find_comparable_sales)
        
        return comparables
    
    async def _adjust_comparables(
        self,
        subject_property: Dict[str, Any],
        comparables: List[Dict[str, Any]]
    ) -> List[PropertyComparable]:
        """Apply hedonic adjustments to comparable properties."""
        
        adjusted_comparables = []
        
        for comp in comparables:
            adjustments = {}
            total_adjustment = 0.0
            
            # Bedroom adjustment
            bedroom_diff = (subject_property.get('bedrooms', 0) - comp['bedrooms'])
            bedroom_adj = bedroom_diff * self.bedroom_adjustment_per_room
            adjustments['bedrooms'] = bedroom_adj
            total_adjustment += bedroom_adj
            
            # Bathroom adjustment
            bathroom_diff = (subject_property.get('bathrooms', 0) - comp['bathrooms'])
            bathroom_adj = bathroom_diff * self.bathroom_adjustment_per_room
            adjustments['bathrooms'] = bathroom_adj
            total_adjustment += bathroom_adj
            
            # Car space adjustment
            car_diff = (subject_property.get('car_spaces', 0) - comp['car_spaces'])
            car_adj = car_diff * self.car_space_adjustment_per_space
            adjustments['car_spaces'] = car_adj
            total_adjustment += car_adj
            
            # Land size adjustment
            if subject_property.get('land_size') and comp['land_size']:
                land_diff = (subject_property['land_size'] - comp['land_size']) / 100
                land_adj = land_diff * self.land_size_adjustment_per_100sqm
                adjustments['land_size'] = land_adj
                total_adjustment += land_adj
            
            # Building size adjustment
            if subject_property.get('building_size') and comp['building_size']:
                building_diff = (subject_property['building_size'] - comp['building_size']) / 100
                building_adj = building_diff * self.building_size_adjustment_per_100sqm
                adjustments['building_size'] = building_adj
                total_adjustment += building_adj
            
            # Time adjustment (market movement since sale)
            months_ago = (datetime.utcnow() - comp['sale_date']).days / 30.0
            time_adj = min(months_ago * self.monthly_market_adjustment, self.max_time_adjustment)
            adjustments['time'] = time_adj
            total_adjustment += time_adj
            
            # Distance penalty
            distance_adj = -comp['distance_km'] * self.distance_penalty_per_km
            adjustments['distance'] = distance_adj
            total_adjustment += distance_adj
            
            # Calculate similarity score (inverse of total absolute adjustments)
            similarity_score = max(0, 1 - abs(total_adjustment))
            
            # Apply adjustments to price
            adjusted_price = comp['sale_price'] * (1 + total_adjustment)
            
            adjusted_comparables.append(PropertyComparable(
                property_id=comp['property_id'],
                address=comp['address'],
                suburb=comp['suburb'],
                postcode=comp['postcode'],
                property_type=comp['property_type'],
                bedrooms=comp['bedrooms'],
                bathrooms=comp['bathrooms'],
                car_spaces=comp['car_spaces'],
                land_size=comp['land_size'],
                building_size=comp['building_size'],
                sale_price=comp['sale_price'],
                sale_date=comp['sale_date'],
                days_on_market=comp['days_on_market'],
                distance_km=comp['distance_km'],
                similarity_score=similarity_score,
                adjustments=adjustments,
                adjusted_price=adjusted_price
            ))
        
        # Sort by similarity score (highest first)
        adjusted_comparables.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return adjusted_comparables
    
    def _calculate_valuation_range(self, comparables: List[PropertyComparable]) -> Dict[str, Any]:
        """Calculate valuation range and confidence intervals using statistical methods."""
        
        # Extract adjusted prices
        prices = [float(comp.adjusted_price) for comp in comparables]
        weights = [comp.similarity_score for comp in comparables]
        
        # Calculate weighted statistics
        weighted_mean = np.average(prices, weights=weights)
        weighted_std = np.sqrt(np.average((prices - weighted_mean)**2, weights=weights))
        
        # Calculate confidence intervals
        n = len(prices)
        t_value = 2.0 if n < 30 else 1.96  # t-distribution for small samples
        margin_of_error = t_value * (weighted_std / math.sqrt(n))
        
        ci_low = weighted_mean - margin_of_error
        ci_high = weighted_mean + margin_of_error
        
        # Calculate price range using interquartile range
        sorted_prices = sorted(prices)
        q1_idx = max(0, int(0.25 * len(sorted_prices)))
        q3_idx = min(len(sorted_prices) - 1, int(0.75 * len(sorted_prices)))
        
        range_low = sorted_prices[q1_idx]
        range_high = sorted_prices[q3_idx]
        
        # Adjust ranges based on data quality
        confidence_level = min(0.95, 0.7 + (n / 20))  # Higher confidence with more data
        
        return {
            'estimated_value': Decimal(str(round(weighted_mean, 2))),
            'range_low': Decimal(str(round(range_low, 2))),
            'range_high': Decimal(str(round(range_high, 2))),
            'ci_low': Decimal(str(round(ci_low, 2))),
            'ci_high': Decimal(str(round(ci_high, 2))),
            'confidence_level': confidence_level,
            'statistics': {
                'mean': weighted_mean,
                'median': np.median(prices),
                'std_dev': weighted_std,
                'min_price': min(prices),
                'max_price': max(prices),
                'sample_size': n,
                'coefficient_of_variation': weighted_std / weighted_mean if weighted_mean > 0 else 0
            }
        }
    
    async def _get_market_conditions_adjustment(
        self, 
        suburb: str, 
        property_type: str
    ) -> float:
        """Get market conditions adjustment factor."""
        
        try:
            async with get_db_session() as session:
                # Get recent market trend
                recent_trend = session.query(MarketTrend).filter(
                    and_(
                        MarketTrend.geography_name == suburb,
                        MarketTrend.property_type == property_type,
                        MarketTrend.period_end >= datetime.utcnow() - timedelta(days=90)
                    )
                ).order_by(MarketTrend.period_end.desc()).first()
                
                if recent_trend and recent_trend.price_change_percent:
                    # Apply partial market movement (conservative approach)
                    return float(recent_trend.price_change_percent) * 0.5 / 100
                
                return 0.0
                
        except Exception as e:
            self.logger.warning(f"Could not get market adjustment: {e}")
            return 0.0
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula."""
        
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) * math.sin(delta_lon / 2))
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _generate_methodology_notes(self, comparables: List[PropertyComparable]) -> str:
        """Generate methodology explanation for the analysis."""
        
        num_comps = len(comparables)
        avg_distance = sum(c.distance_km for c in comparables) / num_comps
        avg_similarity = sum(c.similarity_score for c in comparables) / num_comps
        
        return (
            f"Comparable Sales Analysis based on {num_comps} recent sales within "
            f"{avg_distance:.1f}km average distance. Adjustments applied for bedroom/bathroom "
            f"differences, land/building size variations, time-based market movements, and "
            f"location premiums. Average similarity score: {avg_similarity:.2f}. "
            f"Statistical confidence based on weighted regression analysis with "
            f"{self.confidence_level*100:.0f}% confidence intervals."
        )