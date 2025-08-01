#!/usr/bin/env python3
"""
ReAgent Sydney - Simple Monitoring Validation
==============================================

Standalone monitoring validation without complex dependencies.
"""

import json
import time
import traceback
from datetime import datetime
import sys
import os
import requests
import redis
import psycopg2
from pathlib import Path


class SimpleMonitoringValidator:
    """Simple monitoring validation without complex dependencies."""
    
    def __init__(self):
        self.results = {
            "validation_timestamp": datetime.utcnow().isoformat(),
            "environment": "development",
            "services": {},
            "monitoring_stack": {},
            "configuration": {},
            "recommendations": []
        }
        
        self.test_count = {"total": 0, "passed": 0, "failed": 0, "warnings": 0}
    
    def validate_all(self):
        """Run all validation tests."""
        print("🚀 ReAgent Sydney - Simple Monitoring Validation")
        print("=" * 55)
        
        try:
            self.validate_infrastructure_services()
            self.validate_monitoring_configurations()
            self.validate_monitoring_endpoints()
            self.assess_production_readiness()
            self.generate_recommendations()
            
        except Exception as e:
            print(f"❌ Critical validation error: {e}")
            traceback.print_exc()
        
        return self.finalize_report()
    
    def validate_infrastructure_services(self):
        """Validate core infrastructure services."""
        print("\n📊 Infrastructure Services Validation")
        print("-" * 40)
        
        # PostgreSQL
        postgres_result = self.check_postgres()
        self.results["services"]["postgres"] = postgres_result
        self.print_service_status("PostgreSQL", postgres_result)
        
        # Redis
        redis_result = self.check_redis()
        self.results["services"]["redis"] = redis_result
        self.print_service_status("Redis", redis_result)
        
        # Weaviate
        weaviate_result = self.check_weaviate()
        self.results["services"]["weaviate"] = weaviate_result
        self.print_service_status("Weaviate", weaviate_result)
        
        # ChromaDB
        chromadb_result = self.check_chromadb()
        self.results["services"]["chromadb"] = chromadb_result
        self.print_service_status("ChromaDB", chromadb_result)
    
    def validate_monitoring_configurations(self):
        """Validate monitoring configuration files."""
        print("\n📋 Monitoring Configuration Validation")
        print("-" * 40)
        
        configs = {
            "prometheus_config": "monitoring/prometheus/prometheus.yml",
            "alert_rules": "monitoring/prometheus/alert_rules/reagent_alerts.yml",
            "alertmanager_config": "monitoring/alertmanager/alertmanager.yml",
            "grafana_provisioning": "monitoring/grafana/provisioning/datasources/prometheus.yml"
        }
        
        for config_name, config_path in configs.items():
            result = self.check_config_file(config_path)
            self.results["configuration"][config_name] = result
            
            if result["exists"]:
                print(f"✅ {config_name.replace('_', ' ').title()}: EXISTS")
                self.test_count["passed"] += 1
            else:
                print(f"❌ {config_name.replace('_', ' ').title()}: MISSING")
                self.test_count["failed"] += 1
            
            self.test_count["total"] += 1
        
        # Check Docker Compose monitoring file
        monitoring_compose = self.check_config_file("docker-compose.monitoring.yml")
        self.results["configuration"]["monitoring_compose"] = monitoring_compose
        
        if monitoring_compose["exists"]:
            print("✅ Docker Compose Monitoring: EXISTS")
            self.test_count["passed"] += 1
        else:
            print("❌ Docker Compose Monitoring: MISSING")
            self.test_count["failed"] += 1
        
        self.test_count["total"] += 1
    
    def validate_monitoring_endpoints(self):
        """Validate monitoring service endpoints."""
        print("\n🌐 Monitoring Endpoints Validation")
        print("-" * 40)
        
        endpoints = {
            "prometheus": "http://localhost:9090/-/healthy",
            "grafana": "http://localhost:3001/api/health",
            "alertmanager": "http://localhost:9093/-/healthy"
        }
        
        for service, url in endpoints.items():
            result = self.check_endpoint(url)
            self.results["monitoring_stack"][service] = result
            
            if result["accessible"]:
                print(f"✅ {service.title()}: ACCESSIBLE")
                self.test_count["passed"] += 1
            else:
                print(f"🔴 {service.title()}: NOT ACCESSIBLE")
                self.test_count["failed"] += 1
            
            self.test_count["total"] += 1
    
    def assess_production_readiness(self):
        """Assess production readiness."""
        print("\n🎯 Production Readiness Assessment")
        print("-" * 40)
        
        # Critical services check
        critical_services = ["postgres", "redis"]
        critical_healthy = all(
            self.results["services"].get(service, {}).get("status") == "healthy"
            for service in critical_services
        )
        
        # Configuration files check
        required_configs = ["prometheus_config", "alert_rules", "alertmanager_config"]
        configs_present = all(
            self.results["configuration"].get(config, {}).get("exists", False)
            for config in required_configs
        )
        
        # Calculate readiness score
        total_checks = 6  # 2 critical services + 3 configs + 1 monitoring stack
        passed_checks = 0
        
        if critical_healthy:
            passed_checks += 2
        if configs_present:
            passed_checks += 3
        
        # Check if any monitoring service is accessible
        monitoring_accessible = any(
            stack.get("accessible", False) 
            for stack in self.results["monitoring_stack"].values()
        )
        if monitoring_accessible:
            passed_checks += 1
        
        readiness_score = (passed_checks / total_checks) * 100
        overall_status = "ready" if readiness_score >= 70 else "not_ready"
        
        print(f"📊 Production Readiness Score: {readiness_score:.1f}%")
        print(f"🎯 Overall Status: {overall_status.upper()}")
        
        print(f"✅ Critical Services: {'HEALTHY' if critical_healthy else 'UNHEALTHY'}")
        print(f"✅ Configuration Files: {'PRESENT' if configs_present else 'MISSING'}")
        print(f"✅ Monitoring Stack: {'ACCESSIBLE' if monitoring_accessible else 'NOT ACCESSIBLE'}")
        
        self.results["readiness"] = {
            "score": readiness_score,
            "status": overall_status,
            "critical_services_healthy": critical_healthy,
            "configurations_present": configs_present,
            "monitoring_accessible": monitoring_accessible
        }
    
    def generate_recommendations(self):
        """Generate actionable recommendations."""
        recommendations = []
        
        # Infrastructure recommendations
        for service, result in self.results["services"].items():
            if result.get("status") != "healthy":
                recommendations.append({
                    "category": "infrastructure",
                    "priority": "high" if service in ["postgres", "redis"] else "medium",
                    "issue": f"{service} service is not healthy",
                    "action": f"Check {service} service status and restart if needed"
                })
        
        # Configuration recommendations
        for config, result in self.results["configuration"].items():
            if not result.get("exists", False):
                recommendations.append({
                    "category": "configuration",
                    "priority": "high",
                    "issue": f"{config} configuration missing",
                    "action": f"Create or verify {config} configuration file"
                })
        
        # Monitoring stack recommendations
        for service, result in self.results["monitoring_stack"].items():
            if not result.get("accessible", False):
                recommendations.append({
                    "category": "monitoring",
                    "priority": "high",
                    "issue": f"{service} monitoring service not accessible",
                    "action": f"Start {service} using docker-compose -f docker-compose.monitoring.yml up {service} -d"
                })
        
        # Add deployment recommendation if not ready
        if self.results.get("readiness", {}).get("status") == "not_ready":
            recommendations.append({
                "category": "deployment",
                "priority": "critical",
                "issue": "System not ready for production",
                "action": "Address all high-priority issues before production deployment"
            })
        
        self.results["recommendations"] = recommendations
    
    def check_postgres(self):
        """Check PostgreSQL connectivity."""
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="reagent",
                user="reagent",
                password="reagent_secure_2024",
                connect_timeout=5
            )
            
            cur = conn.cursor()
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            
            cur.close()
            conn.close()
            
            return {
                "status": "healthy",
                "version": version,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_redis(self):
        """Check Redis connectivity."""
        try:
            r = redis.Redis(
                host='localhost', 
                port=6379, 
                decode_responses=True,
                socket_connect_timeout=5
            )
            
            # Test ping
            r.ping()
            
            # Test basic operations
            test_key = "health_check_test"
            r.set(test_key, "test", ex=5)
            value = r.get(test_key)
            r.delete(test_key)
            
            # Get Redis info
            info = r.info()
            
            return {
                "status": "healthy",
                "version": info.get("redis_version", "unknown"),
                "memory_used_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_weaviate(self):
        """Check Weaviate health."""
        try:
            # Check readiness endpoint
            response = requests.get(
                "http://localhost:8080/v1/.well-known/ready", 
                timeout=5
            )
            
            if response.status_code == 200:
                # Try to get meta info
                try:
                    meta_response = requests.get(
                        "http://localhost:8080/v1/meta",
                        timeout=5
                    )
                    meta_data = meta_response.json() if meta_response.status_code == 200 else {}
                except:
                    meta_data = {}
                
                return {
                    "status": "healthy",
                    "ready": True,
                    "version": meta_data.get("version", "unknown"),
                    "response_time_ms": round(response.elapsed.total_seconds() * 1000, 2),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "status": "degraded",
                    "ready": False,
                    "http_status": response.status_code,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_chromadb(self):
        """Check ChromaDB health."""
        try:
            response = requests.get(
                "http://localhost:8000/api/v1/heartbeat",
                timeout=5
            )
            
            if response.status_code == 200:
                # Try to get version
                try:
                    version_response = requests.get(
                        "http://localhost:8000/api/v1/version",
                        timeout=5
                    )
                    version_data = version_response.json() if version_response.status_code == 200 else {}
                except:
                    version_data = {}
                
                return {
                    "status": "healthy",
                    "heartbeat": "ok",
                    "version": version_data.get("version", "unknown"),
                    "response_time_ms": round(response.elapsed.total_seconds() * 1000, 2),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "status": "unhealthy",
                    "http_status": response.status_code,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_config_file(self, file_path):
        """Check if configuration file exists."""
        path = Path(file_path)
        exists = path.exists()
        
        result = {
            "path": file_path,
            "exists": exists,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if exists:
            try:
                result["size_bytes"] = path.stat().st_size
                result["modified"] = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            except:
                pass
        
        return result
    
    def check_endpoint(self, url):
        """Check if endpoint is accessible."""
        try:
            response = requests.get(url, timeout=5)
            
            return {
                "url": url,
                "accessible": True,
                "status_code": response.status_code,
                "response_time_ms": round(response.elapsed.total_seconds() * 1000, 2),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except requests.exceptions.ConnectionError:
            return {
                "url": url,
                "accessible": False,
                "error": "Connection refused - service not running",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "url": url,
                "accessible": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def print_service_status(self, service_name, result):
        """Print service status with appropriate emoji."""
        status = result.get("status", "unknown")
        
        if status == "healthy":
            print(f"✅ {service_name}: HEALTHY")
            self.test_count["passed"] += 1
        elif status == "degraded":
            print(f"⚠️ {service_name}: DEGRADED")
            self.test_count["warnings"] += 1
        else:
            print(f"❌ {service_name}: UNHEALTHY - {result.get('error', 'Unknown error')}")
            self.test_count["failed"] += 1
        
        self.test_count["total"] += 1
    
    def finalize_report(self):
        """Finalize the validation report."""
        # Add test summary
        self.results["test_summary"] = self.test_count
        
        # Calculate overall score
        total = self.test_count["total"]
        passed = self.test_count["passed"]
        score = (passed / total * 100) if total > 0 else 0
        
        self.results["validation_score"] = score
        self.results["validation_status"] = "passed" if score >= 70 else "failed"
        
        return self.results


def main():
    """Main execution function."""
    validator = SimpleMonitoringValidator()
    
    try:
        results = validator.validate_all()
        
        # Print summary
        print("\n" + "=" * 55)
        print("📊 MONITORING VALIDATION SUMMARY")
        print("=" * 55)
        
        summary = results["test_summary"]
        print(f"Total Tests: {summary['total']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Warnings: {summary['warnings']}")
        print(f"Validation Score: {results['validation_score']:.1f}%")
        print(f"Overall Status: {results['validation_status'].upper()}")
        
        # Print key findings
        print(f"\n🔍 Key Findings:")
        readiness = results.get("readiness", {})
        print(f"   • Production Ready: {'YES' if readiness.get('status') == 'ready' else 'NO'}")
        print(f"   • Critical Services: {'HEALTHY' if readiness.get('critical_services_healthy') else 'UNHEALTHY'}")
        print(f"   • Configurations: {'PRESENT' if readiness.get('configurations_present') else 'MISSING'}")
        print(f"   • Monitoring Stack: {'ACCESSIBLE' if readiness.get('monitoring_accessible') else 'NOT ACCESSIBLE'}")
        
        # Print top recommendations
        recommendations = results.get("recommendations", [])
        if recommendations:
            print(f"\n💡 Priority Actions ({len(recommendations)} total):")
            for i, rec in enumerate(recommendations[:3], 1):  # Show top 3
                print(f"   {i}. [{rec['priority'].upper()}] {rec['action']}")
        
        # Save report
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_file = f"monitoring_validation_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed report saved: {report_file}")
        
        return results
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()