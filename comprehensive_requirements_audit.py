#!/usr/bin/env python3
"""
Comprehensive Requirements.txt Security & Quality Audit
======================================================

Enterprise-grade audit for production readiness validation.
Analyzes security vulnerabilities, performance implications, and maintenance status.
"""

import subprocess
import sys
import json
import requests
from typing import Dict, List, Tuple, Optional, Set
from packaging import version
from pathlib import Path
from datetime import datetime, timedelta
import concurrent.futures
import time

# Enhanced security vulnerability database
CRITICAL_SECURITY_ISSUES = {
    'fastapi': {
        'versions_affected': ['<0.115.0'],
        'cves': ['CVE-2024-24762', 'CVE-2024-47874'],
        'description': 'ReDoS vulnerability and Starlette security issue',
        'severity': 'CRITICAL',
        'fixed_in': '0.115.0'
    },
    'langchain': {
        'versions_affected': ['<0.3.7'],
        'cves': ['CVE-2023-46229', 'CVE-2023-44467', 'CVE-2024-36480'],
        'description': 'SSRF, prompt injection, and RCE vulnerabilities',
        'severity': 'CRITICAL',
        'fixed_in': '0.3.7'
    },
    'sqlalchemy': {
        'versions_affected': ['<1.2.18'],
        'cves': ['CVE-2019-7548'],
        'description': 'SQL injection vulnerability in group_by parameter',
        'severity': 'HIGH',
        'fixed_in': '2.0.0'
    },
    'aiohttp': {
        'versions_affected': ['<3.9.2'],
        'cves': ['CVE-2024-23334'],
        'description': 'HTTP request smuggling vulnerability',
        'severity': 'MEDIUM',
        'fixed_in': '3.12.0'
    }
}

# Performance-critical packages and their optimization status
PERFORMANCE_PACKAGES = {
    'httpx': {
        'current_optimal': '0.27.0',
        'performance_impact': 'HIGH',
        'improvements': ['Connection pooling', 'HTTP/2 support', 'Async optimizations']
    },
    'pandas': {
        'current_optimal': '2.2.0',
        'performance_impact': 'MEDIUM',
        'improvements': ['Arrow backend', 'String dtype optimizations', 'Copy-on-write']
    },
    'numpy': {
        'current_optimal': '1.26.0',
        'performance_impact': 'HIGH',
        'improvements': ['SIMD optimizations', 'Memory layout improvements']
    },
    'redis': {
        'current_optimal': '5.0.1',
        'performance_impact': 'LOW',
        'improvements': ['Connection resilience', 'Memory optimizations']
    }
}

# Enterprise deployment readiness criteria
PRODUCTION_READINESS_CRITERIA = {
    'monitoring': ['prometheus-client', 'sentry-sdk', 'structlog'],
    'async_support': ['asyncio', 'asyncpg', 'aiohttp'],
    'caching': ['redis', 'hiredis'],
    'security': ['cryptography', 'passlib'],
    'testing': ['pytest', 'pytest-asyncio', 'pytest-cov'],
    'data_processing': ['pandas', 'numpy'],
    'web_framework': ['fastapi', 'uvicorn'],
    'database': ['sqlalchemy', 'alembic', 'psycopg2-binary'],
    'ml_ai': ['openai', 'langchain', 'weaviate-client'],
    'task_queue': ['celery', 'kombu']
}

class ComprehensiveRequirementsAuditor:
    """Advanced requirements.txt auditor for enterprise deployment."""
    
    def __init__(self, requirements_path: str = "requirements.txt"):
        self.requirements_path = Path(requirements_path)
        self.requirements = self._parse_requirements()
        self.audit_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'file_path': str(self.requirements_path),
            'total_packages': len(self.requirements),
            'security_audit': {},
            'performance_audit': {},
            'maintenance_audit': {},
            'production_readiness': {},
            'recommendations': {},
            'risk_assessment': {}
        }
        
    def _parse_requirements(self) -> Dict[str, str]:
        """Enhanced requirements parsing with better error handling."""
        requirements = {}
        
        if not self.requirements_path.exists():
            raise FileNotFoundError(f"Requirements file not found: {self.requirements_path}")
            
        with open(self.requirements_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('-'):
                    try:
                        # Enhanced parsing for different version specifiers
                        if '==' in line:
                            package, ver = line.split('==', 1)
                            requirements[package.strip()] = ('==', ver.strip())
                        elif '~=' in line:
                            package, ver = line.split('~=', 1)
                            requirements[package.strip()] = ('~=', ver.strip())
                        elif '>=' in line:
                            package, ver = line.split('>=', 1)
                            requirements[package.strip()] = ('>=', ver.strip())
                        elif '>' in line:
                            package, ver = line.split('>', 1)
                            requirements[package.strip()] = ('>', ver.strip())
                        elif '<=' in line:
                            package, ver = line.split('<=', 1)
                            requirements[package.strip()] = ('<=', ver.strip())
                        elif '<' in line:
                            package, ver = line.split('<', 1)
                            requirements[package.strip()] = ('<', ver.strip())
                        else:
                            # Unpinned package
                            package = line.split('[')[0].strip()
                            requirements[package] = ('unpinned', None)
                    except ValueError as e:
                        print(f"Warning: Could not parse line {line_num}: {line} - {e}")
                        
        return requirements
    
    def audit_security_vulnerabilities(self) -> Dict:
        """Comprehensive security vulnerability analysis."""
        security_issues = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': [],
            'summary': {}
        }
        
        for package, (op, version_spec) in self.requirements.items():
            if package in CRITICAL_SECURITY_ISSUES:
                vuln_info = CRITICAL_SECURITY_ISSUES[package]
                
                # Check if current version is affected
                if version_spec and op == '==':
                    try:
                        current_version = version.parse(version_spec)
                        fixed_version = version.parse(vuln_info['fixed_in'])
                        
                        if current_version < fixed_version:
                            issue = {
                                'package': package,
                                'current_version': version_spec,
                                'vulnerability': {
                                    'cves': vuln_info['cves'],
                                    'description': vuln_info['description'],
                                    'severity': vuln_info['severity'],
                                    'fixed_in': vuln_info['fixed_in']
                                },
                                'recommendation': f'Upgrade to {package}>={vuln_info["fixed_in"]}',
                                'urgency': 'IMMEDIATE' if vuln_info['severity'] == 'CRITICAL' else 'HIGH'
                            }
                            
                            severity_key = vuln_info['severity'].lower()
                            security_issues[severity_key].append(issue)
                    except Exception as e:
                        print(f"Error analyzing {package}: {e}")
                elif op == 'unpinned':
                    # Unpinned critical packages are high risk
                    issue = {
                        'package': package,
                        'current_version': 'UNPINNED',
                        'vulnerability': {
                            'description': f'Critical security package {package} is unpinned',
                            'severity': 'HIGH',
                            'risk': 'Version drift may introduce vulnerabilities'
                        },
                        'recommendation': f'Pin {package} to latest secure version',
                        'urgency': 'HIGH'
                    }
                    security_issues['high'].append(issue)
        
        # Calculate security score
        total_issues = sum(len(issues) for issues in security_issues.values() if isinstance(issues, list))
        critical_weight = len(security_issues['critical']) * 10
        high_weight = len(security_issues['high']) * 5
        medium_weight = len(security_issues['medium']) * 2
        
        security_score = 100 - min(100, critical_weight + high_weight + medium_weight)
        
        security_issues['summary'] = {
            'total_issues': total_issues,
            'security_score': security_score,
            'risk_level': self._calculate_risk_level(security_score),
            'requires_immediate_action': len(security_issues['critical']) > 0
        }
        
        return security_issues
    
    def audit_performance_implications(self) -> Dict:
        """Analyze performance implications of package versions."""
        performance_issues = {
            'high_impact': [],
            'medium_impact': [],
            'low_impact': [],
            'optimizations_available': [],
            'summary': {}
        }
        
        for package, (op, version_spec) in self.requirements.items():
            if package in PERFORMANCE_PACKAGES:
                perf_info = PERFORMANCE_PACKAGES[package]
                
                if version_spec and op == '==':
                    try:
                        current_version = version.parse(version_spec)
                        optimal_version = version.parse(perf_info['current_optimal'])
                        
                        if current_version < optimal_version:
                            months_behind = self._estimate_months_behind(current_version, optimal_version)
                            
                            issue = {
                                'package': package,
                                'current_version': version_spec,
                                'optimal_version': perf_info['current_optimal'],
                                'performance_impact': perf_info['performance_impact'],
                                'improvements_available': perf_info['improvements'],
                                'months_behind': months_behind,
                                'recommendation': f'Upgrade to {package}>={perf_info["current_optimal"]}'
                            }
                            
                            impact_key = f"{perf_info['performance_impact'].lower()}_impact"
                            performance_issues[impact_key].append(issue)
                    except Exception as e:
                        print(f"Error analyzing performance for {package}: {e}")
        
        # Calculate performance score
        high_issues = len(performance_issues['high_impact'])
        medium_issues = len(performance_issues['medium_impact'])
        performance_score = 100 - min(100, high_issues * 15 + medium_issues * 5)
        
        performance_issues['summary'] = {
            'performance_score': performance_score,
            'total_optimization_opportunities': sum(len(issues) for key, issues in performance_issues.items() if key.endswith('_impact')),
            'estimated_performance_gain': self._estimate_performance_gain(performance_issues)
        }
        
        return performance_issues
    
    def audit_maintenance_status(self) -> Dict:
        """Analyze maintenance status and long-term viability."""
        maintenance_status = {
            'deprecated': [],
            'maintenance_mode': [],
            'actively_maintained': [],
            'end_of_life_risk': [],
            'summary': {}
        }
        
        # Known maintenance status
        deprecated_packages = {
            'weaviate-client': {
                'status': 'API_DEPRECATED',
                'version_affected': '3.x',
                'migration_path': 'weaviate-client>=4.10.0',
                'deadline': '2025-12-31',
                'description': 'v3 API deprecated, migrate to v4'
            },
            'psycopg2-binary': {
                'status': 'MAINTENANCE_MODE',
                'migration_path': 'psycopg[binary]>=3.1.8',
                'description': 'In maintenance mode, psycopg3 recommended for new projects'
            }
        }
        
        for package, (op, version_spec) in self.requirements.items():
            if package in deprecated_packages:
                dep_info = deprecated_packages[package]
                
                issue = {
                    'package': package,
                    'current_version': version_spec if version_spec else 'unpinned',
                    'status': dep_info['status'],
                    'description': dep_info['description'],
                    'migration_path': dep_info['migration_path'],
                    'urgency': 'HIGH' if 'deadline' in dep_info else 'MEDIUM',
                    'deadline': dep_info.get('deadline')
                }
                
                if dep_info['status'] == 'API_DEPRECATED':
                    maintenance_status['deprecated'].append(issue)
                else:
                    maintenance_status['maintenance_mode'].append(issue)
        
        # Calculate maintenance score
        deprecated_count = len(maintenance_status['deprecated'])
        maintenance_count = len(maintenance_status['maintenance_mode'])
        maintenance_score = 100 - min(100, deprecated_count * 20 + maintenance_count * 10)
        
        maintenance_status['summary'] = {
            'maintenance_score': maintenance_score,
            'packages_requiring_migration': deprecated_count + maintenance_count,
            'estimated_migration_effort': self._estimate_migration_effort(maintenance_status)
        }
        
        return maintenance_status
    
    def audit_production_readiness(self) -> Dict:
        """Assess production deployment readiness."""
        readiness_audit = {
            'missing_categories': [],
            'present_categories': [],
            'version_pinning_issues': [],
            'deployment_blockers': [],
            'summary': {}
        }
        
        present_packages = set(self.requirements.keys())
        
        # Check coverage of essential categories
        for category, required_packages in PRODUCTION_READINESS_CRITERIA.items():
            category_coverage = []
            for req_package in required_packages:
                if any(req_package in pkg for pkg in present_packages):
                    category_coverage.append(req_package)
            
            coverage_percentage = len(category_coverage) / len(required_packages) * 100
            
            if coverage_percentage >= 80:
                readiness_audit['present_categories'].append({
                    'category': category,
                    'coverage': coverage_percentage,
                    'present_packages': category_coverage
                })
            else:
                missing_packages = set(required_packages) - set(category_coverage)
                readiness_audit['missing_categories'].append({
                    'category': category,
                    'coverage': coverage_percentage,
                    'missing_packages': list(missing_packages),
                    'impact': 'HIGH' if coverage_percentage < 50 else 'MEDIUM'
                })
        
        # Check version pinning for critical packages
        critical_unpinned = []
        for package, (op, version_spec) in self.requirements.items():
            if op == 'unpinned' and package in ['fastapi', 'sqlalchemy', 'redis', 'openai']:
                critical_unpinned.append(package)
        
        if critical_unpinned:
            readiness_audit['version_pinning_issues'] = critical_unpinned
        
        # Calculate readiness score
        missing_critical = len([cat for cat in readiness_audit['missing_categories'] if cat['impact'] == 'HIGH'])
        missing_medium = len([cat for cat in readiness_audit['missing_categories'] if cat['impact'] == 'MEDIUM'])
        unpinned_critical = len(critical_unpinned)
        
        readiness_score = 100 - min(100, missing_critical * 25 + missing_medium * 10 + unpinned_critical * 5)
        
        readiness_audit['summary'] = {
            'readiness_score': readiness_score,
            'deployment_ready': readiness_score >= 85,
            'critical_gaps': missing_critical,
            'recommended_actions': self._generate_readiness_actions(readiness_audit)
        }
        
        return readiness_audit
    
    def generate_comprehensive_recommendations(self) -> Dict:
        """Generate prioritized, actionable recommendations."""
        recommendations = {
            'immediate_actions': [],
            'short_term': [],
            'medium_term': [],
            'long_term': [],
            'implementation_plan': {}
        }
        
        # Security recommendations (immediate)
        security_issues = self.audit_results['security_audit']
        for critical_issue in security_issues.get('critical', []):
            recommendations['immediate_actions'].append({
                'action': f"SECURITY FIX: {critical_issue['recommendation']}",
                'reason': f"Critical vulnerability: {critical_issue['vulnerability']['description']}",
                'estimated_effort': 'LOW',
                'business_impact': 'CRITICAL'
            })
        
        # Performance recommendations (short-term)
        performance_issues = self.audit_results['performance_audit']
        for high_impact in performance_issues.get('high_impact', []):
            recommendations['short_term'].append({
                'action': f"PERFORMANCE: {high_impact['recommendation']}",
                'reason': f"Performance improvements: {', '.join(high_impact['improvements_available'])}",
                'estimated_effort': 'MEDIUM',
                'business_impact': 'HIGH'
            })
        
        # Maintenance recommendations (medium-term)
        maintenance_issues = self.audit_results['maintenance_audit']
        for deprecated in maintenance_issues.get('deprecated', []):
            urgency = 'short_term' if deprecated.get('deadline') else 'medium_term'
            recommendations[urgency].append({
                'action': f"MIGRATION: {deprecated['migration_path']}",
                'reason': f"API deprecated: {deprecated['description']}",
                'estimated_effort': 'HIGH',
                'business_impact': 'MEDIUM',
                'deadline': deprecated.get('deadline')
            })
        
        return recommendations
    
    def _calculate_risk_level(self, score: int) -> str:
        """Calculate risk level based on score."""
        if score >= 90:
            return "LOW"
        elif score >= 70:
            return "MEDIUM"
        elif score >= 50:
            return "HIGH"
        else:
            return "CRITICAL"
    
    def _estimate_months_behind(self, current_ver, optimal_ver) -> int:
        """Estimate how many months behind the current version is."""
        # Simplified estimation - in reality, you'd check release dates
        return max(1, int((optimal_ver.major - current_ver.major) * 6 + 
                         (optimal_ver.minor - current_ver.minor) * 2))
    
    def _estimate_performance_gain(self, performance_issues: Dict) -> str:
        """Estimate overall performance gain from updates."""
        high_count = len(performance_issues.get('high_impact', []))
        medium_count = len(performance_issues.get('medium_impact', []))
        
        if high_count >= 3:
            return "30-50% performance improvement expected"
        elif high_count >= 1:
            return "15-30% performance improvement expected"
        elif medium_count >= 2:
            return "5-15% performance improvement expected"
        else:
            return "Minimal performance impact"
    
    def _estimate_migration_effort(self, maintenance_status: Dict) -> str:
        """Estimate effort required for package migrations."""
        deprecated_count = len(maintenance_status.get('deprecated', []))
        maintenance_count = len(maintenance_status.get('maintenance_mode', []))
        
        total_effort = deprecated_count * 3 + maintenance_count * 1  # days
        
        if total_effort >= 10:
            return "HIGH (2-3 weeks)"
        elif total_effort >= 5:
            return "MEDIUM (1 week)"
        else:
            return "LOW (1-2 days)"
    
    def _generate_readiness_actions(self, readiness_audit: Dict) -> List[str]:
        """Generate specific actions for production readiness."""
        actions = []
        
        for missing_cat in readiness_audit.get('missing_categories', []):
            if missing_cat['impact'] == 'HIGH':
                actions.append(f"Add {missing_cat['category']} packages: {', '.join(missing_cat['missing_packages'])}")
        
        if readiness_audit.get('version_pinning_issues'):
            actions.append(f"Pin critical packages: {', '.join(readiness_audit['version_pinning_issues'])}")
        
        return actions
    
    def run_comprehensive_audit(self) -> Dict:
        """Execute complete audit and generate report."""
        print("🔍 Running Comprehensive Requirements Audit...")
        print("=" * 60)
        
        # Run all audit components
        print("📊 Analyzing security vulnerabilities...")
        self.audit_results['security_audit'] = self.audit_security_vulnerabilities()
        
        print("⚡ Analyzing performance implications...")
        self.audit_results['performance_audit'] = self.audit_performance_implications()
        
        print("🔧 Analyzing maintenance status...")
        self.audit_results['maintenance_audit'] = self.audit_maintenance_status()
        
        print("🚀 Analyzing production readiness...")
        self.audit_results['production_readiness'] = self.audit_production_readiness()
        
        print("📋 Generating recommendations...")
        self.audit_results['recommendations'] = self.generate_comprehensive_recommendations()
        
        # Calculate overall risk assessment
        security_score = self.audit_results['security_audit']['summary']['security_score']
        performance_score = self.audit_results['performance_audit']['summary']['performance_score']
        maintenance_score = self.audit_results['maintenance_audit']['summary']['maintenance_score']
        readiness_score = self.audit_results['production_readiness']['summary']['readiness_score']
        
        overall_score = (security_score * 0.4 + readiness_score * 0.3 + 
                        maintenance_score * 0.2 + performance_score * 0.1)
        
        self.audit_results['risk_assessment'] = {
            'overall_score': round(overall_score, 1),
            'risk_level': self._calculate_risk_level(overall_score),
            'deployment_recommendation': self._get_deployment_recommendation(overall_score),
            'component_scores': {
                'security': security_score,
                'production_readiness': readiness_score,
                'maintenance': maintenance_score,
                'performance': performance_score
            }
        }
        
        return self.audit_results
    
    def _get_deployment_recommendation(self, score: int) -> str:
        """Get deployment recommendation based on overall score."""
        if score >= 90:
            return "READY FOR PRODUCTION - All systems green"
        elif score >= 80:
            return "PRODUCTION READY with minor improvements recommended"
        elif score >= 70:
            return "REQUIRES ATTENTION before production deployment"
        elif score >= 50:
            return "SIGNIFICANT ISSUES - Address before production"
        else:
            return "CRITICAL ISSUES - Do not deploy to production"
    
    def print_executive_summary(self):
        """Print executive summary of audit results."""
        risk_assessment = self.audit_results['risk_assessment']
        
        print(f"\n🎯 EXECUTIVE SUMMARY")
        print("=" * 50)
        print(f"Overall Score: {risk_assessment['overall_score']}/100")
        print(f"Risk Level: {risk_assessment['risk_level']}")
        print(f"Deployment Status: {risk_assessment['deployment_recommendation']}")
        
        # Component breakdown
        print(f"\n📊 Component Scores:")
        for component, score in risk_assessment['component_scores'].items():
            print(f"  {component.title()}: {score}/100")
        
        # Critical issues summary
        security_summary = self.audit_results['security_audit']['summary']
        if security_summary['requires_immediate_action']:
            print(f"\n🚨 CRITICAL: {len(self.audit_results['security_audit']['critical'])} security vulnerabilities require immediate attention")
        
        # Top recommendations
        immediate_actions = self.audit_results['recommendations']['immediate_actions']
        if immediate_actions:
            print(f"\n⚡ IMMEDIATE ACTIONS REQUIRED:")
            for action in immediate_actions[:3]:  # Top 3
                print(f"  • {action['action']}")
        
        print(f"\n📁 Detailed report saved to: comprehensive_audit_report.json")


def main():
    """Run comprehensive requirements audit."""
    try:
        auditor = ComprehensiveRequirementsAuditor()
        results = auditor.run_comprehensive_audit()
        
        # Save detailed report
        with open('comprehensive_audit_report.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Print executive summary
        auditor.print_executive_summary()
        
        # Return appropriate exit code
        overall_score = results['risk_assessment']['overall_score']
        if overall_score >= 80:
            return 0  # Success
        elif overall_score >= 70:
            return 1  # Warning
        else:
            return 2  # Error
        
    except Exception as e:
        print(f"❌ Audit failed: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())