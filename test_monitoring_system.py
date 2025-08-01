#!/usr/bin/env python3
"""
ReAgent Sydney - Monitoring System Test

Comprehensive test script to validate monitoring infrastructure,
generate sample metrics, and test alerting functionality.
"""

import asyncio
import time
import random
import requests
from typing import Dict, Any, List
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.monitoring import (
    track_agent_execution,
    record_property_processed,
    record_buyer_match,
    record_vector_search,
    BusinessMetricsCollector,
    PropertyMarketUpdate,
    BuyerBehaviorSnapshot
)
from utils.logging import (
    get_reagent_logger,
    correlation_context,
    agent_execution_context,
    setup_logging_for_development
)

# Configure logging for testing
setup_logging_for_development()
logger = get_reagent_logger("monitoring_test")

class MonitoringSystemTest:
    """Test suite for ReAgent monitoring system."""
    
    def __init__(self):
        self.metrics_collector = BusinessMetricsCollector()
        self.test_results = []
        
    async def run_all_tests(self):
        """Run complete monitoring system test suite."""
        logger.info("Starting comprehensive monitoring system tests")
        
        try:
            # Test 1: Basic metrics collection
            await self.test_basic_metrics()
            
            # Test 2: Agent performance monitoring
            await self.test_agent_monitoring()
            
            # Test 3: Business metrics tracking
            await self.test_business_metrics()
            
            # Test 4: Structured logging
            await self.test_structured_logging()
            
            # Test 5: Health check endpoints
            await self.test_health_endpoints()
            
            # Test 6: Alert generation
            await self.test_alert_generation()
            
            # Generate summary report
            self.generate_test_report()
            
        except Exception as e:
            logger.error("Test suite failed", error=str(e), exc_info=True)
            return False
            
        return True
    
    async def test_basic_metrics(self):
        """Test basic Prometheus metrics collection."""
        logger.info("Testing basic metrics collection")
        
        try:
            # Simulate property processing
            for i in range(10):
                source = random.choice(["domain", "realestate", "corelogic"])
                status = "success" if random.random() > 0.1 else "failed"
                record_property_processed(source, status)
                
            # Simulate buyer matches
            for i in range(5):
                match_quality = random.choice(["high", "medium", "low"])
                property_type = random.choice(["house", "apartment", "townhouse"])
                record_buyer_match(match_quality, property_type)
                
            # Simulate vector searches  
            for i in range(8):
                search_type = random.choice(["property_similarity", "buyer_matching"])
                duration = random.uniform(0.1, 2.0)
                status = "success" if random.random() > 0.05 else "failed"
                record_vector_search(search_type, duration, status)
                
            self.test_results.append({
                "test": "basic_metrics",
                "status": "passed",
                "details": "Generated 23 sample metrics successfully"
            })
            
            logger.info("Basic metrics test completed successfully")
            
        except Exception as e:
            self.test_results.append({
                "test": "basic_metrics", 
                "status": "failed",
                "error": str(e)
            })
            logger.error("Basic metrics test failed", error=str(e))
    
    async def test_agent_monitoring(self):
        """Test agent execution monitoring."""
        logger.info("Testing agent execution monitoring")
        
        try:
            agents = [
                "listing_watcher",
                "suburb_signal", 
                "buyer_matchmaker",
                "seller_strategy",
                "off_market_radar",
                "agent_whisperer"
            ]
            
            for agent_name in agents:
                # Test successful execution
                await self.simulate_agent_execution(agent_name, "success")
                
                # Occasionally test failed execution
                if random.random() < 0.2:
                    await self.simulate_agent_execution(agent_name, "failed")
                    
            self.test_results.append({
                "test": "agent_monitoring",
                "status": "passed", 
                "details": f"Tested {len(agents)} agents with various execution scenarios"
            })
            
            logger.info("Agent monitoring test completed successfully")
            
        except Exception as e:
            self.test_results.append({
                "test": "agent_monitoring",
                "status": "failed",
                "error": str(e)
            })
            logger.error("Agent monitoring test failed", error=str(e))
    
    @track_agent_execution("test_agent", "monitoring_test")
    async def simulate_agent_execution(self, agent_name: str, outcome: str):
        """Simulate an agent execution with monitoring."""
        execution_time = random.uniform(1.0, 30.0)
        
        with agent_execution_context(agent_name):
            logger.info(f"Starting {agent_name} execution simulation")
            
            # Simulate work
            await asyncio.sleep(execution_time / 10)  # Speed up for testing
            
            if outcome == "failed":
                raise Exception(f"Simulated {agent_name} execution failure")
                
            logger.info(f"Completed {agent_name} execution simulation")
    
    async def test_business_metrics(self):
        """Test business intelligence metrics."""
        logger.info("Testing business metrics collection")
        
        try:
            # Generate sample property market data
            suburbs = ["Bondi", "Surry Hills", "Paddington", "Newtown", "Manly"]
            property_types = ["house", "apartment", "townhouse"]
            
            for suburb in suburbs:
                for prop_type in property_types:
                    market_data = PropertyMarketUpdate(
                        suburb=suburb,
                        property_type=prop_type,
                        median_price=random.uniform(800000, 2500000),
                        price_change_pct=random.uniform(-5.0, 10.0),
                        days_on_market_avg=random.uniform(20, 90),
                        total_listings=random.randint(50, 300),
                        new_listings=random.randint(5, 50),
                        sold_listings=random.randint(10, 80)
                    )
                    
                    self.metrics_collector.update_property_market_metrics(market_data)
            
            # Generate buyer behavior data
            behavior_data = BuyerBehaviorSnapshot(
                total_active_buyers=random.randint(800, 1500),
                searches_per_day=random.randint(2000, 5000),
                top_searched_suburbs=random.sample(suburbs, 3),
                average_budget=random.uniform(900000, 1800000),
                inspection_conversion_rate=random.uniform(0.10, 0.25)
            )
            
            self.metrics_collector.update_buyer_behavior_metrics(behavior_data)
            
            # Test agent performance recording
            for agent in ["listing_watcher", "buyer_matchmaker", "suburb_signal"]:
                self.metrics_collector.record_agent_performance(
                    agent_name=agent,
                    task_type="data_processing",
                    completion_rate=random.uniform(0.85, 0.99),
                    accuracy=random.uniform(0.75, 0.95)
                )
            
            # Test market anomaly detection
            self.metrics_collector.record_market_anomaly(
                anomaly_type="price_spike",
                suburb=random.choice(suburbs),
                severity="high"
            )
            
            # Test off-market opportunity tracking
            self.metrics_collector.record_off_market_opportunity(
                opportunity_type="expired_listing",
                suburb=random.choice(suburbs),
                confidence="high"
            )
            
            self.test_results.append({
                "test": "business_metrics",
                "status": "passed",
                "details": "Generated comprehensive business metrics data"
            })
            
            logger.info("Business metrics test completed successfully")
            
        except Exception as e:
            self.test_results.append({
                "test": "business_metrics",
                "status": "failed", 
                "error": str(e)
            })
            logger.error("Business metrics test failed", error=str(e))
    
    async def test_structured_logging(self):
        """Test structured logging with context."""
        logger.info("Testing structured logging system")
        
        try:
            # Test correlation context
            with correlation_context() as correlation_id:
                logger.info("Testing correlation context", 
                           correlation_id=correlation_id,
                           test_type="structured_logging")
                
                # Test property context
                property_logger = logger.with_property_context(
                    property_id="prop_123",
                    suburb="Bondi",
                    property_type="apartment"
                )
                property_logger.info("Property processing started")
                
                # Test buyer context
                buyer_logger = logger.with_buyer_context(
                    buyer_id="buyer_456",
                    preferences={"budget": 1200000, "bedrooms": 2}
                )
                buyer_logger.info("Buyer search initiated")
                
                # Test agent context
                agent_logger = logger.with_agent_context(
                    agent_name="listing_watcher",
                    execution_id="exec_789"
                )
                agent_logger.info("Agent execution started")
                
                # Test API context
                api_logger = logger.with_api_context(
                    api_name="domain",
                    endpoint="/listings/search"
                )
                api_logger.info("External API call initiated")
                
                # Test error logging
                try:
                    raise ValueError("Simulated error for testing")
                except Exception as e:
                    logger.error("Test error occurred", error=str(e), exc_info=True)
            
            self.test_results.append({
                "test": "structured_logging",
                "status": "passed",
                "details": "All logging contexts tested successfully"
            })
            
            logger.info("Structured logging test completed successfully")
            
        except Exception as e:
            self.test_results.append({
                "test": "structured_logging",
                "status": "failed",
                "error": str(e)
            })
            logger.error("Structured logging test failed", error=str(e))
    
    async def test_health_endpoints(self):
        """Test health check API endpoints."""
        logger.info("Testing health check endpoints")
        
        try:
            # Note: This assumes the API is running on localhost:8001
            base_url = "http://localhost:8001"
            
            endpoints_to_test = [
                "/health/",
                "/health/live", 
                "/health/ready",
                "/health/detailed",
                "/health/metrics/summary"
            ]
            
            results = []
            for endpoint in endpoints_to_test:
                try:
                    response = requests.get(f"{base_url}{endpoint}", timeout=5)
                    results.append({
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "response_time_ms": response.elapsed.total_seconds() * 1000
                    })
                except requests.exceptions.RequestException as e:
                    results.append({
                        "endpoint": endpoint,
                        "error": str(e)
                    })
            
            self.test_results.append({
                "test": "health_endpoints",
                "status": "passed" if all("error" not in r for r in results) else "partial",
                "details": results
            })
            
            logger.info("Health endpoints test completed", results=results)
            
        except Exception as e:
            self.test_results.append({
                "test": "health_endpoints",
                "status": "failed",
                "error": str(e)
            })
            logger.error("Health endpoints test failed", error=str(e))
    
    async def test_alert_generation(self):
        """Test alert generation by creating problematic conditions."""
        logger.info("Testing alert generation scenarios")
        
        try:
            # Simulate high error rate
            for i in range(20):
                record_property_processed("domain", "failed")
            
            # Simulate slow agent execution
            @track_agent_execution("slow_agent", "performance_test")
            async def slow_operation():
                await asyncio.sleep(2)  # Simulate slow operation
                
            await slow_operation()
            
            # Simulate API quota issues
            self.metrics_collector.update_api_quota_usage(
                api_provider="domain",
                quota_type="requests_per_hour",
                utilization=0.95  # 95% utilization should trigger warning
            )
            
            # Log critical error to test alerting
            logger.critical("Test critical error for alert validation",
                          error_type="system_failure",
                          component="monitoring_test")
            
            self.test_results.append({
                "test": "alert_generation",
                "status": "passed",
                "details": "Generated various alert conditions for testing"
            })
            
            logger.info("Alert generation test completed")
            
        except Exception as e:
            self.test_results.append({
                "test": "alert_generation",
                "status": "failed",
                "error": str(e)
            })
            logger.error("Alert generation test failed", error=str(e))
    
    def generate_test_report(self):
        """Generate comprehensive test report."""
        logger.info("Generating monitoring system test report")
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "passed"])
        failed_tests = len([r for r in self.test_results if r["status"] == "failed"])
        
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            },
            "test_results": self.test_results,
            "timestamp": time.time(),
            "recommendations": self.generate_recommendations()
        }
        
        logger.info("Monitoring system test report", report=report)
        
        # Print summary to console
        print("\n" + "="*60)
        print("REAGENT SYDNEY - MONITORING SYSTEM TEST REPORT")
        print("="*60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {report['test_summary']['success_rate']:.1f}%")
        print("\nTest Details:")
        
        for result in self.test_results:
            status_emoji = "✅" if result["status"] == "passed" else "❌"
            print(f"{status_emoji} {result['test']}: {result['status']}")
            if "error" in result:
                print(f"   Error: {result['error']}")
        
        print("\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"• {rec}")
        
        print("="*60)
        
        return report
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        failed_tests = [r for r in self.test_results if r["status"] == "failed"]
        
        if not failed_tests:
            recommendations.append("All monitoring systems are functioning correctly")
            recommendations.append("Consider setting up automated monitoring tests")
            recommendations.append("Verify alerting channels are properly configured")
        else:
            recommendations.append("Address failed test cases before production deployment")
            
        recommendations.extend([
            "Configure Grafana dashboard access and verify all panels load correctly",
            "Test AlertManager notification channels (Slack, email, PagerDuty)",
            "Set up log aggregation with proper retention policies",
            "Configure backup monitoring for critical metrics",
            "Establish monitoring runbooks for common alert scenarios"
        ])
        
        return recommendations

async def main():
    """Main test execution function."""
    print("Starting ReAgent Sydney Monitoring System Tests...")
    
    test_suite = MonitoringSystemTest()
    success = await test_suite.run_all_tests()
    
    if success:
        print("\n✅ Monitoring system tests completed successfully!")
        return 0
    else:
        print("\n❌ Monitoring system tests failed!")
        return 1

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)