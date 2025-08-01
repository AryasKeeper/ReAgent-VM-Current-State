#!/usr/bin/env python3
"""
ReAgent Sydney - Simple System Health Check
Tests core components with standard libraries
"""

import subprocess
import json
import sys
import time
import socket
from datetime import datetime, timezone
from typing import Dict, List, Any

class SimpleHealthChecker:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_status": "unknown",
            "services": {},
            "databases": {},
            "containers": {},
            "network": {},
            "issues": [],
            "summary": {}
        }
        
    def log_result(self, component: str, status: str, details: str = ""):
        """Log test result"""
        status_symbol = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"
        print(f"{status_symbol} {component}: {details}")
        
    def check_port_connectivity(self, host: str, port: int, service_name: str):
        """Check if a port is accessible"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                self.log_result(service_name, "healthy", f"Port {port} accessible")
                return True
            else:
                self.log_result(service_name, "unhealthy", f"Port {port} not accessible")
                return False
        except Exception as e:
            self.log_result(service_name, "unhealthy", f"Connection test failed: {str(e)}")
            return False
            
    def check_docker_containers(self):
        """Check Docker container status"""
        print("\n=== DOCKER CONTAINERS STATUS ===")
        
        try:
            # Get container information
            result = subprocess.run([
                "docker", "ps", "--format", 
                "{{.Names}}\t{{.Status}}\t{{.Ports}}"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            name = parts[0]
                            status = parts[1]
                            ports = parts[2] if len(parts) > 2 else ""
                            
                            containers.append({
                                "name": name,
                                "status": status,
                                "ports": ports,
                                "healthy": "Up" in status and "healthy" in status.lower()
                            })
                            
                            status_text = "healthy" if "Up" in status else "unhealthy"
                            self.log_result(name, status_text, status)
                
                self.results["containers"] = containers
                self.results["summary"]["containers_running"] = len([c for c in containers if "Up" in c["status"]])
                self.results["summary"]["containers_total"] = len(containers)
                
            else:
                self.log_result("Docker", "unhealthy", "Failed to get container status")
                
        except Exception as e:
            self.log_result("Docker", "unhealthy", f"Error checking containers: {str(e)}")
            
    def check_database_ports(self):
        """Check database port connectivity"""
        print("\n=== DATABASE CONNECTIVITY ===")
        
        databases = {
            "PostgreSQL": ("localhost", 5432),
            "Redis": ("localhost", 6379),
            "Weaviate": ("localhost", 8080),
            "ChromaDB": ("localhost", 8000)
        }
        
        for db_name, (host, port) in databases.items():
            is_accessible = self.check_port_connectivity(host, port, db_name)
            self.results["databases"][db_name.lower()] = {
                "host": host,
                "port": port,
                "accessible": is_accessible
            }
            
    def check_service_ports(self):
        """Check service port connectivity"""
        print("\n=== SERVICE ENDPOINTS ===")
        
        services = {
            "API Server": ("localhost", 8000),
            "Health Monitor": ("localhost", 8001),
            "Prometheus": ("localhost", 9090),
            "Grafana": ("localhost", 3001)
        }
        
        for service_name, (host, port) in services.items():
            is_accessible = self.check_port_connectivity(host, port, service_name)
            self.results["services"][service_name.lower().replace(" ", "_")] = {
                "host": host,
                "port": port,
                "accessible": is_accessible
            }
            
    def check_docker_logs(self):
        """Check recent Docker logs for critical errors"""
        print("\n=== DOCKER LOGS ANALYSIS ===")
        
        containers = ["reagent-postgres-1", "reagent-redis-1", "reagent-weaviate-1", "reagent-chromadb-1"]
        
        for container in containers:
            try:
                result = subprocess.run([
                    "docker", "logs", "--tail", "50", container
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    logs = result.stdout + result.stderr
                    error_keywords = ["ERROR", "FATAL", "CRITICAL", "failed", "error"]
                    warning_keywords = ["WARNING", "WARN", "deprecated"]
                    
                    errors = sum(1 for keyword in error_keywords if keyword.lower() in logs.lower())
                    warnings = sum(1 for keyword in warning_keywords if keyword.lower() in logs.lower())
                    
                    if errors > 0:
                        self.log_result(container, "degraded", f"{errors} errors, {warnings} warnings in logs")
                        self.results["issues"].append({
                            "component": container,
                            "severity": "warning",
                            "message": f"Found {errors} errors in recent logs"
                        })
                    else:
                        self.log_result(container, "healthy", f"No critical errors in logs ({warnings} warnings)")
                        
            except Exception as e:
                self.log_result(container, "unknown", f"Could not analyze logs: {str(e)}")
                
    def check_disk_usage(self):
        """Check disk usage for Docker volumes"""
        print("\n=== DISK USAGE ANALYSIS ===")
        
        try:
            result = subprocess.run(["df", "-h", "."], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    fields = lines[1].split()
                    if len(fields) >= 5:
                        usage_percent = fields[4].replace('%', '')
                        if usage_percent.isdigit():
                            usage = int(usage_percent)
                            if usage > 90:
                                self.log_result("Disk Usage", "critical", f"{usage}% full")
                                self.results["issues"].append({
                                    "component": "disk",
                                    "severity": "critical",
                                    "message": f"Disk usage at {usage}%"
                                })
                            elif usage > 80:
                                self.log_result("Disk Usage", "degraded", f"{usage}% full")
                                self.results["issues"].append({
                                    "component": "disk",
                                    "severity": "warning", 
                                    "message": f"Disk usage at {usage}%"
                                })
                            else:
                                self.log_result("Disk Usage", "healthy", f"{usage}% full")
                                
                            self.results["summary"]["disk_usage_percent"] = usage
                            
        except Exception as e:
            self.log_result("Disk Usage", "unknown", f"Could not check disk usage: {str(e)}")
            
    def analyze_system_state(self):
        """Analyze overall system state"""
        print("\n=== SYSTEM ANALYSIS ===")
        
        # Count healthy vs unhealthy components
        healthy_dbs = sum(1 for db in self.results["databases"].values() if db.get("accessible", False))
        total_dbs = len(self.results["databases"])
        
        healthy_services = sum(1 for svc in self.results["services"].values() if svc.get("accessible", False))
        total_services = len(self.results["services"])
        
        healthy_containers = self.results["summary"].get("containers_running", 0)
        total_containers = self.results["summary"].get("containers_total", 0)
        
        critical_issues = len([issue for issue in self.results["issues"] if issue.get("severity") == "critical"])
        warning_issues = len([issue for issue in self.results["issues"] if issue.get("severity") == "warning"])
        
        # Determine overall status
        if critical_issues > 0 or healthy_dbs < 2:  # Need at least Postgres and Redis
            self.results["system_status"] = "critical"
            status_text = "CRITICAL"
        elif warning_issues > 2 or healthy_services < 1:
            self.results["system_status"] = "degraded"  
            status_text = "DEGRADED"
        elif healthy_dbs >= 3 and healthy_containers >= 3:
            self.results["system_status"] = "healthy"
            status_text = "HEALTHY"
        else:
            self.results["system_status"] = "partial"
            status_text = "PARTIAL"
            
        self.results["summary"].update({
            "healthy_databases": healthy_dbs,
            "total_databases": total_dbs,
            "healthy_services": healthy_services,
            "total_services": total_services,
            "critical_issues": critical_issues,
            "warning_issues": warning_issues,
            "overall_status": status_text
        })
        
        print(f"\n{'='*50}")
        print(f"🏥 SYSTEM HEALTH SUMMARY")
        print(f"{'='*50}")
        print(f"Overall Status: {status_text}")
        print(f"Databases: {healthy_dbs}/{total_dbs} accessible")
        print(f"Services: {healthy_services}/{total_services} accessible") 
        print(f"Containers: {healthy_containers}/{total_containers} running")
        print(f"Issues: {critical_issues} critical, {warning_issues} warnings")
        
    def run_health_check(self):
        """Run complete health check"""
        print("🔍 REAGENT SYDNEY - SYSTEM HEALTH CHECK")
        print("=" * 50)
        
        self.check_docker_containers()
        self.check_database_ports()
        self.check_service_ports()
        self.check_docker_logs()
        self.check_disk_usage()
        self.analyze_system_state()
        
        # Save results
        report_filename = f"system_health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        print(f"\nDetailed report saved to: {report_filename}")
        return self.results

def main():
    checker = SimpleHealthChecker()
    results = checker.run_health_check()
    
    # Exit with appropriate code
    if results["system_status"] == "critical":
        sys.exit(2)
    elif results["system_status"] == "degraded":
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()