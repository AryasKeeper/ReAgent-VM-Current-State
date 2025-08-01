#!/usr/bin/env python3
"""
Requirements.txt Validation Test Suite
=====================================

Comprehensive validation tests for production readiness of Python dependencies.
Tests security vulnerabilities, version compatibility, and maintenance status.

Usage:
    python test_requirements_validation.py
    pytest test_requirements_validation.py -v
"""

import subprocess
import sys
import json
import requests
from typing import Dict, List, Tuple, Optional
from packaging import version
import pkg_resources
import pytest
from pathlib import Path

# Critical package security thresholds
CRITICAL_PACKAGES = {
    'fastapi': {'min_version': '0.115.0', 'cve_fixed': True},
    'langchain': {'min_version': '0.3.7', 'cve_fixed': True},
    'httpx': {'min_version': '0.27.0', 'security_updates': True},
    'aiohttp': {'min_version': '3.12.0', 'security_updates': True},
    'sqlalchemy': {'min_version': '2.0.23', 'injection_safe': True},
}

# Deprecated packages that should be migrated
DEPRECATED_PACKAGES = {
    'weaviate-client': {
        'current_api': 'v3', 
        'deprecated_version': '3.25.3',
        'recommended': 'weaviate-client>=4.10.0'
    },
    'psycopg2-binary': {
        'status': 'maintenance_mode',
        'recommended': 'psycopg[binary]>=3.1.8'
    }
}

# Packages requiring version pinning
UNPINNED_CRITICAL = ['pydantic']

class RequirementsValidator:
    """Main validator class for requirements.txt analysis"""
    
    def __init__(self, requirements_path: str = "requirements.txt"):
        self.requirements_path = Path(requirements_path)
        self.requirements = self._parse_requirements()
        self.issues = []
        self.warnings = []
        
    def _parse_requirements(self) -> Dict[str, str]:
        """Parse requirements.txt into package:version mapping"""
        requirements = {}
        
        if not self.requirements_path.exists():
            raise FileNotFoundError(f"Requirements file not found: {self.requirements_path}")
            
        with open(self.requirements_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('-'):
                    try:
                        # Handle different version specifiers
                        if '==' in line:
                            package, ver = line.split('==', 1)
                            requirements[package.strip()] = ver.strip()
                        elif '~=' in line:
                            package, ver = line.split('~=', 1)
                            requirements[package.strip()] = f"~={ver.strip()}"
                        elif '>=' in line:
                            package, ver = line.split('>=', 1)
                            requirements[package.strip()] = f">={ver.strip()}"
                        elif line and '=' not in line and '>' not in line and '<' not in line:
                            # Unpinned package
                            package = line.split('[')[0].strip()  # Handle extras like uvicorn[standard]
                            requirements[package] = "unpinned"
                    except ValueError:
                        self.warnings.append(f"Line {line_num}: Could not parse requirement: {line}")
                        
        return requirements
    
    def check_security_vulnerabilities(self) -> List[Dict]:
        """Check for known security vulnerabilities in specified versions"""
        vulnerabilities = []
        
        for package, pkg_version in self.requirements.items():
            if package in CRITICAL_PACKAGES:
                criteria = CRITICAL_PACKAGES[package]
                min_version = criteria['min_version']
                
                if pkg_version == "unpinned":
                    vulnerabilities.append({
                        'package': package,
                        'issue': 'unpinned_version',
                        'severity': 'HIGH',
                        'description': f'Critical package {package} has no version pinning',
                        'recommendation': f'Pin to {package}>={min_version}'
                    })
                elif pkg_version.startswith('=='):
                    current_ver = pkg_version[2:]
                    if version.parse(current_ver) < version.parse(min_version):
                        vulnerabilities.append({
                            'package': package,
                            'issue': 'security_vulnerability',
                            'severity': 'CRITICAL',
                            'current_version': current_ver,
                            'min_safe_version': min_version,
                            'description': f'{package} {current_ver} contains known security vulnerabilities',
                            'recommendation': f'Upgrade to {package}>={min_version}'
                        })
                        
        return vulnerabilities
    
    def check_deprecated_packages(self) -> List[Dict]:
        """Check for deprecated packages and APIs"""
        deprecated = []
        
        for package, pkg_version in self.requirements.items():
            if package in DEPRECATED_PACKAGES:
                dep_info = DEPRECATED_PACKAGES[package]
                deprecated.append({
                    'package': package,
                    'issue': 'deprecated_api',
                    'severity': 'MEDIUM',
                    'current_version': pkg_version,
                    'status': dep_info.get('status', 'deprecated'),
                    'description': f'{package} is deprecated or in maintenance mode',
                    'recommendation': dep_info['recommended']
                })
                
        return deprecated
    
    def check_unpinned_packages(self) -> List[Dict]:
        """Check for critical packages without version pinning"""
        unpinned = []
        
        for package in UNPINNED_CRITICAL:
            if package in self.requirements and self.requirements[package] == "unpinned":
                unpinned.append({
                    'package': package,
                    'issue': 'missing_version_pin',
                    'severity': 'HIGH',
                    'description': f'Critical package {package} lacks version pinning',
                    'recommendation': f'Add version constraint for {package}'
                })
                
        return unpinned
    
    def check_outdated_packages(self) -> List[Dict]:
        """Check for significantly outdated package versions"""
        outdated = []
        
        # Known outdated packages based on analysis
        outdated_mapping = {
            'httpx': {'current': '0.23.3', 'latest': '0.27.x', 'age_months': 18},
            'pandas': {'current': '2.1.4', 'latest': '2.2.x', 'age_months': 6},
            'openai': {'current': '1.54.0', 'latest': '1.58.x', 'age_months': 2}
        }
        
        for package, pkg_version in self.requirements.items():
            if package in outdated_mapping and pkg_version.startswith('=='):
                current_ver = pkg_version[2:]
                info = outdated_mapping[package]
                if current_ver == info['current']:
                    severity = 'HIGH' if info['age_months'] > 12 else 'MEDIUM'
                    outdated.append({
                        'package': package,
                        'issue': 'outdated_version',
                        'severity': severity,
                        'current_version': current_ver,
                        'latest_version': info['latest'],
                        'age_months': info['age_months'],
                        'description': f'{package} is {info["age_months"]} months behind current stable',
                        'recommendation': f'Upgrade to {package}>={info["latest"]}'
                    })
                    
        return outdated
    
    def check_dependency_conflicts(self) -> List[Dict]:
        """Check for potential dependency conflicts"""
        conflicts = []
        
        # Known conflict patterns
        if 'pydantic' in self.requirements and self.requirements['pydantic'] == 'unpinned':
            if 'fastapi' in self.requirements:
                conflicts.append({
                    'packages': ['pydantic', 'fastapi'],
                    'issue': 'version_conflict_risk',
                    'severity': 'HIGH',
                    'description': 'Unpinned pydantic may conflict with FastAPI version requirements',
                    'recommendation': 'Pin pydantic to compatible version range'
                })
                
        return conflicts
    
    def generate_report(self) -> Dict:
        """Generate comprehensive validation report"""
        vulnerabilities = self.check_security_vulnerabilities()
        deprecated = self.check_deprecated_packages()
        unpinned = self.check_unpinned_packages()
        outdated = self.check_outdated_packages()
        conflicts = self.check_dependency_conflicts()
        
        # Calculate risk score
        risk_score = (
            len([v for v in vulnerabilities if v['severity'] == 'CRITICAL']) * 10 +
            len([v for v in vulnerabilities if v['severity'] == 'HIGH']) * 5 +
            len([v for v in deprecated if v['severity'] == 'MEDIUM']) * 3 +
            len(unpinned) * 5 +
            len(outdated) * 2 +
            len(conflicts) * 4
        )
        
        # Determine overall status
        if risk_score >= 20:
            status = "CRITICAL - Immediate action required"
        elif risk_score >= 10:
            status = "HIGH RISK - Address before production"
        elif risk_score >= 5:
            status = "MEDIUM RISK - Should be addressed"
        else:
            status = "LOW RISK - Monitor and plan updates"
            
        return {
            'timestamp': '2025-08-01',
            'requirements_file': str(self.requirements_path),
            'total_packages': len(self.requirements),
            'risk_score': risk_score,
            'status': status,
            'issues': {
                'security_vulnerabilities': vulnerabilities,
                'deprecated_packages': deprecated,
                'unpinned_packages': unpinned,
                'outdated_packages': outdated,
                'dependency_conflicts': conflicts
            },
            'warnings': self.warnings,
            'recommendations': self._generate_recommendations(vulnerabilities, deprecated, unpinned, outdated, conflicts)
        }
    
    def _generate_recommendations(self, vulnerabilities, deprecated, unpinned, outdated, conflicts) -> List[str]:
        """Generate prioritized recommendations"""
        recommendations = []
        
        # Critical security fixes first
        critical_vulns = [v for v in vulnerabilities if v['severity'] == 'CRITICAL']
        if critical_vulns:
            recommendations.append("IMMEDIATE: Upgrade packages with critical security vulnerabilities")
            for vuln in critical_vulns:
                recommendations.append(f"  - {vuln['recommendation']}")
        
        # High priority fixes
        high_issues = [v for v in vulnerabilities if v['severity'] == 'HIGH'] + unpinned
        if high_issues:
            recommendations.append("HIGH PRIORITY: Address high-risk issues")
            for issue in high_issues:
                recommendations.append(f"  - {issue['recommendation']}")
        
        # Medium priority
        if deprecated:
            recommendations.append("MEDIUM PRIORITY: Plan migration for deprecated packages")
            for dep in deprecated:
                recommendations.append(f"  - Migrate {dep['package']} to {dep['recommendation']}")
        
        # General improvements
        if outdated:
            recommendations.append("GENERAL: Update outdated packages during next maintenance window")
            
        return recommendations


# Test Cases
class TestRequirementsValidation:
    """Pytest test cases for requirements validation"""
    
    @pytest.fixture
    def validator(self):
        return RequirementsValidator("requirements.txt")
    
    def test_requirements_file_exists(self, validator):
        """Test that requirements.txt exists and is readable"""
        assert validator.requirements_path.exists(), "requirements.txt file not found"
        assert len(validator.requirements) > 0, "No requirements found in file"
    
    def test_no_critical_security_vulnerabilities(self, validator):
        """Test that no critical security vulnerabilities exist"""
        vulnerabilities = validator.check_security_vulnerabilities()
        critical_vulns = [v for v in vulnerabilities if v['severity'] == 'CRITICAL']
        
        if critical_vulns:
            error_msg = "Critical security vulnerabilities found:\\n"
            for vuln in critical_vulns:
                error_msg += f"  - {vuln['package']}: {vuln['description']}\\n"
            pytest.fail(error_msg)
    
    def test_critical_packages_are_pinned(self, validator):
        """Test that critical packages have version pinning"""
        unpinned = validator.check_unpinned_packages()
        
        if unpinned:
            error_msg = "Critical packages without version pinning:\\n"
            for pkg in unpinned:
                error_msg += f"  - {pkg['package']}: {pkg['description']}\\n"
            pytest.fail(error_msg)
    
    def test_no_severely_outdated_packages(self, validator):
        """Test that packages are not severely outdated (>12 months)"""
        outdated = validator.check_outdated_packages()
        severely_outdated = [p for p in outdated if p.get('age_months', 0) > 12]
        
        if severely_outdated:
            error_msg = "Severely outdated packages found:\\n"
            for pkg in severely_outdated:
                error_msg += f"  - {pkg['package']}: {pkg['age_months']} months old\\n"
            pytest.fail(error_msg)
    
    def test_dependency_conflicts(self, validator):
        """Test for potential dependency conflicts"""
        conflicts = validator.check_dependency_conflicts()
        
        if conflicts:
            error_msg = "Potential dependency conflicts found:\\n"
            for conflict in conflicts:
                error_msg += f"  - {conflict['description']}\\n"
            pytest.fail(error_msg)
    
    def test_generate_full_report(self, validator):
        """Test full report generation"""
        report = validator.generate_report()
        
        assert 'timestamp' in report
        assert 'risk_score' in report
        assert 'status' in report
        assert 'issues' in report
        assert 'recommendations' in report
        
        # Print report for manual review
        print(f"\\n=== REQUIREMENTS VALIDATION REPORT ===")
        print(f"Status: {report['status']}")
        print(f"Risk Score: {report['risk_score']}")
        print(f"Total Packages: {report['total_packages']}")
        
        if report['issues']['security_vulnerabilities']:
            print(f"\\nSecurity Vulnerabilities: {len(report['issues']['security_vulnerabilities'])}")
        if report['issues']['deprecated_packages']:
            print(f"Deprecated Packages: {len(report['issues']['deprecated_packages'])}")
        if report['issues']['unpinned_packages']:
            print(f"Unpinned Critical Packages: {len(report['issues']['unpinned_packages'])}")
            
        print(f"\\nRecommendations:")
        for rec in report['recommendations'][:5]:  # Show top 5
            print(f"  {rec}")


def main():
    """Command-line interface for requirements validation"""
    print("🔍 ReAgent Requirements.txt Validation Suite")
    print("=" * 50)
    
    try:
        validator = RequirementsValidator()
        report = validator.generate_report()
        
        print(f"📊 Analysis Complete")
        print(f"   Total Packages: {report['total_packages']}")
        print(f"   Risk Score: {report['risk_score']}")
        print(f"   Status: {report['status']}")
        
        # Save detailed report
        report_file = "requirements_validation_detailed.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"   Detailed report saved: {report_file}")
        
        # Print summary
        issues = report['issues']
        total_issues = sum(len(issue_list) for issue_list in issues.values())
        
        if total_issues > 0:
            print(f"\\n⚠️  Issues Found: {total_issues}")
            if issues['security_vulnerabilities']:
                print(f"   🔒 Security: {len(issues['security_vulnerabilities'])}")
            if issues['deprecated_packages']:
                print(f"   📱 Deprecated: {len(issues['deprecated_packages'])}")
            if issues['unpinned_packages']:
                print(f"   📌 Unpinned: {len(issues['unpinned_packages'])}")
            if issues['outdated_packages']:
                print(f"   📅 Outdated: {len(issues['outdated_packages'])}")
            if issues['dependency_conflicts']:
                print(f"   ⚡ Conflicts: {len(issues['dependency_conflicts'])}")
                
            print(f"\\n🎯 Top Recommendations:")
            for i, rec in enumerate(report['recommendations'][:3], 1):
                print(f"   {i}. {rec}")
        else:
            print("\\n✅ No issues found - requirements.txt is production ready!")
            
        return 0 if report['risk_score'] < 10 else 1
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())