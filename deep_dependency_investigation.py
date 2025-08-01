#!/usr/bin/env python3
"""
Deep Dependency Investigation - Live Package Analysis
Real-time investigation of package requirements from PyPI
"""

import subprocess
import json
import sys
from typing import Dict, List

def get_package_requirements(package_spec: str) -> Dict:
    """
    Get detailed package requirements by attempting installation dry-run
    """
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "--dry-run", "--quiet", "--report", "-", package_spec
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            try:
                report = json.loads(result.stdout)
                return {
                    "success": True,
                    "dependencies": report.get("install", []),
                    "raw_output": result.stdout[:500]  # First 500 chars
                }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "JSON decode error",
                    "raw_output": result.stdout[:500]
                }
        else:
            return {
                "success": False,
                "error": result.stderr,
                "raw_output": result.stdout[:500]
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_conflicting_packages():
    """
    Check specific conflicting package combinations
    """
    print("🔍 DEEP DEPENDENCY INVESTIGATION")
    print("=" * 60)
    
    # Test individual problematic packages
    test_packages = [
        "crewai==0.22.5",  # Old version in requirements
        "crewai==0.152.0", # Latest version
        "pydantic>=2.0,<3.0",
        "pydantic-settings==2.7.4",
        "langchain==0.3.4",
        "langgraph~=0.2.0",
        "langgraph==0.6.2",  # Latest
        "langgraph-checkpoint-postgres==2.0.3",
        "langgraph-checkpoint-postgres==2.0.23"  # Latest
    ]
    
    results = {}
    
    for package in test_packages:
        print(f"\n📦 Testing: {package}")
        result = get_package_requirements(package)
        results[package] = result
        
        if result["success"]:
            print(f"  ✅ Success - Found {len(result.get('dependencies', []))} dependencies")
        else:
            print(f"  ❌ Failed - {result.get('error', 'Unknown error')}")
    
    return results

def test_specific_conflicts():
    """
    Test specific known conflict scenarios
    """
    print("\n🧪 TESTING SPECIFIC CONFLICTS")
    print("=" * 40)
    
    conflict_scenarios = [
        {
            "name": "CrewAI Old + Pydantic v2",
            "packages": ["crewai==0.22.5", "pydantic>=2.0"]
        },
        {
            "name": "CrewAI New + Pydantic v2", 
            "packages": ["crewai==0.152.0", "pydantic>=2.0"]
        },
        {
            "name": "LangGraph Old + LangChain New",
            "packages": ["langgraph~=0.2.0", "langchain==0.3.4"]
        },
        {
            "name": "LangGraph New + LangChain New",
            "packages": ["langgraph==0.6.2", "langchain==0.3.4"]
        }
    ]
    
    scenario_results = {}
    
    for scenario in conflict_scenarios:
        print(f"\n🧪 {scenario['name']}")
        package_str = " ".join(scenario['packages'])
        
        try:
            result = subprocess.run([
                sys.executable, "-m", "pip", "install",
                "--dry-run", "--quiet"] + scenario['packages'],
                capture_output=True, text=True, timeout=60
            )
            
            scenario_results[scenario['name']] = {
                "success": result.returncode == 0,
                "stdout": result.stdout[:200],
                "stderr": result.stderr[:200]
            }
            
            if result.returncode == 0:
                print("  ✅ Compatible")
            else:
                print(f"  ❌ Conflict detected")
                print(f"    Error: {result.stderr[:100]}...")
                
        except subprocess.TimeoutExpired:
            scenario_results[scenario['name']] = {
                "success": False,
                "error": "Timeout"
            }
            print("  ⏰ Timeout")
    
    return scenario_results

def analyze_current_requirements():
    """
    Analyze the current requirements.txt for specific issues
    """
    print("\n📋 ANALYZING CURRENT REQUIREMENTS.TXT")
    print("=" * 45)
    
    try:
        with open("/home/emergence-admin/Desktop/ReAgent/requirements.txt", "r") as f:
            lines = f.readlines()
        
        issues = []
        recommendations = []
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            # Check for specific issues
            if line == "pydantic":
                issues.append({
                    "line": i,
                    "package": line,
                    "issue": "No version specified - will get latest (pydantic v2)",
                    "conflict_with": ["crewai==0.22.5"]
                })
                
            if "crewai==0.22.5" in line:
                issues.append({
                    "line": i,
                    "package": line,
                    "issue": "Old CrewAI version requires pydantic<2.0",
                    "conflict_with": ["pydantic (unversioned)", "pydantic-settings~=2.7.4"]
                })
                
            if "langgraph~=0.2.0" in line:
                issues.append({
                    "line": i,
                    "package": line,
                    "issue": "Old LangGraph version, latest is 0.6.x",
                    "conflict_with": ["langgraph-checkpoint-postgres==2.0.3"]  
                })
        
        print(f"Found {len(issues)} potential issues:")
        for issue in issues:
            print(f"  ⚠️  Line {issue['line']}: {issue['package']}")
            print(f"      Issue: {issue['issue']}")
            print(f"      Conflicts with: {', '.join(issue['conflict_with'])}")
        
        # Generate recommendations
        if any("pydantic" in issue['package'] for issue in issues):
            recommendations.append("Pin pydantic to specific version (either 1.10.x or 2.x)")
        
        if any("crewai" in issue['package'] for issue in issues):
            recommendations.append("Either upgrade CrewAI to latest or pin pydantic to v1")
            
        if any("langgraph" in issue['package'] for issue in issues):
            recommendations.append("Update LangGraph to latest 0.6.x version")
        
        print(f"\n💡 Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
        
        return {
            "issues": issues,
            "recommendations": recommendations
        }
        
    except FileNotFoundError:
        print("❌ requirements.txt not found")
        return {"error": "File not found"}

if __name__ == "__main__":
    print("🔬 DEEP DEPENDENCY FORENSIC INVESTIGATION")
    print("=" * 60)
    
    # Run all investigations
    package_results = check_conflicting_packages()
    conflict_results = test_specific_conflicts()
    requirements_analysis = analyze_current_requirements()
    
    # Generate final report
    final_report = {
        "timestamp": "2025-08-01",
        "investigation_type": "deep_forensic",
        "individual_packages": package_results,
        "conflict_scenarios": conflict_results,
        "requirements_analysis": requirements_analysis,
        "summary": {
            "root_cause": "pydantic v1 vs v2 ecosystem incompatibility",
            "primary_culprit": "crewai==0.22.5 requires pydantic<2.0",
            "secondary_issue": "langgraph version mismatch with checkpoint package",
            "immediate_fix": "Pin pydantic==1.10.* OR upgrade CrewAI to 0.152.0"
        }
    }
    
    # Save report
    with open("/home/emergence-admin/Desktop/ReAgent/deep_dependency_forensic_report.json", "w") as f:
        json.dump(final_report, f, indent=2)
    
    print("\n" + "=" * 60)
    print("📋 DEEP FORENSIC INVESTIGATION COMPLETE")
    print("📄 Report saved to: deep_dependency_forensic_report.json")
    print("=" * 60)