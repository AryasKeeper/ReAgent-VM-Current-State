"""
ReAgent Sydney - Council DA Tracker

Development Application monitoring system for detecting off-market opportunities
through council planning applications and approvals.
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import json
import re
from dataclasses import dataclass

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import sessionmaker
import structlog

from ...core.database.engine import get_db_session
from ...data.models.property_models import Property
from .data_models import (
    OffMarketOpportunity, OpportunityType, CouncilDARecord, CouncilDAStatus,
    OpportunityScore, DistressSignalType
)


@dataclass
class CouncilAPIConfig:
    """Configuration for council API access."""
    name: str
    base_url: str
    api_key: Optional[str] = None
    rate_limit_per_hour: int = 100
    timeout_seconds: int = 30
    headers: Dict[str, str] = None
    auth_method: str = "api_key"  # api_key, oauth, none
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {
                "User-Agent": "ReAgent-Sydney/1.0 (Real Estate Intelligence)",
                "Accept": "application/json"
            }
            if self.api_key and self.auth_method == "api_key":
                self.headers["X-API-Key"] = self.api_key


class CouncilDATracker:
    """
    Council Development Application Tracker for Sydney councils.
    
    Monitors planning applications and development approvals to identify
    potential off-market opportunities.
    """
    
    def __init__(self, radar_config):
        self.radar_config = radar_config
        self.logger = structlog.get_logger("off_market_radar.council_da_tracker")
        
        # Council API configurations
        self.council_configs = self._initialize_council_configs()
        
        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting
        self.request_counts = {}
        self.last_request_times = {}
        
        # Cache for DA records
        self.da_cache = {}
        self.cache_expiry = {}
    
    def _initialize_council_configs(self) -> Dict[str, CouncilAPIConfig]:
        """Initialize configurations for Sydney council APIs."""
        return {
            "sydney": CouncilAPIConfig(
                name="City of Sydney",
                base_url="https://www.cityofsydney.nsw.gov.au/api/da",
                rate_limit_per_hour=200
            ),
            "waverley": CouncilAPIConfig(
                name="Waverley Council",
                base_url="https://www.waverley.nsw.gov.au/api/planning",
                rate_limit_per_hour=100
            ),
            "woollahra": CouncilAPIConfig(
                name="Woollahra Council",
                base_url="https://www.woollahra.nsw.gov.au/api/development",
                rate_limit_per_hour=100
            ),
            "randwick": CouncilAPIConfig(
                name="Randwick City Council",
                base_url="https://www.randwick.nsw.gov.au/api/da",
                rate_limit_per_hour=150
            ),
            "bayside": CouncilAPIConfig(
                name="Bayside Council",
                base_url="https://www.bayside.nsw.gov.au/api/planning",
                rate_limit_per_hour=100
            ),
            "inner_west": CouncilAPIConfig(
                name="Inner West Council",
                base_url="https://www.innerwest.nsw.gov.au/api/development",
                rate_limit_per_hour=150
            ),
            "north_sydney": CouncilAPIConfig(
                name="North Sydney Council",
                base_url="https://www.northsydney.nsw.gov.au/api/da",
                rate_limit_per_hour=100
            ),
            "mosman": CouncilAPIConfig(
                name="Mosman Council",
                base_url="https://www.mosman.nsw.gov.au/api/planning",
                rate_limit_per_hour=75
            ),
            "manly": CouncilAPIConfig(
                name="Northern Beaches Council",
                base_url="https://www.northernbeaches.nsw.gov.au/api/development",
                rate_limit_per_hour=200
            ),
            "ryde": CouncilAPIConfig(
                name="City of Ryde",
                base_url="https://www.ryde.nsw.gov.au/api/da",
                rate_limit_per_hour=100
            )
        }
    
    async def initialize(self) -> None:
        """Initialize the DA tracker."""
        try:
            # Create HTTP session
            connector = aiohttp.TCPConnector(limit=20, limit_per_host=5)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )
            
            # Initialize request tracking
            current_time = datetime.utcnow()
            for council_id in self.council_configs:
                self.request_counts[council_id] = 0
                self.last_request_times[council_id] = current_time
            
            self.logger.info("Council DA Tracker initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Council DA Tracker: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup DA tracker resources."""
        try:
            if self.session:
                await self.session.close()
            
            self.logger.info("Council DA Tracker cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Council DA Tracker cleanup: {e}")
    
    async def scan_development_applications(
        self, 
        target_suburbs: List[str] = None,
        lookback_days: int = 30
    ) -> List[OffMarketOpportunity]:
        """
        Scan for development application opportunities.
        
        Args:
            target_suburbs: List of suburbs to focus on
            lookback_days: How many days back to search
            
        Returns:
            List of opportunities discovered
        """
        opportunities = []
        
        try:
            # Determine which councils to query based on suburbs
            target_councils = self._get_councils_for_suburbs(target_suburbs)
            
            # Fetch DA records from each council
            all_da_records = []
            for council_id in target_councils:
                try:
                    da_records = await self._fetch_council_das(
                        council_id, 
                        lookback_days=lookback_days,
                        target_suburbs=target_suburbs
                    )
                    all_da_records.extend(da_records)
                    
                    # Rate limiting delay
                    await asyncio.sleep(self.radar_config.request_delay_seconds)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to fetch DAs from {council_id}: {e}")
                    continue
            
            # Process DA records to identify opportunities
            for da_record in all_da_records:
                opportunity = await self._analyze_da_for_opportunity(da_record)
                if opportunity:
                    opportunities.append(opportunity)
            
            # Save DA records to database
            await self._save_da_records(all_da_records)
            
            self.logger.info(f"Found {len(opportunities)} DA opportunities from {len(all_da_records)} records")
            
        except Exception as e:
            self.logger.error(f"Error scanning development applications: {e}")
            raise
        
        return opportunities
    
    def _get_councils_for_suburbs(self, target_suburbs: List[str]) -> List[str]:
        """Map suburbs to their corresponding councils."""
        if not target_suburbs:
            # Return all councils if no specific suburbs
            return list(self.council_configs.keys())
        
        # Mapping of suburbs to councils (simplified for demo)
        suburb_council_map = {
            # City of Sydney
            "sydney": "sydney", "the rocks": "sydney", "circular quay": "sydney",
            "haymarket": "sydney", "chippendale": "sydney", "ultimo": "sydney",
            "pyrmont": "sydney", "darlinghurst": "sydney", "surry hills": "sydney",
            "woolloomooloo": "sydney", "potts point": "sydney", "kings cross": "sydney",
            
            # Waverley
            "bondi": "waverley", "bondi beach": "waverley", "bondi junction": "waverley",
            "bronte": "waverley", "tamarama": "waverley", "waverley": "waverley",
            "dover heights": "waverley",
            
            # Woollahra
            "woollahra": "woollahra", "double bay": "woollahra", "edgecliff": "woollahra",
            "paddington": "woollahra", "point piper": "woollahra", "rose bay": "woollahra",
            "vaucluse": "woollahra", "watsons bay": "woollahra",
            
            # Randwick
            "randwick": "randwick", "coogee": "randwick", "clovelly": "randwick",
            "maroubra": "randwick", "south coogee": "randwick", "little bay": "randwick",
            "malabar": "randwick", "la perouse": "randwick",
            
            # Inner West
            "newtown": "inner_west", "enmore": "inner_west", "marrickville": "inner_west",
            "dulwich hill": "inner_west", "petersham": "inner_west", "leichhardt": "inner_west",
            "balmain": "inner_west", "rozelle": "inner_west", "lilyfield": "inner_west",
            
            # North Sydney
            "north sydney": "north_sydney", "milsons point": "north_sydney",
            "lavender bay": "north_sydney", "kirribilli": "north_sydney",
            "neutral bay": "north_sydney", "cremorne": "north_sydney",
            
            # Mosman
            "mosman": "mosman", "balmoral": "mosman", "the spit": "mosman",
            
            # Northern Beaches (Manly)
            "manly": "manly", "freshwater": "manly", "curl curl": "manly",
            "dee why": "manly", "brookvale": "manly", "avalon": "manly",
            "palm beach": "manly", "mona vale": "manly",
            
            # Ryde
            "ryde": "ryde", "gladesville": "ryde", "huntleys cove": "ryde",
            "putney": "ryde", "tennyson point": "ryde"
        }
        
        councils = set()
        for suburb in target_suburbs:
            suburb_lower = suburb.lower().strip()
            council = suburb_council_map.get(suburb_lower)
            if council:
                councils.add(council)
        
        return list(councils) if councils else list(self.council_configs.keys())
    
    async def _fetch_council_das(
        self, 
        council_id: str, 
        lookback_days: int,
        target_suburbs: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch DA records from a specific council."""
        config = self.council_configs.get(council_id)
        if not config:
            return []
        
        # Check rate limits
        if not await self._check_rate_limit(council_id):
            self.logger.warning(f"Rate limit exceeded for {council_id}")
            return []
        
        try:
            # Build query parameters
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=lookback_days)
            
            params = {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "format": "json",
                "limit": 100
            }
            
            if target_suburbs:
                params["suburbs"] = ",".join(target_suburbs)
            
            # Make API request
            url = f"{config.base_url}/applications"
            headers = config.headers.copy()
            
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    da_records = self._parse_da_response(data, council_id)
                    
                    # Update request tracking
                    self.request_counts[council_id] += 1
                    self.last_request_times[council_id] = datetime.utcnow()
                    
                    return da_records
                else:
                    self.logger.warning(f"API request failed for {council_id}: {response.status}")
                    return []
        
        except Exception as e:
            self.logger.error(f"Error fetching DAs from {council_id}: {e}")
            return []
    
    def _parse_da_response(self, data: Dict[str, Any], council_id: str) -> List[Dict[str, Any]]:
        """Parse DA response data into standardized format."""
        da_records = []
        
        try:
            # Handle different response formats from different councils
            records = data.get("applications", data.get("results", data.get("data", [])))
            
            for record in records:
                parsed_record = {
                    "council_id": council_id,
                    "da_number": record.get("application_number", record.get("da_number", "")),
                    "status": self._normalize_da_status(record.get("status", "")),
                    "address": record.get("address", record.get("property_address", "")),
                    "suburb": record.get("suburb", ""),
                    "postcode": record.get("postcode", ""),
                    "application_type": record.get("application_type", record.get("type", "")),
                    "development_type": record.get("development_type", record.get("development", "")),
                    "description": record.get("description", record.get("proposal", "")),
                    "estimated_cost": Decimal(str(record.get("estimated_cost", 0))) if record.get("estimated_cost") else None,
                    "lodged_date": self._parse_date(record.get("lodged_date", record.get("date_lodged"))),
                    "decision_date": self._parse_date(record.get("decision_date", record.get("determination_date"))),
                    "applicant_name": record.get("applicant", record.get("applicant_name", "")),
                    "applicant_type": record.get("applicant_type", "unknown"),
                    "officer_assessment": record.get("assessment", record.get("officer_comments", "")),
                    "public_submissions": int(record.get("submissions", record.get("public_submissions", 0))),
                    "conditions": record.get("conditions", {}),
                    "source_url": record.get("url", ""),
                    "raw_data": record
                }
                
                # Only include records with minimum required data
                if parsed_record["da_number"] and parsed_record["address"]:
                    da_records.append(parsed_record)
        
        except Exception as e:
            self.logger.error(f"Error parsing DA response from {council_id}: {e}")
        
        return da_records
    
    def _normalize_da_status(self, status: str) -> str:
        """Normalize DA status across different councils."""
        if not status:
            return "unknown"
        
        status_lower = status.lower().strip()
        
        # Map various status formats to standard values
        status_mapping = {
            "lodged": CouncilDAStatus.LODGED.value,
            "received": CouncilDAStatus.LODGED.value,
            "under assessment": CouncilDAStatus.UNDER_ASSESSMENT.value,
            "assessment": CouncilDAStatus.UNDER_ASSESSMENT.value,
            "pending": CouncilDAStatus.UNDER_ASSESSMENT.value,
            "approved": CouncilDAStatus.APPROVED.value,
            "consent": CouncilDAStatus.APPROVED.value,
            "granted": CouncilDAStatus.APPROVED.value,
            "refused": CouncilDAStatus.REJECTED.value,
            "rejected": CouncilDAStatus.REJECTED.value,
            "denied": CouncilDAStatus.REJECTED.value,
            "withdrawn": CouncilDAStatus.WITHDRAWN.value,
            "cancelled": CouncilDAStatus.WITHDRAWN.value,
            "appealed": CouncilDAStatus.APPEALED.value,
            "appeal": CouncilDAStatus.APPEALED.value
        }
        
        return status_mapping.get(status_lower, "unknown")
    
    def _parse_date(self, date_str: Any) -> Optional[datetime]:
        """Parse date string into datetime object."""
        if not date_str:
            return None
        
        if isinstance(date_str, datetime):
            return date_str
        
        # Try different date formats
        date_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ"
        ]
        
        for date_format in date_formats:
            try:
                return datetime.strptime(str(date_str), date_format)
            except ValueError:
                continue
        
        return None
    
    async def _analyze_da_for_opportunity(self, da_record: Dict[str, Any]) -> Optional[OffMarketOpportunity]:
        """Analyze a DA record to identify potential opportunities."""
        try:
            # Skip if insufficient data
            if not da_record.get("address") or not da_record.get("suburb"):
                return None
            
            # Identify opportunity indicators
            opportunity_indicators = self._identify_opportunity_indicators(da_record)
            
            if not opportunity_indicators["has_opportunity"]:
                return None
            
            # Calculate opportunity score
            scoring = await self._calculate_da_opportunity_score(da_record, opportunity_indicators)
            
            # Create opportunity
            opportunity = OffMarketOpportunity(
                opportunity_type=OpportunityType.COUNCIL_DA,
                address=da_record["address"],
                suburb=da_record["suburb"],
                postcode=da_record.get("postcode", ""),
                title=f"DA Opportunity: {da_record.get('development_type', 'Development')}",
                description=self._generate_da_opportunity_description(da_record, opportunity_indicators),
                scoring=scoring,
                opportunity_details={
                    "da_number": da_record["da_number"],
                    "council_id": da_record["council_id"],
                    "status": da_record["status"],
                    "application_type": da_record.get("application_type", ""),
                    "development_type": da_record.get("development_type", ""),
                    "estimated_cost": float(da_record["estimated_cost"]) if da_record["estimated_cost"] else None,
                    "lodged_date": da_record["lodged_date"].isoformat() if da_record["lodged_date"] else None,
                    "opportunity_indicators": opportunity_indicators["indicators"]
                },
                data_sources=["council_da", da_record["council_id"]],
                evidence={
                    "da_record": da_record,
                    "opportunity_analysis": opportunity_indicators
                },
                confidence_level=opportunity_indicators["confidence"],
                expires_at=self._calculate_da_opportunity_expiry(da_record),
                compliance_checked=True,
                ethical_approval=True,  # Public DA records are ethical to use
                data_privacy_compliant=True
            )
            
            # Add relevant tags
            opportunity.tags = self._generate_da_tags(da_record, opportunity_indicators)
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Error analyzing DA for opportunity: {e}")
            return None
    
    def _identify_opportunity_indicators(self, da_record: Dict[str, Any]) -> Dict[str, Any]:
        """Identify indicators that suggest an off-market opportunity."""
        indicators = []
        confidence = 0.0
        
        try:
            status = da_record.get("status", "").lower()
            development_type = da_record.get("development_type", "").lower()
            description = da_record.get("description", "").lower()
            applicant_type = da_record.get("applicant_type", "").lower()
            
            # High-opportunity indicators
            if "demolition" in development_type or "demolish" in description:
                indicators.append("demolition_planned")
                confidence += 0.3
            
            if "subdivision" in development_type or "subdivide" in description:
                indicators.append("subdivision_opportunity")
                confidence += 0.25
            
            if "major development" in development_type or "multi-unit" in description:
                indicators.append("development_potential")
                confidence += 0.2
            
            # Status-based indicators
            if status == "approved":
                indicators.append("approved_development")
                confidence += 0.15
            elif status == "rejected" or status == "refused":
                indicators.append("rejected_application")
                confidence += 0.1  # Lower confidence for rejected apps
            
            # Applicant type indicators
            if "developer" in applicant_type:
                indicators.append("developer_involvement")
                confidence += 0.1
            elif "owner" in applicant_type:
                indicators.append("owner_initiated")
                confidence += 0.05
            
            # Cost-based indicators
            estimated_cost = da_record.get("estimated_cost")
            if estimated_cost and estimated_cost > 500000:
                indicators.append("major_investment")
                confidence += 0.1
            
            # Timeline indicators
            lodged_date = da_record.get("lodged_date")
            if lodged_date:
                days_since_lodged = (datetime.utcnow() - lodged_date).days
                if days_since_lodged > 180:  # Long processing time
                    indicators.append("extended_processing")
                    confidence += 0.05
            
            # Public submissions (high controversy might indicate opportunity)
            submissions = da_record.get("public_submissions", 0)
            if submissions > 10:
                indicators.append("high_public_interest")
                confidence += 0.05
            
            has_opportunity = len(indicators) > 0 and confidence > 0.1
            
            return {
                "has_opportunity": has_opportunity,
                "indicators": indicators,
                "confidence": min(1.0, confidence),
                "total_indicators": len(indicators)
            }
            
        except Exception as e:
            self.logger.error(f"Error identifying opportunity indicators: {e}")
            return {
                "has_opportunity": False,
                "indicators": [],
                "confidence": 0.0,
                "total_indicators": 0
            }
    
    async def _calculate_da_opportunity_score(
        self, 
        da_record: Dict[str, Any], 
        indicators: Dict[str, Any]
    ) -> OpportunityScore:
        """Calculate opportunity score for DA-based opportunity."""
        try:
            # Base scoring from indicators
            base_confidence = indicators["confidence"]
            
            # ROI potential based on development type and cost
            roi_potential = 0.0
            development_type = da_record.get("development_type", "").lower()
            estimated_cost = da_record.get("estimated_cost")
            
            if "demolition" in development_type:
                roi_potential = 0.8  # High redevelopment potential
            elif "subdivision" in development_type:
                roi_potential = 0.7  # Good subdivision potential
            elif "extension" in development_type or "addition" in development_type:
                roi_potential = 0.4  # Moderate improvement potential
            else:
                roi_potential = 0.3  # General development potential
            
            # Adjust for cost magnitude
            if estimated_cost:
                if estimated_cost > 1000000:
                    roi_potential *= 1.2  # Major developments have higher potential
                elif estimated_cost < 50000:
                    roi_potential *= 0.7  # Minor works have lower potential
            
            # Time sensitivity based on status and dates
            time_sensitivity = 0.0
            status = da_record.get("status", "").lower()
            
            if status == "approved":
                time_sensitivity = 0.8  # Approved DAs are time-sensitive
            elif status == "under_assessment":
                time_sensitivity = 0.4  # Assessment stage is moderately time-sensitive
            elif status == "rejected":
                time_sensitivity = 0.6  # Rejected apps might lead to quick sales
            
            # Market conditions (simplified - would integrate with market data)
            suburb = da_record.get("suburb", "")
            market_conditions = await self._get_suburb_market_conditions(suburb)
            
            # Acquisition difficulty
            acquisition_difficulty = 0.5  # Base difficulty
            
            # Adjust based on applicant type
            applicant_type = da_record.get("applicant_type", "").lower()
            if "developer" in applicant_type:
                acquisition_difficulty = 0.7  # Developers less likely to sell quickly
            elif "owner" in applicant_type:
                acquisition_difficulty = 0.4  # Owner-occupiers might be more flexible
            
            # Overall score calculation
            overall_score = (
                base_confidence * 0.3 +
                roi_potential * 0.3 +
                time_sensitivity * 0.2 +
                market_conditions * 0.1 +
                (1 - acquisition_difficulty) * 0.1
            )
            
            return OpportunityScore(
                overall_score=min(1.0, overall_score),
                roi_potential=min(1.0, roi_potential),
                acquisition_difficulty=min(1.0, acquisition_difficulty),
                time_sensitivity=min(1.0, time_sensitivity),
                market_conditions=market_conditions,
                price_attractiveness=0.5,  # Not available from DA data
                location_desirability=market_conditions,
                property_condition=0.5,  # Not available from DA data
                seller_motivation=time_sensitivity,
                legal_risk=0.2 if status == "approved" else 0.4,  # Lower risk for approved DAs
                market_risk=1 - market_conditions,
                execution_risk=acquisition_difficulty
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating DA opportunity score: {e}")
            return OpportunityScore()
    
    async def _get_suburb_market_conditions(self, suburb: str) -> float:
        """Get market conditions score for a suburb (0.0 to 1.0)."""
        try:
            # This would integrate with the Suburb Signal Agent
            # For now, return a reasonable default based on suburb
            
            # Premium Sydney suburbs get higher scores
            premium_suburbs = [
                "double bay", "point piper", "vaucluse", "bellevue hill",
                "mosman", "kirribilli", "milsons point", "bondi beach"
            ]
            
            good_suburbs = [
                "paddington", "surry hills", "newtown", "balmain",
                "coogee", "bronte", "manly", "neutral bay"
            ]
            
            suburb_lower = suburb.lower().strip()
            
            if suburb_lower in premium_suburbs:
                return 0.8
            elif suburb_lower in good_suburbs:
                return 0.6
            else:
                return 0.4  # Default for other areas
                
        except Exception:
            return 0.4  # Safe default
    
    def _generate_da_opportunity_description(
        self, 
        da_record: Dict[str, Any], 
        indicators: Dict[str, Any]
    ) -> str:
        """Generate a description for the DA opportunity."""
        try:
            da_number = da_record.get("da_number", "Unknown")
            development_type = da_record.get("development_type", "development")
            status = da_record.get("status", "unknown status")
            
            description = f"Development Application {da_number} for {development_type} "
            description += f"(Status: {status}). "
            
            # Add key indicators
            if "demolition_planned" in indicators["indicators"]:
                description += "Property planned for demolition, indicating potential redevelopment opportunity. "
            
            if "subdivision_opportunity" in indicators["indicators"]:
                description += "Subdivision application suggests land value optimization potential. "
            
            if "approved_development" in indicators["indicators"]:
                description += "Approved development provides clear development pathway. "
            
            if "developer_involvement" in indicators["indicators"]:
                description += "Developer involvement suggests commercial viability. "
            
            # Add estimated cost if available
            estimated_cost = da_record.get("estimated_cost")
            if estimated_cost:
                description += f"Estimated development cost: ${estimated_cost:,.0f}. "
            
            description += f"Confidence level: {indicators['confidence']:.1%}"
            
            return description
            
        except Exception as e:
            self.logger.error(f"Error generating DA opportunity description: {e}")
            return "Development application opportunity identified."
    
    def _calculate_da_opportunity_expiry(self, da_record: Dict[str, Any]) -> Optional[datetime]:
        """Calculate when this DA opportunity might expire."""
        try:
            status = da_record.get("status", "").lower()
            lodged_date = da_record.get("lodged_date")
            decision_date = da_record.get("decision_date")
            
            # Different expiry logic based on status
            if status == "approved" and decision_date:
                # Approved DAs typically have 5 years to commence
                return decision_date + timedelta(days=1825)  # 5 years
            
            elif status == "under_assessment" and lodged_date:
                # Assessment typically takes 6-12 months
                return lodged_date + timedelta(days=365)  # 1 year from lodged
            
            elif status == "rejected" and decision_date:
                # Rejected applications might lead to quick sales within 6 months
                return decision_date + timedelta(days=180)  # 6 months
            
            # Default expiry of 1 year from now
            return datetime.utcnow() + timedelta(days=365)
            
        except Exception:
            return datetime.utcnow() + timedelta(days=365)  # Safe default
    
    def _generate_da_tags(
        self, 
        da_record: Dict[str, Any], 
        indicators: Dict[str, Any]
    ) -> List[str]:
        """Generate tags for the DA opportunity."""
        tags = ["council_da", "development_opportunity"]
        
        # Add council-specific tag
        council_id = da_record.get("council_id")
        if council_id:
            tags.append(f"council_{council_id}")
        
        # Add development type tag
        development_type = da_record.get("development_type", "").lower()
        if development_type:
            tags.append(development_type.replace(" ", "_"))
        
        # Add status tag
        status = da_record.get("status", "").lower()
        if status:
            tags.append(f"status_{status}")
        
        # Add indicator-based tags
        for indicator in indicators["indicators"]:
            tags.append(indicator)
        
        # Add confidence level tag
        confidence = indicators["confidence"]
        if confidence > 0.7:
            tags.append("high_confidence")
        elif confidence > 0.4:
            tags.append("medium_confidence")
        else:
            tags.append("low_confidence")
        
        return tags
    
    async def _check_rate_limit(self, council_id: str) -> bool:
        """Check if we can make a request to this council."""
        config = self.council_configs.get(council_id)
        if not config:
            return False
        
        now = datetime.utcnow()
        last_request = self.last_request_times.get(council_id, now)
        
        # Reset counter if it's been more than an hour
        if (now - last_request).total_seconds() > 3600:
            self.request_counts[council_id] = 0
        
        return self.request_counts[council_id] < config.rate_limit_per_hour
    
    async def _save_da_records(self, da_records: List[Dict[str, Any]]) -> None:
        """Save DA records to the database."""
        if not da_records:
            return
        
        try:
            async with get_db_session() as session:
                for da_record in da_records:
                    # Check if record already exists
                    existing = await session.execute(
                        select(CouncilDARecord).where(
                            CouncilDARecord.da_number == da_record["da_number"]
                        )
                    )
                    
                    if existing.scalar_one_or_none():
                        continue  # Skip existing records
                    
                    # Create new record
                    db_record = CouncilDARecord(
                        da_number=da_record["da_number"],
                        council_name=self.council_configs[da_record["council_id"]].name,
                        status=da_record["status"],
                        address=da_record["address"],
                        suburb=da_record["suburb"],
                        postcode=da_record["postcode"],
                        application_type=da_record.get("application_type"),
                        development_type=da_record.get("development_type"),
                        description=da_record.get("description"),
                        estimated_cost=da_record.get("estimated_cost"),
                        lodged_date=da_record.get("lodged_date"),
                        decision_date=da_record.get("decision_date"),
                        applicant_name=da_record.get("applicant_name"),
                        applicant_type=da_record.get("applicant_type"),
                        officer_assessment=da_record.get("officer_assessment"),
                        public_submissions=da_record.get("public_submissions", 0),
                        conditions=da_record.get("conditions", {}),
                        source_url=da_record.get("source_url"),
                        raw_data=da_record.get("raw_data"),
                        last_updated_source=datetime.utcnow()
                    )
                    
                    session.add(db_record)
                
                await session.commit()
                
                self.logger.info(f"Saved {len(da_records)} DA records to database")
                
        except Exception as e:
            self.logger.error(f"Error saving DA records: {e}")
    
    async def get_recent_das_by_suburb(
        self, 
        suburb: str, 
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """Get recent DAs for a specific suburb."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            async with get_db_session() as session:
                result = await session.execute(
                    select(CouncilDARecord).where(
                        and_(
                            CouncilDARecord.suburb.ilike(f"%{suburb}%"),
                            CouncilDARecord.created_at >= cutoff_date
                        )
                    ).order_by(CouncilDARecord.created_at.desc())
                )
                
                records = result.scalars().all()
                
                return [
                    {
                        "da_number": record.da_number,
                        "council_name": record.council_name,
                        "status": record.status,
                        "address": record.address,
                        "suburb": record.suburb,
                        "development_type": record.development_type,
                        "lodged_date": record.lodged_date,
                        "estimated_cost": float(record.estimated_cost) if record.estimated_cost else None
                    }
                    for record in records
                ]
                
        except Exception as e:
            self.logger.error(f"Error getting recent DAs for {suburb}: {e}")
            return []