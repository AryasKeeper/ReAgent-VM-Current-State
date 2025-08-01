#!/usr/bin/env python3
"""
ReAgent Sydney - Comprehensive Monitoring Validation
====================================================

Production-ready monitoring stack validation for Prometheus, Grafana, and health systems.
Tests all monitoring components and provides operational readiness assessment.
"""

import asyncio
import json
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import sys
import os
import subprocess
import requests
import redis
import psycopg2
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from reagent.utils.monitoring.metrics import (
        HealthChecker, agent_executions_total, 
        properties_processed_total, vector_searches_total
    )
    from reagent.utils.monitoring.production_health_monitor import (
        ProductionHealthMonitor, ServiceStatus, CircuitState
    )
    from reagent.core.config import get_settings
    from reagent.utils.logging import get_logger
except ImportError as e:
    print(f"⚠️ Warning: Could not import ReAgent modules: {e}")
    HealthChecker = None
    ProductionHealthMonitor = None


class MonitoringValidationReport:
    """Comprehensive monitoring validation and reporting."""
    
    def __init__(self):
        self.results = {
            "validation_timestamp": datetime.utcnow().isoformat(),
            "system_info": {
                "environment": "development",
                "validation_host": "localhost",
                "python_version": sys.version
            },
            "monitoring_stack": {
                "prometheus": {"status": "unknown", "details": {}},
                "grafana": {"status": "unknown", "details": {}},
                "alertmanager": {"status": "unknown", "details": {}}
            },
            "service_health": {},
            "metrics_collection": {},
            "alert_system": {},
            "performance_baseline": {},
            "production_readiness": {},
            "recommendations": []
        }
        
        self.test_summary = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "warnings": 0,
            "critical_issues": []
        }
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Execute complete monitoring system validation."""
        print("🚀 ReAgent Sydney - Monitoring Stack Validation")
        print("=" * 60)
        
        try:
            # 1. Infrastructure Services Validation
            await self._validate_infrastructure_services()
            
            # 2. Monitoring Stack Validation
            await self._validate_monitoring_stack()
            
            # 3. Service Health Checks
            await self._validate_service_health_checks()
            
            # 4. Metrics Collection Validation
            await self._validate_metrics_collection()
            
            # 5. Alert System Validation
            await self._validate_alert_system()
            
            # 6. Performance Baseline Assessment
            await self._validate_performance_baselines()
            
            # 7. Production Readiness Assessment
            await self._assess_production_readiness()
            
            # 8. Generate Recommendations
            self._generate_recommendations()
            
        except Exception as e:
            print(f"❌ Critical validation error: {e}")
            traceback.print_exc()
            self.test_summary["critical_issues"].append(f"Validation failed: {str(e)}")
        
        return self._finalize_report()
    
    async def _validate_infrastructure_services(self):
        """Validate core infrastructure services."""
        print("\n📊 Infrastructure Services Validation")
        print("-" * 40)
        
        services = {
            "postgres": {"port": 5432, "health_check": self._check_postgres},
            "redis": {"port": 6379, "health_check": self._check_redis},
            "weaviate": {"port": 8080, "health_check": self._check_weaviate},
            "chromadb": {"port": 8000, "health_check": self._check_chromadb}
        }
        
        for service_name, config in services.items():
            try:
                result = await config["health_check"]()
                self.results["service_health"][service_name] = result
                
                if result["status"] == "healthy":
                    print(f"✅ {service_name.upper()}: {result['status'].upper()}")
                    self.test_summary["passed_tests"] += 1
                else:
                    print(f"⚠️ {service_name.upper()}: {result['status'].upper()} - {result.get('error', '')}")
                    self.test_summary["warnings"] += 1
                    
                self.test_summary["total_tests"] += 1
                
            except Exception as e:
                print(f"❌ {service_name.upper()}: FAILED - {str(e)}")
                self.results["service_health"][service_name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.test_summary["failed_tests"] += 1
                self.test_summary["total_tests"] += 1
    
    async def _validate_monitoring_stack(self):
        """Validate Prometheus, Grafana, and AlertManager."""
        print("\n📈 Monitoring Stack Validation")
        print("-" * 40)
        
        # Check if monitoring services should be running
        monitoring_services = {
            "prometheus": "http://localhost:9090",
            "grafana": "http://localhost:3001",
            "alertmanager": "http://localhost:9093"
        }
        
        for service, url in monitoring_services.items():
            try:
                # Check if service is accessible
                response = requests.get(f"{url}/api/v1/query?query=up", timeout=5)
                if response.status_code == 200:
                    self.results["monitoring_stack"][service] = {
                        "status": "healthy",
                        "url": url,
                        "response_time_ms": response.elapsed.total_seconds() * 1000,
                        "details": {"accessible": True}
                    }
                    print(f"✅ {service.upper()}: Running at {url}")
                    self.test_summary["passed_tests"] += 1
                else:
                    self.results["monitoring_stack"][service] = {
                        "status": "degraded",
                        "url": url,
                        "details": {"error": f"HTTP {response.status_code}"}
                    }
                    print(f"⚠️ {service.upper()}: HTTP {response.status_code}")
                    self.test_summary["warnings"] += 1
                    
            except requests.exceptions.ConnectionError:
                self.results["monitoring_stack"][service] = {
                    "status": "not_running",
                    "url": url,
                    "details": {"error": "Connection refused - service not running"}
                }
                print(f"🔴 {service.upper()}: NOT RUNNING")
                self.test_summary["failed_tests"] += 1
                
            except Exception as e:
                self.results["monitoring_stack"][service] = {
                    "status": "error",
                    "url": url,
                    "details": {"error": str(e)}
                }
                print(f"❌ {service.upper()}: ERROR - {str(e)}")
                self.test_summary["failed_tests"] += 1
            
            self.test_summary["total_tests"] += 1
    
    async def _validate_service_health_checks(self):
        """Validate health check implementations."""
        print("\n🏥 Service Health Check Validation")
        print("-" * 40)
        
        if HealthChecker is None:
            print("⚠️ HealthChecker not available - monitoring module import failed")
            self.test_summary["warnings"] += 1
            self.test_summary["total_tests"] += 1
            return
        
        try:
            health_checker = HealthChecker()
            
            # Test database health check
            try:
                db_health = await health_checker.check_database_health()
                print(f"✅ Database Health Check: {db_health['status'].upper()}")
                self.results["service_health"]["database_health_check"] = db_health
                self.test_summary["passed_tests"] += 1
            except Exception as e:
                print(f"❌ Database Health Check: FAILED - {str(e)}")
                self.test_summary["failed_tests"] += 1
            
            # Test Redis health check
            try:
                redis_health = await health_checker.check_redis_health()
                print(f"✅ Redis Health Check: {redis_health['status'].upper()}")
                self.results["service_health"]["redis_health_check"] = redis_health
                self.test_summary["passed_tests"] += 1
            except Exception as e:
                print(f"❌ Redis Health Check: FAILED - {str(e)}")
                self.test_summary["failed_tests"] += 1
            
            # Test Weaviate health check
            try:
                weaviate_health = await health_checker.check_weaviate_health()
                print(f"✅ Weaviate Health Check: {weaviate_health['status'].upper()}")
                self.results["service_health"]["weaviate_health_check"] = weaviate_health
                self.test_summary["passed_tests"] += 1
            except Exception as e:
                print(f"❌ Weaviate Health Check: FAILED - {str(e)}")
                self.test_summary["failed_tests"] += 1
            
            self.test_summary["total_tests"] += 3
            
        except Exception as e:
            print(f"❌ Health Check System: CRITICAL FAILURE - {str(e)}")
            self.test_summary["critical_issues"].append(f"Health check system failed: {str(e)}")
            self.test_summary["failed_tests"] += 1
            self.test_summary["total_tests"] += 1
    
    async def _validate_metrics_collection(self):
        """Validate Prometheus metrics collection."""
        print("\n📊 Metrics Collection Validation")
        print("-" * 40)
        
        # Test metrics availability (mock since actual services may not be running)
        metrics_tests = [
            "agent_executions_total",
            "properties_processed_total", 
            "vector_searches_total",
            "external_api_requests_total",
            "cache_operations_total"
        ]
        
        try:
            # Test if metrics are properly initialized
            from prometheus_client import REGISTRY
            
            available_metrics = []
            for metric_family in REGISTRY.collect():
                available_metrics.append(metric_family.name)
            
            for metric_name in metrics_tests:
                if any(metric_name in available for available in available_metrics):
                    print(f"✅ Metric Available: {metric_name}")
                    self.test_summary["passed_tests"] += 1
                else:
                    print(f"⚠️ Metric Missing: {metric_name}")
                    self.test_summary["warnings"] += 1
                
                self.test_summary["total_tests"] += 1
            
            self.results["metrics_collection"] = {
                "status": "configured",
                "available_metrics_count": len(available_metrics),
                "expected_metrics": metrics_tests,
                "available_metrics": available_metrics[:10]  # First 10 for brevity
            }
            
        except Exception as e:
            print(f"❌ Metrics Collection: FAILED - {str(e)}")
            self.results["metrics_collection"] = {
                "status": "failed",
                "error": str(e)
            }
            self.test_summary["failed_tests"] += 1
            self.test_summary["total_tests"] += 1
    
    async def _validate_alert_system(self):
        """Validate alert system configuration."""
        print("\n🚨 Alert System Validation")
        print("-" * 40)
        
        try:
            # Check alert rules file exists
            alert_rules_path = Path("monitoring/prometheus/alert_rules/reagent_alerts.yml")
            if alert_rules_path.exists():
                print("✅ Alert Rules Configuration: EXISTS")
                
                # Read and validate alert rules
                with open(alert_rules_path) as f:
                    import yaml
                    try:
                        alert_config = yaml.safe_load(f)
                        rule_groups = len(alert_config.get('groups', []))
                        total_alerts = sum(len(group.get('rules', [])) for group in alert_config.get('groups', []))
                        
                        print(f"✅ Alert Rules: {rule_groups} groups, {total_alerts} alerts")
                        
                        self.results["alert_system"] = {
                            "status": "configured",
                            "rules_file_exists": True,
                            "rule_groups": rule_groups,
                            "total_alerts": total_alerts,
                            "alert_categories": [group.get('name', 'unnamed') for group in alert_config.get('groups', [])]
                        }
                        
                        self.test_summary["passed_tests"] += 2
                        
                    except yaml.YAMLError as e:
                        print(f"❌ Alert Rules: INVALID YAML - {str(e)}")
                        self.test_summary["failed_tests"] += 1
                        
            else:
                print("❌ Alert Rules Configuration: MISSING")
                self.results["alert_system"]["status"] = "missing"
                self.test_summary["failed_tests"] += 1
            
            # Check AlertManager configuration
            alertmanager_config_path = Path("monitoring/alertmanager/alertmanager.yml")
            if alertmanager_config_path.exists():
                print("✅ AlertManager Configuration: EXISTS")
                self.test_summary["passed_tests"] += 1
            else:
                print("❌ AlertManager Configuration: MISSING")
                self.test_summary["failed_tests"] += 1
            
            self.test_summary["total_tests"] += 3
            
        except Exception as e:
            print(f"❌ Alert System Validation: FAILED - {str(e)}")
            self.results["alert_system"] = {"status": "failed", "error": str(e)}
            self.test_summary["failed_tests"] += 1
            self.test_summary["total_tests"] += 1
    
    async def _validate_performance_baselines(self):
        """Validate performance monitoring capabilities."""
        print("\n⚡ Performance Baseline Validation")
        print("-" * 40)
        
        try:
            # Simulate performance metrics collection
            start_time = time.time()
            
            # Test database connection performance
            db_response_times = []
            for i in range(3):
                db_start = time.time()
                db_result = await self._check_postgres()
                db_time = (time.time() - db_start) * 1000
                db_response_times.append(db_time)
            
            avg_db_response = sum(db_response_times) / len(db_response_times)
            
            # Test Redis performance
            redis_response_times = []
            for i in range(3):
                redis_start = time.time()
                redis_result = await self._check_redis()
                redis_time = (time.time() - redis_start) * 1000
                redis_response_times.append(redis_time)
            
            avg_redis_response = sum(redis_response_times) / len(redis_response_times)
            
            # Performance baseline assessment
            performance_metrics = {
                "database_avg_response_ms": round(avg_db_response, 2),
                "redis_avg_response_ms": round(avg_redis_response, 2),
                "baseline_test_duration_ms": round((time.time() - start_time) * 1000, 2)
            }
            
            # Performance thresholds (production SLA targets)
            thresholds = {
                "database_response_ms": 100,  # 100ms max
                "redis_response_ms": 10,      # 10ms max
                "api_response_ms": 500        # 500ms max
            }
            
            print(f"✅ Database Response Time: {performance_metrics['database_avg_response_ms']}ms")
            print(f"✅ Redis Response Time: {performance_metrics['redis_avg_response_ms']}ms")
            
            self.results["performance_baseline"] = {
                "status": "measured",
                "metrics": performance_metrics,
                "thresholds": thresholds,
                "performance_assessment": self._assess_performance_against_thresholds(
                    performance_metrics, thresholds
                )
            }
            
            self.test_summary["passed_tests"] += 2
            self.test_summary["total_tests"] += 2
            
        except Exception as e:
            print(f"❌ Performance Baseline: FAILED - {str(e)}")
            self.results["performance_baseline"] = {"status": "failed", "error": str(e)}
            self.test_summary["failed_tests"] += 1
            self.test_summary["total_tests"] += 1
    
    async def _assess_production_readiness(self):
        """Assess overall production readiness."""
        print("\n🎯 Production Readiness Assessment")
        print("-" * 40)
        
        readiness_criteria = {
            "infrastructure_services": self._assess_infrastructure_readiness(),
            "monitoring_stack": self._assess_monitoring_readiness(),
            "health_checks": self._assess_health_check_readiness(),
            "metrics_collection": self._assess_metrics_readiness(),
            "alert_system": self._assess_alert_readiness(),
            "performance_baselines": self._assess_performance_readiness()
        }
        
        # Calculate overall readiness score
        total_criteria = len(readiness_criteria)
        passed_criteria = sum(1 for status in readiness_criteria.values() if status == "ready")
        readiness_score = (passed_criteria / total_criteria) * 100
        
        overall_status = "ready" if readiness_score >= 80 else "not_ready"
        
        print(f"📊 Production Readiness Score: {readiness_score:.1f}%")
        print(f"🎯 Overall Status: {overall_status.upper()}")
        
        for criteria, status in readiness_criteria.items():
            status_icon = "✅" if status == "ready" else "❌"
            print(f"{status_icon} {criteria.replace('_', ' ').title()}: {status.upper()}")
        
        self.results["production_readiness"] = {
            "overall_status": overall_status,
            "readiness_score": readiness_score,
            "criteria_assessment": readiness_criteria,
            "passed_criteria": passed_criteria,
            "total_criteria": total_criteria
        }
    
    def _assess_infrastructure_readiness(self) -> str:
        """Assess infrastructure services readiness."""
        critical_services = ["postgres", "redis"]
        
        for service in critical_services:
            health = self.results["service_health"].get(service, {})
            if health.get("status") != "healthy":
                return "not_ready"
        
        return "ready"
    
    def _assess_monitoring_readiness(self) -> str:
        """Assess monitoring stack readiness."""
        monitoring_services = ["prometheus", "grafana"]
        
        for service in monitoring_services:
            stack_health = self.results["monitoring_stack"].get(service, {})
            if stack_health.get("status") not in ["healthy", "degraded"]:
                return "not_ready"
        
        return "ready"
    
    def _assess_health_check_readiness(self) -> str:
        """Assess health check system readiness."""
        health_checks = ["database_health_check", "redis_health_check"]
        
        for check in health_checks:
            if check not in self.results["service_health"]:
                return "not_ready"
        
        return "ready"
    
    def _assess_metrics_readiness(self) -> str:
        """Assess metrics collection readiness."""
        metrics_status = self.results["metrics_collection"].get("status")
        return "ready" if metrics_status == "configured" else "not_ready"
    
    def _assess_alert_readiness(self) -> str:
        """Assess alert system readiness."""
        alert_status = self.results["alert_system"].get("status")
        return "ready" if alert_status == "configured" else "not_ready"
    
    def _assess_performance_readiness(self) -> str:
        """Assess performance monitoring readiness."""
        perf_status = self.results["performance_baseline"].get("status")
        return "ready" if perf_status == "measured" else "not_ready"
    
    def _assess_performance_against_thresholds(self, metrics: Dict, thresholds: Dict) -> Dict:
        """Assess performance metrics against SLA thresholds."""
        assessment = {}
        
        if "database_avg_response_ms" in metrics:
            db_response = metrics["database_avg_response_ms"]
            assessment["database"] = {
                "status": "good" if db_response < thresholds["database_response_ms"] else "warning",
                "actual": db_response,
                "threshold": thresholds["database_response_ms"]
            }
        
        if "redis_avg_response_ms" in metrics:
            redis_response = metrics["redis_avg_response_ms"]
            assessment["redis"] = {
                "status": "good" if redis_response < thresholds["redis_response_ms"] else "warning",
                "actual": redis_response,
                "threshold": thresholds["redis_response_ms"]
            }
        
        return assessment
    
    def _generate_recommendations(self):
        """Generate actionable recommendations based on validation results."""
        recommendations = []
        
        # Infrastructure recommendations
        for service, health in self.results["service_health"].items():
            if health.get("status") == "unhealthy":
                recommendations.append({
                    "category": "infrastructure",
                    "priority": "high",
                    "issue": f"{service} service is unhealthy",
                    "recommendation": f"Investigate and fix {service} connectivity issues",
                    "action": f"Check {service} logs and restart if necessary"
                })
        
        # Monitoring stack recommendations
        for service, status in self.results["monitoring_stack"].items():
            if status.get("status") == "not_running":
                recommendations.append({
                    "category": "monitoring",
                    "priority": "high",
                    "issue": f"{service} monitoring service not running",
                    "recommendation": f"Start {service} monitoring service",
                    "action": f"docker-compose -f docker-compose.monitoring.yml up {service} -d"
                })
        
        # Performance recommendations
        perf_assessment = self.results["performance_baseline"].get("performance_assessment", {})
        for component, assessment in perf_assessment.items():
            if assessment.get("status") == "warning":
                recommendations.append({
                    "category": "performance",
                    "priority": "medium",
                    "issue": f"{component} response time above threshold",
                    "recommendation": f"Optimize {component} performance",
                    "action": f"Review {component} configuration and add monitoring"
                })
        
        # Production readiness recommendations
        readiness = self.results["production_readiness"]
        if readiness.get("overall_status") == "not_ready":
            recommendations.append({
                "category": "production",
                "priority": "critical",
                "issue": "System not ready for production deployment",
                "recommendation": "Address all failing readiness criteria before production deployment",
                "action": "Review and fix all failed validation tests"
            })
        
        self.results["recommendations"] = recommendations
    
    async def _check_postgres(self) -> Dict[str, Any]:
        """Check PostgreSQL health."""
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="reagent",
                user="reagent",
                password="reagent_secure_2024"
            )
            
            cur = conn.cursor()
            cur.execute("SELECT 1")
            result = cur.fetchone()
            
            cur.close()
            conn.close()
            
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "connection_test": "passed"
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _check_redis(self) -> Dict[str, Any]:
        """Check Redis health."""
        try:
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            r.ping()
            
            # Test basic operations
            r.set("test_key", "test_value", ex=5)
            value = r.get("test_key")
            r.delete("test_key")
            
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "ping_test": "passed",
                "read_write_test": "passed" if value == "test_value" else "failed"
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _check_weaviate(self) -> Dict[str, Any]:
        """Check Weaviate health."""
        try:
            response = requests.get("http://localhost:8080/v1/.well-known/ready", timeout=5)
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "ready_check": "passed",
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
            else:
                return {
                    "status": "degraded",
                    "timestamp": datetime.utcnow().isoformat(),
                    "ready_check": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _check_chromadb(self) -> Dict[str, Any]:
        """Check ChromaDB health."""
        try:
            response = requests.get("http://localhost:8000/api/v1/heartbeat", timeout=5)
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "heartbeat_check": "passed"
                }
            else:
                return {
                    "status": "unhealthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "heartbeat_check": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _finalize_report(self) -> Dict[str, Any]:
        """Finalize and return comprehensive validation report."""
        # Add test summary to results
        self.results["test_summary"] = self.test_summary
        
        # Calculate validation score
        total_tests = self.test_summary["total_tests"]
        passed_tests = self.test_summary["passed_tests"]
        validation_score = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        self.results["validation_score"] = validation_score
        self.results["validation_status"] = "passed" if validation_score >= 70 else "failed"
        
        return self.results


async def main():
    """Main execution function."""
    validator = MonitoringValidationReport()
    
    try:
        # Run comprehensive validation
        results = await validator.run_comprehensive_validation()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 MONITORING VALIDATION SUMMARY")
        print("=" * 60)
        
        summary = results["test_summary"]
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Warnings: {summary['warnings']}")
        print(f"Validation Score: {results['validation_score']:.1f}%")
        print(f"Overall Status: {results['validation_status'].upper()}")
        
        if summary['critical_issues']:
            print(f"\n❌ Critical Issues: {len(summary['critical_issues'])}")
            for issue in summary['critical_issues']:
                print(f"   • {issue}")
        
        # Print recommendations
        recommendations = results.get("recommendations", [])
        if recommendations:
            print(f"\n💡 Recommendations: {len(recommendations)}")
            for i, rec in enumerate(recommendations[:5], 1):  # Show first 5
                print(f"   {i}. [{rec['priority'].upper()}] {rec['recommendation']}")
        
        # Save detailed report
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_file = f"monitoring_validation_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed report saved: {report_file}")
        
        return results
        
    except Exception as e:
        print(f"❌ Validation failed with critical error: {e}")
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(main())