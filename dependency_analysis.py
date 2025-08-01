#!/usr/bin/env python3
"""
Dependency Conflict Detective - Root Cause Analysis
Forensic investigation of ReAgent Sydney dependency hell
"""

import subprocess
import json
import re
from typing import Dict, List, Tuple, Set
from packaging import version
from packaging.requirements import Requirement

class DependencyDetective:
    """
    🔍 Forensic dependency conflict analyzer
    """
    
    def __init__(self):
        self.conflicts = []
        self.package_info = {}
        self.dependency_tree = {}
        
    def get_package_metadata(self, package_name: str) -> Dict:
        """Get package metadata from PyPI"""
        try:
            result = subprocess.run(
                ["python3", "-m", "pip", "show", package_name],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                metadata = {}
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip()
                return metadata
        except subprocess.TimeoutExpired:
            pass
        return {}
    
    def check_package_versions(self, package_name: str) -> List[str]:
        """Get available versions for a package"""
        try:
            result = subprocess.run(
                ["python3", "-m", "pip", "index", "versions", package_name],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                # Parse versions from output
                versions = []
                for line in result.stdout.split('\n'):
                    if 'Available versions:' in line:
                        version_line = line.split('Available versions:')[1].strip()
                        versions = [v.strip() for v in version_line.split(',') if v.strip()]
                        break
                return versions[:10]  # Return top 10 versions
        except subprocess.TimeoutExpired:
            pass
        return []
    
    def analyze_pydantic_ecosystem(self) -> Dict:
        """
        Deep dive into pydantic v1 vs v2 ecosystem conflicts
        """
        print("🔍 ANALYZING PYDANTIC ECOSYSTEM CONFLICTS")
        
        pydantic_packages = [
            "pydantic",
            "pydantic-settings", 
            "fastapi",
            "langchain",
            "langchain-core",
            "crewai"
        ]
        
        analysis = {
            "pydantic_v1_packages": [],
            "pydantic_v2_packages": [],
            "conflicts": [],
            "recommendations": []
        }
        
        # Known pydantic v1 vs v2 requirements
        pydantic_v1_required = ["crewai<=0.22.5"]
        pydantic_v2_required = ["fastapi>=0.100", "pydantic-settings>=2.0"]
        
        for pkg in pydantic_packages:
            versions = self.check_package_versions(pkg)
            if versions:
                print(f"  📦 {pkg}: Latest versions {versions[:3]}")
        
        # Check specific conflicts
        analysis["conflicts"].append({
            "issue": "CrewAI 0.22.5 requires pydantic<2.0",
            "affected_packages": ["crewai", "pydantic"],
            "resolution": "Pin pydantic==1.10.* OR upgrade CrewAI to newer version"
        })
        
        analysis["conflicts"].append({
            "issue": "FastAPI 0.104.1 works with both pydantic v1 and v2 but pydantic-settings 2.7.4 requires pydantic>=2.0",
            "affected_packages": ["fastapi", "pydantic", "pydantic-settings"],
            "resolution": "Use pydantic>=2.0 with compatible packages"
        })
        
        return analysis
    
    def analyze_langchain_ecosystem(self) -> Dict:
        """
        Deep dive into langchain version conflicts
        """
        print("🔍 ANALYZING LANGCHAIN ECOSYSTEM CONFLICTS")
        
        langchain_packages = [
            "langchain",
            "langchain-core", 
            "langchain-openai",
            "langgraph",
            "langgraph-checkpoint-postgres"
        ]
        
        analysis = {
            "version_matrix": {},
            "conflicts": [],
            "recommendations": []
        }
        
        # Known version constraints
        constraints = {
            "langchain==0.3.4": "requires langchain-core>=0.3.0,<0.4.0",
            "langgraph~=0.2.0": "requires langchain-core>=0.2.0",
            "langgraph-checkpoint-postgres==2.0.3": "may require newer langgraph version"
        }
        
        for pkg in langchain_packages:
            versions = self.check_package_versions(pkg)
            if versions:
                analysis["version_matrix"][pkg] = versions[:5]
                print(f"  📦 {pkg}: {versions[:3]}")
        
        # Specific conflict analysis
        analysis["conflicts"].append({
            "issue": "langgraph-checkpoint-postgres 2.0.3 may require langgraph>=0.2.28",
            "affected_packages": ["langgraph", "langgraph-checkpoint-postgres"],
            "resolution": "Update langgraph to latest 0.2.x version"
        })
        
        return analysis
    
    def test_clean_resolution(self) -> Dict:
        """
        Test dependency resolution in clean environment
        """
        print("🧪 TESTING CLEAN DEPENDENCY RESOLUTION")
        
        test_scenarios = [
            {
                "name": "pydantic_v2_ecosystem",
                "packages": [
                    "pydantic>=2.0,<3.0",
                    "pydantic-settings==2.7.4",
                    "fastapi==0.104.1"
                ]
            },
            {
                "name": "langchain_core_only",
                "packages": [
                    "langchain-core==0.3.12",
                    "langchain-openai==0.2.2"
                ]
            },
            {
                "name": "minimal_working_set",
                "packages": [
                    "fastapi==0.104.1",
                    "pydantic==2.5.0",
                    "langchain-core==0.3.12"
                ]
            }
        ]
        
        results = {}
        for scenario in test_scenarios:
            print(f"  🧪 Testing {scenario['name']}")
            # We'll simulate this since we can't actually create virtual envs
            results[scenario['name']] = {
                "status": "simulation",
                "packages": scenario['packages'],
                "expected_result": "Would test in isolated environment"
            }
        
        return results
    
    def generate_compatibility_matrix(self) -> Dict:
        """
        Generate version compatibility matrix
        """
        print("📊 GENERATING COMPATIBILITY MATRIX")
        
        matrix = {
            "pydantic": {
                "1.10.x": {
                    "compatible_with": ["crewai<=0.22.5", "fastapi<0.100"],
                    "incompatible_with": ["pydantic-settings>=2.0"]
                },
                "2.x": {
                    "compatible_with": ["fastapi>=0.100", "pydantic-settings>=2.0", "langchain>=0.1"],
                    "incompatible_with": ["crewai<=0.22.5"]
                }
            },
            "langchain": {
                "0.3.x": {
                    "requires": ["langchain-core>=0.3.0,<0.4.0"],
                    "compatible_with": ["langgraph>=0.2.0"]
                }
            }
        }
        
        return matrix
    
    def suggest_resolution_strategies(self) -> List[Dict]:
        """
        Suggest multiple resolution strategies
        """
        print("💡 GENERATING RESOLUTION STRATEGIES")
        
        strategies = [
            {
                "name": "Strategy 1: Pydantic v2 + CrewAI Alternative",
                "approach": "Remove CrewAI, use pydantic v2 ecosystem",
                "changes": [
                    "Remove crewai==0.22.5",
                    "Set pydantic>=2.0,<3.0",
                    "Keep pydantic-settings==2.7.4",
                    "Replace CrewAI with direct LangGraph orchestration"
                ],
                "risk": "Low - Modern stack",
                "effort": "Medium - Requires CrewAI migration"
            },
            {
                "name": "Strategy 2: Pydantic v1 Pinning",
                "approach": "Pin to pydantic v1 ecosystem",
                "changes": [
                    "Set pydantic>=1.10.0,<2.0",
                    "Downgrade pydantic-settings to v1.x",
                    "Keep crewai==0.22.5",
                    "May need FastAPI version adjustment"
                ],
                "risk": "Medium - Using older pydantic",
                "effort": "Low - Minimal code changes"
            },
            {
                "name": "Strategy 3: Hybrid Approach",
                "approach": "Use virtual environments for conflicting agents",
                "changes": [
                    "Separate CrewAI agents in pydantic v1 environment",
                    "Main system uses pydantic v2",
                    "IPC between environments via Redis/HTTP"
                ],
                "risk": "Medium - Complex deployment",
                "effort": "High - Architecture changes"
            },
            {
                "name": "Strategy 4: Emergency Workaround",
                "approach": "Temporary fixes for immediate deployment",
                "changes": [
                    "Use pip-tools for exact resolution",
                    "Generate locked requirements.txt",
                    "Pin all transitive dependencies",
                    "Plan migration for next sprint"
                ],
                "risk": "High - Technical debt",
                "effort": "Low - Quick fix"
            }
        ]
        
        return strategies
    
    def run_full_analysis(self) -> Dict:
        """
        Run complete dependency forensic analysis
        """
        print("🔍 DEPENDENCY CONFLICT ROOT CAUSE ANALYSIS")
        print("=" * 60)
        
        report = {
            "timestamp": "2025-08-01",
            "analysis_type": "forensic_investigation",
            "pydantic_analysis": self.analyze_pydantic_ecosystem(),
            "langchain_analysis": self.analyze_langchain_ecosystem(),
            "compatibility_matrix": self.generate_compatibility_matrix(),
            "clean_resolution_tests": self.test_clean_resolution(),
            "resolution_strategies": self.suggest_resolution_strategies()
        }
        
        return report

if __name__ == "__main__":
    detective = DependencyDetective()
    analysis_report = detective.run_full_analysis()
    
    print("\n" + "=" * 60)
    print("📋 FORENSIC ANALYSIS COMPLETE")
    print("=" * 60)
    
    # Save detailed report
    with open("/home/emergence-admin/Desktop/ReAgent/dependency_forensic_report.json", "w") as f:
        json.dump(analysis_report, f, indent=2)
    
    print("📄 Detailed report saved to: dependency_forensic_report.json")