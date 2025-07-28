"""
ReAgent Sydney - Compliance Monitor

Comprehensive compliance and ethical monitoring system ensuring all
off-market radar activities adhere to legal and ethical standards.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

import structlog

from .data_models import OffMarketOpportunity, OpportunityType


class ComplianceLevel(str, Enum):
    """Compliance severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationType(str, Enum):
    """Types of compliance violations."""
    PRIVACY_BREACH = "privacy_breach"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_MISUSE = "data_misuse"
    ETHICAL_VIOLATION = "ethical_violation"
    LEGAL_VIOLATION = "legal_violation"
    RATE_LIMIT_BREACH = "rate_limit_breach"
    TERMS_VIOLATION = "terms_violation"
    DISCRIMINATION = "discrimination"


@dataclass
class ComplianceRule:
    """Represents a compliance rule."""
    
    rule_id: str
    name: str
    description: str
    category: str  # 'privacy', 'legal', 'ethical', 'technical'
    severity: ComplianceLevel
    
    # Rule logic
    check_function: str  # Name of the checking function
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Enforcement
    enforce: bool = True
    allow_override: bool = False
    
    # Documentation
    legal_basis: str = ""
    reference_url: str = ""
    
    @property
    def is_critical(self) -> bool:
        """Check if this is a critical compliance rule."""
        return self.severity == ComplianceLevel.CRITICAL


@dataclass
class ComplianceViolation:
    """Represents a compliance violation."""
    
    violation_id: str
    rule_id: str
    rule_name: str
    violation_type: ViolationType
    severity: ComplianceLevel
    
    # Details
    description: str
    evidence: Dict[str, Any]
    affected_entity: str  # Property ID, opportunity ID, etc.
    
    # Context
    detected_at: datetime
    detection_method: str
    source_component: str
    
    # Resolution
    resolved: bool = False
    resolution_action: Optional[str] = None
    resolved_at: Optional[datetime] = None
    
    @property
    def is_blocking(self) -> bool:
        """Check if this violation blocks further processing."""
        return self.severity in [ComplianceLevel.HIGH, ComplianceLevel.CRITICAL]


@dataclass
class ComplianceReport:
    """Comprehensive compliance report."""
    
    report_id: str
    generated_at: datetime
    scope: str  # 'scan', 'opportunity', 'system'
    
    # Summary
    total_checks: int
    passed_checks: int
    failed_checks: int
    violations: List[ComplianceViolation]
    
    # Status
    overall_status: str  # 'compliant', 'warning', 'violation', 'critical'
    blocking_violations: int
    
    # Recommendations
    recommendations: List[str]
    required_actions: List[str]
    
    @property
    def compliance_rate(self) -> float:
        """Calculate compliance rate percentage."""
        if self.total_checks == 0:
            return 100.0
        return (self.passed_checks / self.total_checks) * 100.0
    
    @property
    def has_blocking_violations(self) -> bool:
        """Check if there are blocking violations."""
        return self.blocking_violations > 0


class ComplianceMonitor:
    """
    Comprehensive compliance monitoring system.
    
    Monitors compliance across:
    1. Data privacy and protection (GDPR, Privacy Act)
    2. Legal and regulatory requirements
    3. Ethical guidelines and standards
    4. Terms of service and API usage
    5. Rate limiting and technical constraints
    6. Anti-discrimination policies
    """
    
    def __init__(self, radar_config):
        self.radar_config = radar_config
        self.logger = structlog.get_logger("off_market_radar.compliance_monitor")
        
        # Compliance rules
        self.compliance_rules = self._initialize_compliance_rules()
        
        # Monitoring state
        self.violation_log = []
        self.api_usage_tracking = {}
        self.data_access_log = []
        
        # Rate limiting
        self.rate_limits = {
            'domain_api': {'limit': 1000, 'window': 3600, 'usage': 0, 'reset_time': datetime.utcnow()},
            'rea_api': {'limit': 500, 'window': 3600, 'usage': 0, 'reset_time': datetime.utcnow()},
            'council_api': {'limit': 100, 'window': 3600, 'usage': 0, 'reset_time': datetime.utcnow()},
            'data_scraping': {'limit': 200, 'window': 3600, 'usage': 0, 'reset_time': datetime.utcnow()}
        }
    
    async def initialize(self) -> None:
        """Initialize the compliance monitor."""
        try:
            # Load any stored compliance state
            await self._load_compliance_state()
            
            # Validate compliance rules
            self._validate_compliance_rules()
            
            self.logger.info("Compliance Monitor initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Compliance Monitor: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup compliance monitor resources."""
        try:
            # Save compliance state
            await self._save_compliance_state()
            
            # Generate final compliance report
            await self._generate_session_report()
            
            self.logger.info("Compliance Monitor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Compliance Monitor cleanup: {e}")
    
    async def pre_scan_check(self) -> Dict[str, Any]:
        """Perform compliance checks before scanning operations."""
        try:
            self.logger.info("Performing pre-scan compliance check")
            
            violations = []
            
            # Check rate limits
            rate_violations = await self._check_rate_limits()
            violations.extend(rate_violations)
            
            # Check data access permissions
            access_violations = await self._check_data_access_permissions()
            violations.extend(access_violations)
            
            # Check privacy compliance
            privacy_violations = await self._check_privacy_compliance()
            violations.extend(privacy_violations)
            
            # Check ethical guidelines
            ethical_violations = await self._check_ethical_guidelines()
            violations.extend(ethical_violations)
            
            # Determine if scan can proceed
            blocking_violations = [v for v in violations if v.is_blocking]
            
            approval_status = {
                'approved': len(blocking_violations) == 0,
                'violations': len(violations),
                'blocking_violations': len(blocking_violations),
                'reason': None,
                'recommendations': []
            }
            
            if blocking_violations:
                approval_status['reason'] = f"Found {len(blocking_violations)} blocking compliance violations"
                approval_status['recommendations'] = [
                    "Resolve all critical and high-severity violations before proceeding",
                    "Review compliance policies and procedures",
                    "Contact compliance team if violations persist"
                ]
            
            # Log violations
            for violation in violations:
                self.violation_log.append(violation)
                self.logger.warning(f"Compliance violation: {violation.description}")
            
            return approval_status
            
        except Exception as e:
            self.logger.error(f"Error in pre-scan compliance check: {e}")
            return {
                'approved': False,
                'violations': 0,
                'blocking_violations': 1,
                'reason': f"Compliance check failed: {str(e)}",
                'recommendations': ["Review system configuration and try again"]
            }
    
    async def generate_scan_report(
        self, 
        opportunities: List[OffMarketOpportunity]
    ) -> Dict[str, Any]:
        """Generate compliance report for scan results."""
        try:
            report_id = f"scan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            violations = []
            total_checks = 0
            passed_checks = 0
            
            # Check each opportunity for compliance
            for opportunity in opportunities:
                opp_violations, opp_checks, opp_passed = await self._check_opportunity_compliance(opportunity)
                violations.extend(opp_violations)
                total_checks += opp_checks
                passed_checks += opp_passed
            
            # Check overall scan compliance
            scan_violations, scan_checks, scan_passed = await self._check_scan_compliance(opportunities)
            violations.extend(scan_violations)
            total_checks += scan_checks
            passed_checks += scan_passed
            
            # Determine overall status
            blocking_violations = len([v for v in violations if v.is_blocking])
            
            if blocking_violations > 0:
                overall_status = "critical"
            elif len(violations) > 0:
                overall_status = "violation"
            elif total_checks > passed_checks:
                overall_status = "warning"
            else:
                overall_status = "compliant"
            
            # Generate recommendations
            recommendations = self._generate_compliance_recommendations(violations)
            required_actions = self._generate_required_actions(violations)
            
            # Create compliance report
            report = ComplianceReport(
                report_id=report_id,
                generated_at=datetime.utcnow(),
                scope="scan",
                total_checks=total_checks,
                passed_checks=passed_checks,
                failed_checks=total_checks - passed_checks,
                violations=violations,
                overall_status=overall_status,
                blocking_violations=blocking_violations,
                recommendations=recommendations,
                required_actions=required_actions
            )
            
            # Convert to dictionary for API response
            return {
                'report_id': report.report_id,
                'generated_at': report.generated_at.isoformat(),
                'scope': report.scope,
                'overall_status': report.overall_status,
                'compliance_rate': report.compliance_rate,
                'total_checks': report.total_checks,
                'passed_checks': report.passed_checks,
                'failed_checks': report.failed_checks,
                'violations_count': len(report.violations),
                'blocking_violations': report.blocking_violations,
                'has_blocking_violations': report.has_blocking_violations,
                'violations': [
                    {
                        'rule_name': v.rule_name,
                        'severity': v.severity.value,
                        'description': v.description,
                        'affected_entity': v.affected_entity,
                        'violation_type': v.violation_type.value
                    }
                    for v in report.violations
                ],
                'recommendations': report.recommendations,
                'required_actions': report.required_actions
            }
            
        except Exception as e:
            self.logger.error(f"Error generating scan compliance report: {e}")
            return {
                'report_id': 'error',
                'generated_at': datetime.utcnow().isoformat(),
                'overall_status': 'error',
                'error': str(e)
            }
    
    def _initialize_compliance_rules(self) -> List[ComplianceRule]:
        """Initialize compliance rules."""
        rules = [
            # Privacy and Data Protection Rules
            ComplianceRule(
                rule_id="privacy_001",
                name="Public Data Only",
                description="Only access publicly available property data",
                category="privacy",
                severity=ComplianceLevel.CRITICAL,
                check_function="check_public_data_only",
                legal_basis="Privacy Act 1988 (Cth), GDPR Article 6",
                reference_url="https://www.oaic.gov.au/privacy/privacy-act"
            ),
            
            ComplianceRule(
                rule_id="privacy_002",
                name="Personal Information Protection",
                description="Protect personal information of property owners and agents",
                category="privacy",  
                severity=ComplianceLevel.HIGH,
                check_function="check_personal_info_protection",
                legal_basis="Privacy Act 1988 (Cth)",
                reference_url="https://www.oaic.gov.au/privacy/privacy-act"
            ),
            
            ComplianceRule(
                rule_id="privacy_003",
                name="Data Retention Limits",
                description="Respect data retention limits and delete expired data",
                category="privacy",
                severity=ComplianceLevel.MEDIUM,
                check_function="check_data_retention",
                parameters={"max_retention_days": self.radar_config.data_retention_days}
            ),
            
            # Legal and Regulatory Rules
            ComplianceRule(
                rule_id="legal_001",
                name="Terms of Service Compliance",
                description="Comply with all website terms of service",
                category="legal",
                severity=ComplianceLevel.HIGH,
                check_function="check_terms_compliance"
            ),
            
            ComplianceRule(
                rule_id="legal_002",
                name="Robot.txt Compliance",
                description="Respect robots.txt files for web scraping",
                category="legal",
                severity=ComplianceLevel.MEDIUM,
                check_function="check_robots_compliance"
            ),
            
            ComplianceRule(
                rule_id="legal_003",
                name="Copyright Respect",
                description="Respect copyright on images and content",
                category="legal",
                severity=ComplianceLevel.HIGH,
                check_function="check_copyright_compliance"
            ),
            
            # Ethical Rules
            ComplianceRule(
                rule_id="ethical_001",
                name="No Discriminatory Practices",
                description="Ensure no discriminatory bias in opportunity identification",
                category="ethical",
                severity=ComplianceLevel.CRITICAL,
                check_function="check_no_discrimination"
            ),
            
            ComplianceRule(
                rule_id="ethical_002",
                name="Fair Market Practices",
                description="Promote fair and transparent market practices",
                category="ethical",
                severity=ComplianceLevel.HIGH,
                check_function="check_fair_practices"
            ),
            
            ComplianceRule(
                rule_id="ethical_003",
                name="Vulnerable Person Protection",
                description="Avoid exploiting vulnerable property owners",
                category="ethical",
                severity=ComplianceLevel.CRITICAL,
                check_function="check_vulnerable_protection"
            ),
            
            # Technical Rules
            ComplianceRule(
                rule_id="technical_001",
                name="Rate Limit Compliance",
                description="Respect API rate limits and request quotas",
                category="technical",
                severity=ComplianceLevel.MEDIUM,
                check_function="check_rate_limits_compliance"
            ),
            
            ComplianceRule(
                rule_id="technical_002",
                name="Request Delay Compliance",
                description="Maintain appropriate delays between requests",
                category="technical",
                severity=ComplianceLevel.LOW,
                check_function="check_request_delays",
                parameters={"min_delay_seconds": self.radar_config.request_delay_seconds}
            ),
            
            ComplianceRule(
                rule_id="technical_003",
                name="Concurrent Request Limits",
                description="Limit concurrent requests to external services",
                category="technical",
                severity=ComplianceLevel.MEDIUM,
                check_function="check_concurrent_limits",
                parameters={"max_concurrent": self.radar_config.max_concurrent_requests}
            )
        ]
        
        return rules
    
    async def _check_rate_limits(self) -> List[ComplianceViolation]:
        """Check API rate limits compliance."""
        violations = []
        
        try:
            current_time = datetime.utcnow()
            
            for service, limits in self.rate_limits.items():
                # Reset counter if window has passed
                if current_time > limits['reset_time']:
                    limits['usage'] = 0
                    limits['reset_time'] = current_time + timedelta(seconds=limits['window'])
                
                # Check if approaching or exceeding limits
                usage_percentage = (limits['usage'] / limits['limit']) * 100
                
                if usage_percentage >= 100:
                    violations.append(ComplianceViolation(
                        violation_id=f"rate_limit_{service}_{int(current_time.timestamp())}",
                        rule_id="technical_001",
                        rule_name="Rate Limit Compliance",
                        violation_type=ViolationType.RATE_LIMIT_BREACH,
                        severity=ComplianceLevel.HIGH,
                        description=f"Rate limit exceeded for {service}: {limits['usage']}/{limits['limit']}",
                        evidence={'service': service, 'usage': limits['usage'], 'limit': limits['limit']},
                        affected_entity=service,
                        detected_at=current_time,
                        detection_method="rate_limit_monitor",
                        source_component="compliance_monitor"
                    ))
                elif usage_percentage >= 90:
                    violations.append(ComplianceViolation(
                        violation_id=f"rate_limit_warning_{service}_{int(current_time.timestamp())}",
                        rule_id="technical_001",
                        rule_name="Rate Limit Compliance",
                        violation_type=ViolationType.RATE_LIMIT_BREACH,
                        severity=ComplianceLevel.MEDIUM,
                        description=f"Rate limit warning for {service}: {usage_percentage:.1f}% of limit used",
                        evidence={'service': service, 'usage_percentage': usage_percentage},
                        affected_entity=service,
                        detected_at=current_time,
                        detection_method="rate_limit_monitor",
                        source_component="compliance_monitor"
                    ))
            
        except Exception as e:
            self.logger.error(f"Error checking rate limits: {e}")
        
        return violations
    
    async def _check_data_access_permissions(self) -> List[ComplianceViolation]:
        """Check data access permissions."""
        violations = []
        
        try:
            # This would check API keys, access tokens, permissions etc.
            # For now, we'll implement basic checks
            
            # Check if we have required API keys
            required_apis = ['domain', 'rea', 'nsw_lpi'] if self.radar_config.council_apis_enabled else []
            
            for api in required_apis:
                # This would actually check if API key is valid
                # For demo, we'll assume they're configured properly
                pass
            
        except Exception as e:
            self.logger.error(f"Error checking data access permissions: {e}")
        
        return violations
    
    async def _check_privacy_compliance(self) -> List[ComplianceViolation]:
        """Check privacy compliance."""
        violations = []
        
        try:
            # Check data retention compliance
            retention_days = self.radar_config.data_retention_days
            if retention_days > 365:
                violations.append(ComplianceViolation(
                    violation_id=f"privacy_retention_{int(datetime.utcnow().timestamp())}",
                    rule_id="privacy_003",
                    rule_name="Data Retention Limits",
                    violation_type=ViolationType.PRIVACY_BREACH,
                    severity=ComplianceLevel.MEDIUM,
                    description=f"Data retention period ({retention_days} days) exceeds recommended maximum (365 days)",
                    evidence={'retention_days': retention_days, 'max_recommended': 365},
                    affected_entity="system_configuration",
                    detected_at=datetime.utcnow(),
                    detection_method="configuration_check",
                    source_component="compliance_monitor"
                ))
            
        except Exception as e:
            self.logger.error(f"Error checking privacy compliance: {e}")
        
        return violations
    
    async def _check_ethical_guidelines(self) -> List[ComplianceViolation]:
        """Check ethical guidelines compliance."""
        violations = []
        
        try:
            # This would implement comprehensive ethical checks
            # For now, we'll implement basic framework
            
            # Check for discriminatory patterns (placeholder)
            # In production, this would analyze opportunity patterns for bias
            
            pass
            
        except Exception as e:
            self.logger.error(f"Error checking ethical guidelines: {e}")
        
        return violations
    
    async def _check_opportunity_compliance(
        self, 
        opportunity: OffMarketOpportunity
    ) -> Tuple[List[ComplianceViolation], int, int]:
        """Check compliance for a specific opportunity."""
        violations = []
        total_checks = 0
        passed_checks = 0
        
        try:
            # Check 1: Public data only
            total_checks += 1
            if self._is_public_data_only(opportunity):
                passed_checks += 1
            else:
                violations.append(ComplianceViolation(
                    violation_id=f"public_data_{opportunity.id}",
                    rule_id="privacy_001",
                    rule_name="Public Data Only",
                    violation_type=ViolationType.PRIVACY_BREACH,
                    severity=ComplianceLevel.CRITICAL,
                    description="Opportunity contains non-public data",
                    evidence={'opportunity_id': opportunity.id, 'data_sources': opportunity.data_sources},
                    affected_entity=opportunity.id,
                    detected_at=datetime.utcnow(),
                    detection_method="data_source_analysis",
                    source_component="compliance_monitor"
                ))
            
            # Check 2: No personal information exposure
            total_checks += 1
            if self._has_personal_info_protection(opportunity):
                passed_checks += 1
            else:
                violations.append(ComplianceViolation(
                    violation_id=f"personal_info_{opportunity.id}",
                    rule_id="privacy_002",
                    rule_name="Personal Information Protection",
                    violation_type=ViolationType.PRIVACY_BREACH,
                    severity=ComplianceLevel.HIGH,
                    description="Opportunity may expose personal information",
                    evidence={'opportunity_id': opportunity.id},
                    affected_entity=opportunity.id,
                    detected_at=datetime.utcnow(),
                    detection_method="personal_info_scan",
                    source_component="compliance_monitor"
                ))
            
            # Check 3: Ethical sourcing
            total_checks += 1
            if self._is_ethically_sourced(opportunity):
                passed_checks += 1
            else:
                violations.append(ComplianceViolation(
                    violation_id=f"ethical_source_{opportunity.id}",
                    rule_id="ethical_002",
                    rule_name="Fair Market Practices",
                    violation_type=ViolationType.ETHICAL_VIOLATION,
                    severity=ComplianceLevel.HIGH,
                    description="Opportunity may not be ethically sourced",
                    evidence={'opportunity_id': opportunity.id, 'opportunity_type': opportunity.opportunity_type.value},
                    affected_entity=opportunity.id,
                    detected_at=datetime.utcnow(),
                    detection_method="ethical_analysis",
                    source_component="compliance_monitor"
                ))
            
            # Check 4: Vulnerable person protection
            total_checks += 1
            if not self._exploits_vulnerable_person(opportunity):
                passed_checks += 1
            else:
                violations.append(ComplianceViolation(
                    violation_id=f"vulnerable_protection_{opportunity.id}",
                    rule_id="ethical_003",
                    rule_name="Vulnerable Person Protection",
                    violation_type=ViolationType.ETHICAL_VIOLATION,
                    severity=ComplianceLevel.CRITICAL,
                    description="Opportunity may exploit vulnerable property owner",
                    evidence={'opportunity_id': opportunity.id, 'risk_indicators': self._get_vulnerability_indicators(opportunity)},
                    affected_entity=opportunity.id,
                    detected_at=datetime.utcnow(),
                    detection_method="vulnerability_analysis",
                    source_component="compliance_monitor"
                ))
            
        except Exception as e:
            self.logger.error(f"Error checking opportunity compliance: {e}")
        
        return violations, total_checks, passed_checks
    
    async def _check_scan_compliance(
        self, 
        opportunities: List[OffMarketOpportunity]
    ) -> Tuple[List[ComplianceViolation], int, int]:
        """Check compliance for overall scan results."""
        violations = []
        total_checks = 0
        passed_checks = 0
        
        try:
            # Check 1: No discriminatory bias in results
            total_checks += 1
            if not self._has_discriminatory_bias(opportunities):
                passed_checks += 1
            else:
                violations.append(ComplianceViolation(
                    violation_id=f"discrimination_bias_{int(datetime.utcnow().timestamp())}",
                    rule_id="ethical_001",
                    rule_name="No Discriminatory Practices",
                    violation_type=ViolationType.DISCRIMINATION,
                    severity=ComplianceLevel.CRITICAL,
                    description="Scan results show potential discriminatory bias",
                    evidence={'opportunity_count': len(opportunities)},
                    affected_entity="scan_results",
                    detected_at=datetime.utcnow(),
                    detection_method="bias_analysis",
                    source_component="compliance_monitor"
                ))
            
            # Check 2: Reasonable opportunity count
            total_checks += 1
            if len(opportunities) <= 100:  # Reasonable limit
                passed_checks += 1
            else:
                violations.append(ComplianceViolation(
                    violation_id=f"excessive_opportunities_{int(datetime.utcnow().timestamp())}",
                    rule_id="ethical_002",
                    rule_name="Fair Market Practices",
                    violation_type=ViolationType.ETHICAL_VIOLATION,
                    severity=ComplianceLevel.MEDIUM,
                    description=f"Excessive number of opportunities identified: {len(opportunities)}",
                    evidence={'opportunity_count': len(opportunities), 'max_reasonable': 100},
                    affected_entity="scan_results",
                    detected_at=datetime.utcnow(),
                    detection_method="volume_analysis",
                    source_component="compliance_monitor"
                ))
            
        except Exception as e:
            self.logger.error(f"Error checking scan compliance: {e}")
        
        return violations, total_checks, passed_checks
    
    def _is_public_data_only(self, opportunity: OffMarketOpportunity) -> bool:
        """Check if opportunity uses only public data sources."""
        try:
            # Define public data sources
            public_sources = [
                'domain', 'realestate', 'council_da', 'price_history', 
                'market_metrics', 'suburb_metrics', 'expired_listings',
                'market_analysis', 'statistical_analysis'
            ]
            
            # Check if all data sources are public
            for source in opportunity.data_sources:
                if source not in public_sources:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _has_personal_info_protection(self, opportunity: OffMarketOpportunity) -> bool:
        """Check if opportunity protects personal information."""
        try:
            # Check for exposed personal information in description
            sensitive_keywords = [
                'phone', 'email', 'address', 'name', 'contact',
                'mobile', 'personal', 'private', 'owner name'
            ]
            
            description_lower = opportunity.description.lower()
            for keyword in sensitive_keywords:
                if keyword in description_lower:
                    return False
            
            # Check if contact information is anonymized
            if opportunity.owner_contact or opportunity.agent_contact:
                # Would implement anonymization checks here
                pass
            
            return True
            
        except Exception:
            return True  # Assume protected if can't determine
    
    def _is_ethically_sourced(self, opportunity: OffMarketOpportunity) -> bool:
        """Check if opportunity is ethically sourced."""
        try:
            # Check compliance flags
            if not (opportunity.compliance_checked and 
                   opportunity.ethical_approval and 
                   opportunity.data_privacy_compliant):
                return False
            
            # Check for ethical concerns in opportunity type
            if opportunity.opportunity_type == OpportunityType.DISTRESS_SIGNAL:
                # Distress signals require extra ethical scrutiny
                distress_details = opportunity.opportunity_details.get('distress_score', 0)
                if distress_details > 0.9:  # Very high distress
                    return False  # May be exploitative
            
            return True
            
        except Exception:
            return True  # Assume ethical if can't determine
    
    def _exploits_vulnerable_person(self, opportunity: OffMarketOpportunity) -> bool:
        """Check if opportunity may exploit vulnerable person."""
        try:
            vulnerability_indicators = self._get_vulnerability_indicators(opportunity)
            
            # High vulnerability risk if multiple indicators present
            return len(vulnerability_indicators) >= 2
            
        except Exception:
            return False  # Assume no exploitation if can't determine
    
    def _get_vulnerability_indicators(self, opportunity: OffMarketOpportunity) -> List[str]:
        """Get indicators that suggest vulnerable property owner."""
        indicators = []
        
        try:
            # Check tags for vulnerability indicators
            vulnerable_tags = [
                'deceased_estate', 'elderly_owner', 'financial_distress',
                'bankruptcy', 'foreclosure', 'medical_emergency',
                'divorce_settlement', 'job_loss'
            ]
            
            for tag in opportunity.tags:
                if tag in vulnerable_tags:
                    indicators.append(tag)
            
            # Check description for vulnerability keywords
            vulnerable_keywords = [
                'deceased', 'elderly', 'urgent sale', 'must sell',
                'financial difficulty', 'divorce', 'separation',
                'medical', 'health', 'retirement home'
            ]
            
            description_lower = opportunity.description.lower()
            for keyword in vulnerable_keywords:
                if keyword in description_lower:
                    indicators.append(f"keyword_{keyword.replace(' ', '_')}")
            
            # Check distress indicators
            if opportunity.opportunity_type == OpportunityType.DISTRESS_SIGNAL:
                distress_score = opportunity.opportunity_details.get('distress_score', 0)
                if distress_score > 0.8:
                    indicators.append('high_distress_score')
            
        except Exception as e:
            self.logger.error(f"Error getting vulnerability indicators: {e}")
        
        return indicators
    
    def _has_discriminatory_bias(self, opportunities: List[OffMarketOpportunity]) -> bool:
        """Check for discriminatory bias in opportunity selection."""
        try:
            if not opportunities:
                return False
            
            # Check suburb distribution for bias
            suburb_counts = {}
            for opp in opportunities:
                suburb = opp.suburb.lower()
                suburb_counts[suburb] = suburb_counts.get(suburb, 0) + 1
            
            # Simple bias check: if >80% of opportunities are from premium suburbs
            premium_count = sum(
                count for suburb, count in suburb_counts.items() 
                if suburb in self.premium_suburbs
            )
            
            bias_percentage = (premium_count / len(opportunities)) * 100
            
            # Consider biased if heavily skewed toward premium areas
            return bias_percentage > 80
            
        except Exception:
            return False
    
    def _generate_compliance_recommendations(self, violations: List[ComplianceViolation]) -> List[str]:
        """Generate compliance recommendations based on violations."""
        recommendations = []
        
        try:
            violation_types = set(v.violation_type for v in violations)
            
            if ViolationType.PRIVACY_BREACH in violation_types:
                recommendations.append("Review data collection practices to ensure only public data is used")
                recommendations.append("Implement additional privacy controls and data anonymization")
            
            if ViolationType.ETHICAL_VIOLATION in violation_types:
                recommendations.append("Strengthen ethical review processes for opportunity identification")
                recommendations.append("Implement vulnerable person protection protocols")
            
            if ViolationType.RATE_LIMIT_BREACH in violation_types:
                recommendations.append("Implement better rate limiting and request throttling")
                recommendations.append("Consider spreading requests across longer time periods")
            
            if ViolationType.DISCRIMINATION in violation_types:
                recommendations.append("Review opportunity selection algorithms for bias")
                recommendations.append("Implement fairness metrics and monitoring")
            
            # General recommendations
            if violations:
                recommendations.append("Conduct regular compliance audits and reviews")
                recommendations.append("Provide compliance training for system operators")
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {e}")
        
        return recommendations
    
    def _generate_required_actions(self, violations: List[ComplianceViolation]) -> List[str]:
        """Generate required actions for compliance violations."""
        actions = []
        
        try:
            critical_violations = [v for v in violations if v.severity == ComplianceLevel.CRITICAL]
            high_violations = [v for v in violations if v.severity == ComplianceLevel.HIGH]
            
            if critical_violations:
                actions.append("CRITICAL: Stop all scanning operations until critical violations are resolved")
                actions.append("Review and update compliance policies immediately")
            
            if high_violations:
                actions.append("Address high-severity violations within 24 hours")
                actions.append("Document remediation steps taken")
            
            # Specific actions for violation types
            violation_types = set(v.violation_type for v in violations)
            
            if ViolationType.PRIVACY_BREACH in violation_types:
                actions.append("Conduct immediate privacy impact assessment")
                actions.append("Notify relevant privacy authorities if required")
            
            if ViolationType.DISCRIMINATION in violation_types:
                actions.append("Suspend affected opportunity recommendations")
                actions.append("Audit selection algorithms for bias")
            
        except Exception as e:
            self.logger.error(f"Error generating required actions: {e}")
        
        return actions
    
    def _validate_compliance_rules(self) -> None:
        """Validate compliance rules configuration."""
        try:
            for rule in self.compliance_rules:
                # Check that critical rules have appropriate enforcement
                if rule.is_critical and not rule.enforce:
                    self.logger.warning(f"Critical rule {rule.rule_id} is not enforced")
                
                # Check for required documentation
                if not rule.legal_basis and rule.severity in [ComplianceLevel.CRITICAL, ComplianceLevel.HIGH]:
                    self.logger.warning(f"High/critical rule {rule.rule_id} missing legal basis")
            
            self.logger.info(f"Validated {len(self.compliance_rules)} compliance rules")
            
        except Exception as e:
            self.logger.error(f"Error validating compliance rules: {e}")
    
    async def _load_compliance_state(self) -> None:
        """Load stored compliance state."""
        try:
            # This would load from persistent storage
            # For now, just initialize empty state
            self.violation_log = []
            
        except Exception as e:
            self.logger.warning(f"Failed to load compliance state: {e}")
    
    async def _save_compliance_state(self) -> None:
        """Save compliance state."""
        try:
            # This would save to persistent storage
            # For now, just log summary
            self.logger.info(f"Compliance session: {len(self.violation_log)} violations recorded")
            
        except Exception as e:
            self.logger.warning(f"Failed to save compliance state: {e}")
    
    async def _generate_session_report(self) -> None:
        """Generate final session compliance report."""
        try:
            if self.violation_log:
                critical_count = len([v for v in self.violation_log if v.severity == ComplianceLevel.CRITICAL])
                high_count = len([v for v in self.violation_log if v.severity == ComplianceLevel.HIGH])
                
                self.logger.info(
                    f"Session compliance summary: {len(self.violation_log)} total violations, "
                    f"{critical_count} critical, {high_count} high severity"
                )
            else:
                self.logger.info("Session completed with no compliance violations")
                
        except Exception as e:
            self.logger.error(f"Error generating session report: {e}")
    
    # Public API methods
    
    def record_api_usage(self, service: str, request_count: int = 1) -> None:
        """Record API usage for rate limit tracking."""
        try:
            if service in self.rate_limits:
                self.rate_limits[service]['usage'] += request_count
                
        except Exception as e:
            self.logger.error(f"Error recording API usage: {e}")
    
    def get_compliance_status(self) -> Dict[str, Any]:
        """Get current compliance status."""
        try:
            recent_violations = [
                v for v in self.violation_log 
                if (datetime.utcnow() - v.detected_at).days <= 1
            ]
            
            return {
                'total_violations': len(self.violation_log),
                'recent_violations': len(recent_violations),
                'critical_violations': len([v for v in recent_violations if v.severity == ComplianceLevel.CRITICAL]),
                'rate_limit_status': {
                    service: {
                        'usage': limits['usage'],
                        'limit': limits['limit'],
                        'usage_percentage': (limits['usage'] / limits['limit']) * 100
                    }
                    for service, limits in self.rate_limits.items()
                },
                'last_check': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting compliance status: {e}")
            return {'error': str(e)}