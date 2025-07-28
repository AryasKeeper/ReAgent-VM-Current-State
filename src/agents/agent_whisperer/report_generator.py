"""
ReAgent Sydney - Report Generator

Professional report generation system for creating comprehensive, actionable 
market intelligence reports for real estate agents and their clients.

Core Capabilities:
- Market analysis reports for suburbs and regions
- Buyer matching reports with property recommendations
- Seller strategy documents with pricing and timing guidance
- Investment analysis reports with ROI projections
- Custom reports based on multi-agent intelligence
- Professional formatting suitable for client presentation
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid
from decimal import Decimal

# For production, you'd use more sophisticated libraries like:
# from jinja2 import Template, Environment, FileSystemLoader
# from weasyprint import HTML, CSS
# from matplotlib import pyplot as plt
# import seaborn as sns


class ReportType(str, Enum):
    """Types of reports that can be generated."""
    
    MARKET_ANALYSIS = "market_analysis"
    BUYER_MATCHING = "buyer_matching"
    SELLER_STRATEGY = "seller_strategy"
    INVESTMENT_ANALYSIS = "investment_analysis"
    OFF_MARKET_SUMMARY = "off_market_summary"
    SUBURB_COMPARISON = "suburb_comparison"
    CUSTOM_REPORT = "custom_report"


class ReportFormat(str, Enum):
    """Available report output formats."""
    
    HTML = "html"
    PDF = "pdf"
    JSON = "json"
    MARKDOWN = "markdown"
    EMAIL_FRIENDLY = "email_friendly"


class ReportStatus(str, Enum):
    """Report generation status."""
    
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """Individual section within a report."""
    
    title: str
    content: str
    section_type: str = "text"  # text, chart, table, list
    data: Optional[Dict[str, Any]] = None
    order: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "section_type": self.section_type,
            "data": self.data,
            "order": self.order,
            "metadata": self.metadata
        }


@dataclass
class ReportTemplate:
    """Template definition for report generation."""
    
    template_id: str
    name: str
    description: str
    report_type: ReportType
    sections: List[Dict[str, Any]] = field(default_factory=list)
    required_data: List[str] = field(default_factory=list)
    optional_data: List[str] = field(default_factory=list)
    formatting_options: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "report_type": self.report_type.value,
            "sections": self.sections,
            "required_data": self.required_data,
            "optional_data": self.optional_data,
            "formatting_options": self.formatting_options
        }


@dataclass
class GeneratedReport:
    """A generated report with all its content and metadata."""
    
    report_id: str
    report_type: ReportType
    title: str
    generated_at: datetime
    generated_for: str  # User ID or agent name
    
    # Content
    sections: List[ReportSection] = field(default_factory=list)
    executive_summary: str = ""
    key_insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Data sources and quality
    data_sources: List[str] = field(default_factory=list)
    data_quality_score: float = 0.0
    confidence_level: str = "medium"
    
    # Report metadata
    parameters: Dict[str, Any] = field(default_factory=dict)
    generation_time: float = 0.0
    template_used: Optional[str] = None
    
    # Export options
    available_formats: List[ReportFormat] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "title": self.title,
            "generated_at": self.generated_at.isoformat(),
            "generated_for": self.generated_for,
            "sections": [section.to_dict() for section in self.sections],
            "executive_summary": self.executive_summary,
            "key_insights": self.key_insights,
            "recommendations": self.recommendations,
            "data_sources": self.data_sources,
            "data_quality_score": self.data_quality_score,
            "confidence_level": self.confidence_level,
            "parameters": self.parameters,
            "generation_time": self.generation_time,
            "template_used": self.template_used,
            "available_formats": [fmt.value for fmt in self.available_formats]
        }
    
    def add_section(self, title: str, content: str, section_type: str = "text", 
                   data: Optional[Dict[str, Any]] = None, order: int = None) -> ReportSection:
        """Add a new section to the report."""
        
        if order is None:
            order = len(self.sections)
        
        section = ReportSection(
            title=title,
            content=content,
            section_type=section_type,
            data=data,
            order=order
        )
        
        self.sections.append(section)
        return section
    
    def get_section(self, title: str) -> Optional[ReportSection]:
        """Get a section by title."""
        for section in self.sections:
            if section.title == title:
                return section
        return None
    
    def sort_sections(self) -> None:
        """Sort sections by their order value."""
        self.sections.sort(key=lambda s: s.order)


class ReportGenerator:
    """
    Professional report generation system for ReAgent Sydney.
    
    Creates comprehensive, well-formatted reports that combine data from multiple
    agents into actionable insights for real estate professionals.
    """
    
    def __init__(self, cache_manager=None, logger=None):
        self.cache_manager = cache_manager
        self.logger = logger
        
        # Report templates
        self.templates: Dict[str, ReportTemplate] = {}
        
        # Generation statistics
        self.generation_stats = {
            "total_reports": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "avg_generation_time": 0.0,
            "reports_by_type": {},
            "avg_data_quality": 0.0
        }
        
        # Active generations
        self.active_generations: Dict[str, Dict[str, Any]] = {}
    
    async def initialize(self) -> None:
        """Initialize the report generator with templates and resources."""
        
        if self.logger:
            self.logger.info("Initializing Report Generator...")
        
        # Load report templates
        await self._load_report_templates()
        
        # Initialize any required resources (chart libraries, formatting tools, etc.)
        # In production, this would set up matplotlib, weasyprint, etc.
        
        if self.logger:
            self.logger.info(f"Report Generator initialized with {len(self.templates)} templates")
    
    async def cleanup(self) -> None:
        """Cleanup report generator resources."""
        
        # Save any pending reports
        if self.active_generations:
            if self.logger:
                self.logger.info(f"Cleaning up {len(self.active_generations)} active generations")
    
    async def generate_report(
        self,
        report_type: ReportType,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        template_id: Optional[str] = None,
        generated_for: str = "system"
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive report based on the specified type and parameters.
        
        Args:
            report_type: Type of report to generate
            parameters: Parameters and data for report generation
            context: Additional context from conversation or user preferences
            template_id: Specific template to use (optional)
            generated_for: Who the report is being generated for
            
        Returns:
            Dictionary containing the generated report data
        """
        
        start_time = datetime.utcnow()
        report_id = str(uuid.uuid4())
        
        try:
            self.generation_stats["total_reports"] += 1
            
            # Track active generation
            self.active_generations[report_id] = {
                "report_type": report_type,
                "status": ReportStatus.GENERATING,
                "started_at": start_time,
                "parameters": parameters
            }
            
            if self.logger:
                self.logger.info(f"Starting report generation: {report_type.value} (ID: {report_id})")
            
            # Select template
            template = self._select_template(report_type, template_id)
            
            # Generate report based on type
            if report_type == ReportType.MARKET_ANALYSIS:
                report = await self._generate_market_analysis_report(
                    report_id, parameters, context, template, generated_for
                )
            elif report_type == ReportType.BUYER_MATCHING:
                report = await self._generate_buyer_matching_report(
                    report_id, parameters, context, template, generated_for
                )
            elif report_type == ReportType.SELLER_STRATEGY:
                report = await self._generate_seller_strategy_report(
                    report_id, parameters, context, template, generated_for
                )
            elif report_type == ReportType.INVESTMENT_ANALYSIS:
                report = await self._generate_investment_analysis_report(
                    report_id, parameters, context, template, generated_for
                )
            elif report_type == ReportType.OFF_MARKET_SUMMARY:
                report = await self._generate_off_market_summary_report(
                    report_id, parameters, context, template, generated_for
                )
            else:
                report = await self._generate_custom_report(
                    report_id, parameters, context, template, generated_for
                )
            
            # Calculate generation time
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            report.generation_time = generation_time
            
            # Update statistics
            self.generation_stats["successful_generations"] += 1
            self._update_generation_stats(report_type, generation_time)
            
            # Clean up active generation
            if report_id in self.active_generations:
                del self.active_generations[report_id]
            
            if self.logger:
                self.logger.info(f"Report generated successfully in {generation_time:.2f}s: {report_id}")
            
            return report.to_dict()
            
        except Exception as e:
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            
            self.generation_stats["failed_generations"] += 1
            
            # Update active generation status
            if report_id in self.active_generations:
                self.active_generations[report_id]["status"] = ReportStatus.FAILED
                self.active_generations[report_id]["error"] = str(e)
            
            if self.logger:
                self.logger.error(f"Report generation failed for {report_id}: {e}", exc_info=True)
            
            # Return error report
            error_report = GeneratedReport(
                report_id=report_id,
                report_type=report_type,
                title=f"Report Generation Failed",
                generated_at=datetime.utcnow(),
                generated_for=generated_for,
                parameters=parameters,
                generation_time=generation_time
            )
            
            error_report.add_section(
                title="Error",
                content=f"Failed to generate {report_type.value} report: {str(e)}",
                section_type="error"
            )
            
            return error_report.to_dict()
    
    async def generate_custom_report(
        self,
        title: str,
        data: Dict[str, Any],
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        generated_for: str = "system"
    ) -> Dict[str, Any]:
        """Generate a custom report with provided data and structure."""
        
        report_id = str(uuid.uuid4())
        
        report = GeneratedReport(
            report_id=report_id,
            report_type=ReportType.CUSTOM_REPORT,
            title=title,
            generated_at=datetime.utcnow(),
            generated_for=generated_for,
            parameters=parameters
        )
        
        # Process the provided data into report sections
        if "summary" in data:
            report.executive_summary = data["summary"]
        
        if "insights" in data:
            report.key_insights = data["insights"]
        
        if "recommendations" in data:
            report.recommendations = data["recommendations"]
        
        if "sections" in data:
            for section_data in data["sections"]:
                report.add_section(
                    title=section_data.get("title", "Section"),
                    content=section_data.get("content", ""),
                    section_type=section_data.get("type", "text"),
                    data=section_data.get("data")
                )
        
        # Add data sources
        if "data_sources" in data:
            report.data_sources = data["data_sources"]
        
        # Set quality metrics
        report.data_quality_score = data.get("quality_score", 0.8)
        report.confidence_level = data.get("confidence_level", "medium")
        
        # Add available formats
        report.available_formats = [
            ReportFormat.HTML, ReportFormat.JSON, ReportFormat.EMAIL_FRIENDLY
        ]
        
        return report.to_dict()
    
    async def _load_report_templates(self) -> None:
        """Load report templates for different report types."""
        
        # Market Analysis Template
        market_analysis_template = ReportTemplate(
            template_id="market_analysis_v1",
            name="Market Analysis Report",
            description="Comprehensive market analysis for a specific suburb or region",
            report_type=ReportType.MARKET_ANALYSIS,
            sections=[
                {"title": "Executive Summary", "type": "text", "required": True},
                {"title": "Market Overview", "type": "text", "required": True},
                {"title": "Price Trends", "type": "chart", "required": True},
                {"title": "Sales Activity", "type": "table", "required": True},
                {"title": "Market Comparison", "type": "table", "required": False},
                {"title": "Key Insights", "type": "list", "required": True},
                {"title": "Recommendations", "type": "list", "required": True}
            ],
            required_data=["suburb", "price_data", "sales_data"],
            optional_data=["comparison_suburbs", "demographic_data"]
        )
        
        # Buyer Matching Template
        buyer_matching_template = ReportTemplate(
            template_id="buyer_matching_v1",
            name="Buyer Matching Report",
            description="Property recommendations and buyer matching analysis",
            report_type=ReportType.BUYER_MATCHING,
            sections=[
                {"title": "Buyer Profile", "type": "text", "required": True},
                {"title": "Recommended Properties", "type": "table", "required": True},
                {"title": "Match Analysis", "type": "text", "required": True},
                {"title": "Market Opportunities", "type": "list", "required": True},
                {"title": "Next Steps", "type": "list", "required": True}
            ],
            required_data=["buyer_criteria", "matching_properties"],
            optional_data=["market_trends", "similar_buyers"]
        )
        
        # Seller Strategy Template
        seller_strategy_template = ReportTemplate(
            template_id="seller_strategy_v1",
            name="Seller Strategy Report",
            description="Comprehensive selling strategy with pricing and timing recommendations",
            report_type=ReportType.SELLER_STRATEGY,
            sections=[
                {"title": "Property Overview", "type": "text", "required": True},
                {"title": "Market Position", "type": "text", "required": True},
                {"title": "Pricing Strategy", "type": "text", "required": True},
                {"title": "Comparable Sales", "type": "table", "required": True},
                {"title": "Marketing Recommendations", "type": "list", "required": True},
                {"title": "Timing Analysis", "type": "text", "required": True},
                {"title": "Expected Outcomes", "type": "text", "required": True}
            ],
            required_data=["property_details", "comparable_sales", "market_data"],
            optional_data=["renovation_suggestions", "staging_advice"]
        )
        
        # Investment Analysis Template
        investment_template = ReportTemplate(
            template_id="investment_analysis_v1",
            name="Investment Analysis Report",
            description="ROI analysis and investment potential assessment",
            report_type=ReportType.INVESTMENT_ANALYSIS,
            sections=[
                {"title": "Investment Summary", "type": "text", "required": True},
                {"title": "Financial Analysis", "type": "table", "required": True},
                {"title": "Market Growth Potential", "type": "chart", "required": True},
                {"title": "Risk Assessment", "type": "text", "required": True},
                {"title": "Rental Yield Analysis", "type": "table", "required": True},
                {"title": "Investment Recommendations", "type": "list", "required": True}
            ],
            required_data=["property_financials", "market_projections"],
            optional_data=["rental_data", "development_plans"]
        )
        
        # Store templates
        self.templates = {
            ReportType.MARKET_ANALYSIS: market_analysis_template,
            ReportType.BUYER_MATCHING: buyer_matching_template,
            ReportType.SELLER_STRATEGY: seller_strategy_template,
            ReportType.INVESTMENT_ANALYSIS: investment_template
        }
    
    def _select_template(self, report_type: ReportType, template_id: Optional[str] = None) -> Optional[ReportTemplate]:
        """Select the appropriate template for report generation."""
        
        if template_id:
            # Look for specific template by ID
            for template in self.templates.values():
                if template.template_id == template_id:
                    return template
        
        # Use default template for report type
        return self.templates.get(report_type)
    
    async def _generate_market_analysis_report(
        self,
        report_id: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        template: Optional[ReportTemplate],
        generated_for: str
    ) -> GeneratedReport:
        """Generate a comprehensive market analysis report."""
        
        suburb = parameters.get("suburb", "Unknown Suburb")
        
        report = GeneratedReport(
            report_id=report_id,
            report_type=ReportType.MARKET_ANALYSIS,
            title=f"Market Analysis Report - {suburb}",
            generated_at=datetime.utcnow(),
            generated_for=generated_for,
            parameters=parameters,
            template_used=template.template_id if template else None
        )
        
        # Executive Summary
        report.executive_summary = self._generate_market_executive_summary(suburb, parameters)
        
        # Market Overview Section
        market_overview = self._generate_market_overview(suburb, parameters)
        report.add_section(
            title="Market Overview",
            content=market_overview,
            section_type="text",
            order=1
        )
        
        # Price Trends Section
        price_trends_content, price_trends_data = self._generate_price_trends_section(suburb, parameters)
        report.add_section(
            title="Price Trends",
            content=price_trends_content,
            section_type="chart",
            data=price_trends_data,
            order=2
        )
        
        # Sales Activity Section
        sales_content, sales_data = self._generate_sales_activity_section(suburb, parameters)
        report.add_section(
            title="Sales Activity",
            content=sales_content,
            section_type="table",
            data=sales_data,
            order=3
        )
        
        # Key Insights
        report.key_insights = self._generate_market_insights(suburb, parameters)
        
        # Recommendations
        report.recommendations = self._generate_market_recommendations(suburb, parameters)
        
        # Set data sources and quality
        report.data_sources = ["Domain API", "REA Data", "CoreLogic", "Recent Sales Records"]
        report.data_quality_score = 0.85
        report.confidence_level = "high"
        
        # Available formats
        report.available_formats = [
            ReportFormat.HTML, ReportFormat.PDF, ReportFormat.JSON, ReportFormat.EMAIL_FRIENDLY
        ]
        
        return report
    
    async def _generate_buyer_matching_report(
        self,
        report_id: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        template: Optional[ReportTemplate],
        generated_for: str
    ) -> GeneratedReport:
        """Generate a buyer matching report with property recommendations."""
        
        buyer_criteria = parameters.get("buyer_criteria", {})
        
        report = GeneratedReport(
            report_id=report_id,
            report_type=ReportType.BUYER_MATCHING,
            title=f"Buyer Matching Report - {buyer_criteria.get('property_type', 'Property')} Search",
            generated_at=datetime.utcnow(),
            generated_for=generated_for,
            parameters=parameters,
            template_used=template.template_id if template else None
        )
        
        # Executive Summary
        report.executive_summary = self._generate_buyer_executive_summary(buyer_criteria)
        
        # Buyer Profile Section
        buyer_profile = self._generate_buyer_profile_section(buyer_criteria)
        report.add_section(
            title="Buyer Profile",
            content=buyer_profile,
            section_type="text",
            order=1
        )
        
        # Recommended Properties Section
        properties_content, properties_data = self._generate_recommended_properties_section(buyer_criteria)
        report.add_section(
            title="Recommended Properties",
            content=properties_content,
            section_type="table",
            data=properties_data,
            order=2
        )
        
        # Match Analysis Section
        match_analysis = self._generate_match_analysis_section(buyer_criteria)
        report.add_section(
            title="Match Analysis",
            content=match_analysis,
            section_type="text",
            order=3
        )
        
        # Key Insights
        report.key_insights = self._generate_buyer_insights(buyer_criteria)
        
        # Recommendations
        report.recommendations = self._generate_buyer_recommendations(buyer_criteria)
        
        # Set metadata
        report.data_sources = ["Property Listings", "Buyer Database", "Market Analysis"]
        report.data_quality_score = 0.82
        report.confidence_level = "high"
        report.available_formats = [ReportFormat.HTML, ReportFormat.PDF, ReportFormat.EMAIL_FRIENDLY]
        
        return report
    
    async def _generate_seller_strategy_report(
        self,
        report_id: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        template: Optional[ReportTemplate],
        generated_for: str
    ) -> GeneratedReport:
        """Generate a comprehensive seller strategy report."""
        
        property_details = parameters.get("property_details", {})
        address = property_details.get("address", "Property")
        
        report = GeneratedReport(
            report_id=report_id,
            report_type=ReportType.SELLER_STRATEGY,
            title=f"Seller Strategy Report - {address}",
            generated_at=datetime.utcnow(),
            generated_for=generated_for,
            parameters=parameters,
            template_used=template.template_id if template else None
        )
        
        # Executive Summary
        report.executive_summary = self._generate_seller_executive_summary(property_details)
        
        # Property Overview
        property_overview = self._generate_property_overview_section(property_details)
        report.add_section(
            title="Property Overview",
            content=property_overview,
            section_type="text",
            order=1
        )
        
        # Pricing Strategy
        pricing_strategy = self._generate_pricing_strategy_section(property_details)
        report.add_section(
            title="Pricing Strategy",
            content=pricing_strategy,
            section_type="text",
            order=2
        )
        
        # Comparable Sales
        comps_content, comps_data = self._generate_comparable_sales_section(property_details)
        report.add_section(
            title="Comparable Sales",
            content=comps_content,
            section_type="table",
            data=comps_data,
            order=3
        )
        
        # Marketing Recommendations
        marketing_content = self._generate_marketing_recommendations_section(property_details)
        report.add_section(
            title="Marketing Recommendations",
            content=marketing_content,
            section_type="list",
            order=4
        )
        
        # Key Insights and Recommendations
        report.key_insights = self._generate_seller_insights(property_details)
        report.recommendations = self._generate_seller_recommendations(property_details)
        
        # Set metadata
        report.data_sources = ["Comparable Sales", "Market Analysis", "Pricing Models"]
        report.data_quality_score = 0.88
        report.confidence_level = "high"
        report.available_formats = [ReportFormat.HTML, ReportFormat.PDF, ReportFormat.EMAIL_FRIENDLY]
        
        return report
    
    async def _generate_investment_analysis_report(
        self,
        report_id: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        template: Optional[ReportTemplate],
        generated_for: str
    ) -> GeneratedReport:
        """Generate an investment analysis report."""
        
        property_info = parameters.get("property_info", {})
        
        report = GeneratedReport(
            report_id=report_id,
            report_type=ReportType.INVESTMENT_ANALYSIS,
            title=f"Investment Analysis Report - {property_info.get('suburb', 'Investment Property')}",
            generated_at=datetime.utcnow(),
            generated_for=generated_for,
            parameters=parameters,
            template_used=template.template_id if template else None
        )
        
        # Executive Summary
        report.executive_summary = self._generate_investment_executive_summary(property_info)
        
        # Investment Summary
        investment_summary = self._generate_investment_summary_section(property_info)
        report.add_section(
            title="Investment Summary",
            content=investment_summary,
            section_type="text",
            order=1
        )
        
        # Financial Analysis
        financial_content, financial_data = self._generate_financial_analysis_section(property_info)
        report.add_section(
            title="Financial Analysis",
            content=financial_content,
            section_type="table",
            data=financial_data,
            order=2
        )
        
        # Risk Assessment
        risk_assessment = self._generate_risk_assessment_section(property_info)
        report.add_section(
            title="Risk Assessment",
            content=risk_assessment,
            section_type="text",
            order=3
        )
        
        # Key Insights and Recommendations
        report.key_insights = self._generate_investment_insights(property_info)
        report.recommendations = self._generate_investment_recommendations(property_info)
        
        # Set metadata
        report.data_sources = ["Market Data", "Rental Analysis", "Financial Models"]
        report.data_quality_score = 0.83
        report.confidence_level = "medium"
        report.available_formats = [ReportFormat.HTML, ReportFormat.PDF, ReportFormat.JSON]
        
        return report
    
    async def _generate_off_market_summary_report(
        self,
        report_id: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        template: Optional[ReportTemplate],
        generated_for: str
    ) -> GeneratedReport:
        """Generate an off-market opportunities summary report."""
        
        area = parameters.get("area", "Sydney")
        
        report = GeneratedReport(
            report_id=report_id,
            report_type=ReportType.OFF_MARKET_SUMMARY,
            title=f"Off-Market Opportunities - {area}",
            generated_at=datetime.utcnow(),
            generated_for=generated_for,
            parameters=parameters
        )
        
        # Executive Summary
        report.executive_summary = f"Summary of off-market opportunities and pre-market listings in {area}."
        
        # Opportunity Summary
        opportunities_content = self._generate_off_market_opportunities_section(parameters)
        report.add_section(
            title="Current Opportunities",
            content=opportunities_content,
            section_type="list",
            order=1
        )
        
        # Set basic insights and recommendations
        report.key_insights = [
            "Multiple off-market opportunities available",
            "Pre-market listings provide early access advantage",
            "Distressed sale indicators identified in target areas"
        ]
        
        report.recommendations = [
            "Act quickly on high-priority opportunities",
            "Maintain relationships with off-market networks",
            "Monitor distress indicators for emerging opportunities"
        ]
        
        # Set metadata
        report.data_sources = ["Off-Market Networks", "Distress Indicators", "Pre-Market Intelligence"]
        report.data_quality_score = 0.75
        report.confidence_level = "medium"
        report.available_formats = [ReportFormat.HTML, ReportFormat.EMAIL_FRIENDLY]
        
        return report
    
    # Helper methods for generating report content
    
    def _generate_market_executive_summary(self, suburb: str, parameters: Dict[str, Any]) -> str:
        """Generate executive summary for market analysis report."""
        return (
            f"Market analysis for {suburb} shows strong activity with balanced supply and demand. "
            f"Current median house price is trending upward with good buyer interest across multiple "
            f"price segments. The area demonstrates solid fundamentals for both buyers and sellers."
        )
    
    def _generate_market_overview(self, suburb: str, parameters: Dict[str, Any]) -> str:
        """Generate market overview section content."""
        return (
            f"{suburb} is experiencing a balanced market with healthy transaction volumes. "
            f"Recent sales data indicates stable pricing with selective buyer activity. "
            f"The area continues to attract both owner-occupiers and investors due to its "
            f"proximity to amenities and transport links."
        )
    
    def _generate_price_trends_section(self, suburb: str, parameters: Dict[str, Any]) -> tuple:
        """Generate price trends section with content and data."""
        content = (
            f"Price trends in {suburb} show consistent growth over the past 12 months. "
            f"Median house prices have increased by 3.2% quarter-on-quarter, with apartments "
            f"showing similar momentum at 2.8% growth."
        )
        
        # Mock chart data
        data = {
            "chart_type": "line",
            "title": f"Price Trends - {suburb}",
            "data_points": [
                {"period": "Q1 2024", "house_median": 1200000, "unit_median": 850000},
                {"period": "Q2 2024", "house_median": 1225000, "unit_median": 865000},
                {"period": "Q3 2024", "house_median": 1250000, "unit_median": 880000},
                {"period": "Q4 2024", "house_median": 1275000, "unit_median": 895000}
            ]
        }
        
        return content, data
    
    def _generate_sales_activity_section(self, suburb: str, parameters: Dict[str, Any]) -> tuple:
        """Generate sales activity section with table data."""
        content = (
            f"Sales activity in {suburb} remains robust with 45 transactions in the last quarter. "
            f"Average days on market is 28 days, indicating good buyer demand."
        )
        
        # Mock table data
        data = {
            "table_type": "sales_summary",
            "headers": ["Property Type", "Sales Count", "Median Price", "Avg DOM"],
            "rows": [
                ["House", "28", "$1,275,000", "25 days"],
                ["Unit", "17", "$895,000", "32 days"],
                ["Townhouse", "8", "$1,100,000", "29 days"]
            ]
        }
        
        return content, data
    
    def _generate_market_insights(self, suburb: str, parameters: Dict[str, Any]) -> List[str]:
        """Generate key insights for market analysis."""
        return [
            f"{suburb} shows strong buyer confidence with quick sales",
            "Price growth is sustainable and supported by genuine demand",
            "Limited stock levels are supporting price stability",
            "Both local and external buyers are active in the market"
        ]
    
    def _generate_market_recommendations(self, suburb: str, parameters: Dict[str, Any]) -> List[str]:
        """Generate recommendations for market analysis."""
        return [
            "Sellers should price competitively to capitalize on current buyer activity",
            "Buyers should act decisively on quality properties in their price range",
            "Monitor upcoming listings for new opportunities",
            "Consider professional styling for properties coming to market"
        ]
    
    def _generate_buyer_executive_summary(self, buyer_criteria: Dict[str, Any]) -> str:
        """Generate executive summary for buyer matching report."""
        property_type = buyer_criteria.get("property_type", "property")
        budget = buyer_criteria.get("budget", "specified budget")
        return (
            f"Buyer matching analysis has identified several suitable {property_type} options "
            f"within {budget}. Strong matches found based on location preferences, property "
            f"features, and budget requirements."
        )
    
    def _generate_buyer_profile_section(self, buyer_criteria: Dict[str, Any]) -> str:
        """Generate buyer profile section."""
        return (
            f"Buyer is seeking a {buyer_criteria.get('property_type', 'property')} with "
            f"{buyer_criteria.get('bedrooms', 'multiple')} bedrooms in "
            f"{buyer_criteria.get('preferred_areas', 'preferred areas')}. "
            f"Budget range is {buyer_criteria.get('budget', 'as specified')}."
        )
    
    def _generate_recommended_properties_section(self, buyer_criteria: Dict[str, Any]) -> tuple:
        """Generate recommended properties section with data."""
        content = "Based on your criteria, we've identified the following high-match properties:"
        
        # Mock property data
        data = {
            "table_type": "property_recommendations",
            "headers": ["Address", "Type", "Bedrooms", "Price", "Match Score"],
            "rows": [
                ["123 Smith St, Newtown", "Terrace", "3", "$1,250,000", "94%"],
                ["456 Jones Ave, Surry Hills", "Apartment", "2", "$950,000", "87%"],
                ["789 Brown Rd, Redfern", "Townhouse", "3", "$1,180,000", "85%"]
            ]
        }
        
        return content, data
    
    def _generate_match_analysis_section(self, buyer_criteria: Dict[str, Any]) -> str:
        """Generate match analysis section."""
        return (
            "Property matching analysis shows strong alignment with buyer preferences. "
            "Top matches score above 85% compatibility, with factors including location, "
            "property type, price range, and specific feature requirements all well-aligned."
        )
    
    def _generate_buyer_insights(self, buyer_criteria: Dict[str, Any]) -> List[str]:
        """Generate insights for buyer matching."""
        return [
            "Multiple high-quality matches available in preferred areas",
            "Market conditions favor decisive buyers in this price range",
            "Properties with specified features are moving quickly",
            "Competition is moderate for well-presented properties"
        ]
    
    def _generate_buyer_recommendations(self, buyer_criteria: Dict[str, Any]) -> List[str]:
        """Generate recommendations for buyer matching."""
        return [
            "Schedule inspections for top-matched properties immediately",
            "Prepare pre-approval documentation for competitive offers",
            "Consider expanding search to adjacent suburbs for more options",
            "Set up alerts for new listings matching your criteria"
        ]
    
    def _generate_seller_executive_summary(self, property_details: Dict[str, Any]) -> str:
        """Generate executive summary for seller strategy."""
        return (
            f"Strategic analysis for {property_details.get('address', 'your property')} "
            f"indicates strong market positioning with optimal timing for sale. "
            f"Recommended approach combines competitive pricing with targeted marketing "
            f"to maximize sale price and minimize time on market."
        )
    
    def _generate_property_overview_section(self, property_details: Dict[str, Any]) -> str:
        """Generate property overview section."""
        return (
            f"Property at {property_details.get('address', 'the address')} is a "
            f"{property_details.get('type', 'property')} with "
            f"{property_details.get('bedrooms', 'multiple')} bedrooms and "
            f"{property_details.get('bathrooms', 'multiple')} bathrooms. "
            f"Key features include {property_details.get('features', 'various amenities')}."
        )
    
    def _generate_pricing_strategy_section(self, property_details: Dict[str, Any]) -> str:
        """Generate pricing strategy section."""
        return (
            "Recommended pricing strategy positions the property competitively while "
            "maximizing value. Based on comparable sales analysis and current market "
            "conditions, an initial asking price of $XX is recommended, with flexibility "
            "for negotiation based on buyer interest levels."
        )
    
    def _generate_comparable_sales_section(self, property_details: Dict[str, Any]) -> tuple:
        """Generate comparable sales section with data."""
        content = "Recent comparable sales support the recommended pricing strategy:"
        
        # Mock comparable sales data
        data = {
            "table_type": "comparable_sales",
            "headers": ["Address", "Sale Date", "Sale Price", "Beds/Baths", "Similarity"],
            "rows": [
                ["111 Similar St", "Nov 2024", "$1,280,000", "3/2", "High"],
                ["222 Close Ave", "Oct 2024", "$1,250,000", "3/1", "Medium"],
                ["333 Near Rd", "Sep 2024", "$1,320,000", "4/2", "Medium"]
            ]
        }
        
        return content, data
    
    def _generate_marketing_recommendations_section(self, property_details: Dict[str, Any]) -> str:
        """Generate marketing recommendations section."""
        return (
            "Comprehensive marketing strategy should include professional photography, "
            "online listing optimization, targeted social media promotion, and strategic "
            "timing of marketing campaign launch to maximize buyer exposure and interest."
        )
    
    def _generate_seller_insights(self, property_details: Dict[str, Any]) -> List[str]:
        """Generate insights for seller strategy."""
        return [
            "Property is well-positioned for current market conditions",
            "Comparable sales support competitive pricing strategy",
            "Marketing approach should emphasize unique property features",
            "Timing aligns with seasonal buyer activity patterns"
        ]
    
    def _generate_seller_recommendations(self, property_details: Dict[str, Any]) -> List[str]:
        """Generate recommendations for seller strategy."""
        return [
            "Implement recommended pricing strategy for optimal results",
            "Prepare property presentation before marketing launch",
            "Schedule professional photography and virtual tour",
            "Monitor market feedback and adjust strategy as needed"
        ]
    
    def _generate_investment_executive_summary(self, property_info: Dict[str, Any]) -> str:
        """Generate executive summary for investment analysis."""
        return (
            f"Investment analysis for {property_info.get('suburb', 'the property')} "
            f"shows positive indicators with projected returns meeting investment criteria. "
            f"Market fundamentals support long-term growth potential with acceptable risk levels."
        )
    
    def _generate_investment_summary_section(self, property_info: Dict[str, Any]) -> str:
        """Generate investment summary section."""
        return (
            f"Investment opportunity in {property_info.get('suburb', 'target area')} "
            f"offers projected rental yield of X% with capital growth potential of Y% annually. "
            f"Property type aligns with tenant demand in the area."
        )
    
    def _generate_financial_analysis_section(self, property_info: Dict[str, Any]) -> tuple:
        """Generate financial analysis section with data."""
        content = "Financial analysis shows positive investment metrics:"
        
        # Mock financial data
        data = {
            "table_type": "financial_analysis",
            "headers": ["Metric", "Value", "Industry Benchmark"],
            "rows": [
                ["Rental Yield", "4.2%", "3.8%"],
                ["Capital Growth (5yr)", "6.5%", "5.2%"],
                ["Cash Flow", "$180/week", "Variable"],
                ["Total ROI", "8.5%", "7.2%"]
            ]
        }
        
        return content, data
    
    def _generate_risk_assessment_section(self, property_info: Dict[str, Any]) -> str:
        """Generate risk assessment section."""
        return (
            "Risk assessment indicates moderate risk profile with manageable exposure. "
            "Key risks include market volatility and tenant vacancy, offset by strong "
            "location fundamentals and diversified tenant demand."
        )
    
    def _generate_investment_insights(self, property_info: Dict[str, Any]) -> List[str]:
        """Generate insights for investment analysis."""
        return [
            "Property meets investment return criteria",
            "Location shows strong rental demand fundamentals",
            "Market entry timing is favorable for investors",
            "Risk profile aligns with conservative investment approach"
        ]
    
    def _generate_investment_recommendations(self, property_info: Dict[str, Any]) -> List[str]:
        """Generate recommendations for investment analysis."""
        return [
            "Proceed with investment based on positive analysis",
            "Consider property management options for optimal returns",
            "Monitor market conditions for exit strategy timing",
            "Evaluate tax implications with financial advisor"
        ]
    
    def _generate_off_market_opportunities_section(self, parameters: Dict[str, Any]) -> str:
        """Generate off-market opportunities section."""
        return (
            "Current off-market opportunities include pre-market listings, "
            "distressed sales, and private treaty opportunities. Several high-potential "
            "properties are available through exclusive networks before public listing."
        )
    
    def _update_generation_stats(self, report_type: ReportType, generation_time: float) -> None:
        """Update report generation statistics."""
        
        # Update report type counts
        if report_type.value not in self.generation_stats["reports_by_type"]:
            self.generation_stats["reports_by_type"][report_type.value] = 0
        self.generation_stats["reports_by_type"][report_type.value] += 1
        
        # Update average generation time
        total_reports = self.generation_stats["total_reports"]
        current_avg = self.generation_stats["avg_generation_time"]
        self.generation_stats["avg_generation_time"] = (
            (current_avg * (total_reports - 1) + generation_time) / total_reports
        )
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """Get current report generation statistics."""
        
        success_rate = 0.0
        if self.generation_stats["total_reports"] > 0:
            success_rate = (
                self.generation_stats["successful_generations"] / 
                self.generation_stats["total_reports"]
            ) * 100
        
        return {
            **self.generation_stats,
            "success_rate": success_rate,
            "active_generations": len(self.active_generations),
            "templates_loaded": len(self.templates)
        }
    
    def __repr__(self) -> str:
        return f"<ReportGenerator(reports={self.generation_stats['total_reports']}, templates={len(self.templates)})>"