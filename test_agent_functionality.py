#!/usr/bin/env python3
"""
ReAgent Sydney - Agent Functionality Test
Tests individual agent modules and basic functionality
"""

import sys
import os
import importlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

class AgentFunctionalityTester:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test_status": "unknown",
            "agents": {},
            "imports": {},
            "modules": {},
            "issues": [],
            "summary": {}
        }
        
    def log_result(self, component: str, status: str, details: str = ""):
        """Log test result"""
        status_symbol = "✅" if status == "success" else "⚠️" if status == "warning" else "❌"
        print(f"{status_symbol} {component}: {details}")
        
    def test_agent_imports(self):
        """Test if agent modules can be imported"""
        print("\n=== AGENT IMPORT TESTS ===")
        
        agents_to_test = [
            ("listing_watcher", "src.reagent.agents.listing_watcher.agent"),
            ("suburb_signal", "src.reagent.agents.suburb_signal.agent"),
            ("buyer_matchmaker", "src.reagent.agents.buyer_matchmaker.agent"),
            ("seller_strategy", "src.reagent.agents.seller_strategy.agent"),
            ("off_market_radar", "src.reagent.agents.off_market_radar.agent"),
            ("agent_whisperer", "src.reagent.agents.agent_whisperer.agent")
        ]
        
        for agent_name, module_path in agents_to_test:
            try:
                module = importlib.import_module(module_path)
                self.log_result(f"{agent_name} Import", "success", f"Module loaded: {module_path}")
                
                # Check for main agent class
                agent_classes = [attr for attr in dir(module) if 'Agent' in attr and not attr.startswith('_')]
                if agent_classes:
                    self.log_result(f"{agent_name} Classes", "success", f"Found classes: {agent_classes}")
                    self.results["agents"][agent_name] = {
                        "import_status": "success",
                        "module_path": module_path,
                        "classes": agent_classes,
                        "attributes": len(dir(module))
                    }
                else:
                    self.log_result(f"{agent_name} Classes", "warning", "No Agent classes found")
                    self.results["agents"][agent_name] = {
                        "import_status": "success",
                        "module_path": module_path,
                        "classes": [],
                        "warning": "No Agent classes found"
                    }
                    
            except ImportError as e:
                self.log_result(f"{agent_name} Import", "error", f"Import failed: {str(e)}")
                self.results["agents"][agent_name] = {
                    "import_status": "error",
                    "module_path": module_path,
                    "error": str(e)
                }
                self.results["issues"].append({
                    "component": agent_name,
                    "severity": "error",
                    "message": f"Import failed: {str(e)}"
                })
            except Exception as e:
                self.log_result(f"{agent_name} Import", "error", f"Unexpected error: {str(e)}")
                self.results["agents"][agent_name] = {
                    "import_status": "error",
                    "module_path": module_path,
                    "error": f"Unexpected error: {str(e)}"
                }
                
    def test_core_modules(self):
        """Test core system modules"""
        print("\n=== CORE MODULE TESTS ===")
        
        core_modules = [
            ("database", "src.reagent.core.database.engine"),
            ("cache", "src.reagent.core.cache.redis_client"),
            ("vector_db", "src.reagent.core.vector_db.client"),
            ("orchestration", "src.reagent.orchestration.graph"),
            ("config", "src.reagent.core.config")
        ]
        
        for module_name, module_path in core_modules:
            try:
                module = importlib.import_module(module_path)
                self.log_result(f"{module_name} Module", "success", f"Core module loaded")
                
                self.results["modules"][module_name] = {
                    "import_status": "success",
                    "module_path": module_path,
                    "attributes": len(dir(module))
                }
                
            except ImportError as e:
                self.log_result(f"{module_name} Module", "error", f"Import failed: {str(e)}")
                self.results["modules"][module_name] = {
                    "import_status": "error",
                    "module_path": module_path,
                    "error": str(e)
                }
            except Exception as e:
                self.log_result(f"{module_name} Module", "error", f"Unexpected error: {str(e)}")
                
    def test_orchestration_components(self):
        """Test orchestration system components"""
        print("\n=== ORCHESTRATION TESTS ===")
        
        try:
            # Test state management
            from src.reagent.orchestration.state import AgentState
            self.log_result("AgentState", "success", "State class imported successfully")
            
            # Test nodes
            from src.reagent.orchestration.nodes.base_node import BaseNode
            self.log_result("BaseNode", "success", "Base node class imported")
            
            # Test graph construction
            from src.reagent.orchestration.graph import create_reagent_graph
            self.log_result("Graph Creation", "success", "Graph creation function imported")
            
            self.results["orchestration"] = {
                "state_management": "success",
                "node_system": "success", 
                "graph_creation": "success"
            }
            
        except ImportError as e:
            self.log_result("Orchestration", "error", f"Import failed: {str(e)}")
            self.results["orchestration"] = {"status": "error", "error": str(e)}
        except Exception as e:
            self.log_result("Orchestration", "error", f"Unexpected error: {str(e)}")
            
    def test_database_models(self):
        """Test database model definitions"""
        print("\n=== DATABASE MODEL TESTS ===")
        
        model_modules = [
            ("property_models", "src.reagent.data.models.property_models"),
            ("buyer_models", "src.reagent.data.models.buyer_models"),
            ("market_models", "src.reagent.data.models.market_models"),
            ("agent_models", "src.reagent.data.models.agent_models")
        ]
        
        for model_name, module_path in model_modules:
            try:
                module = importlib.import_module(module_path)
                
                # Count model classes (typically inherit from Base)
                model_classes = [attr for attr in dir(module) 
                               if not attr.startswith('_') and 
                               hasattr(getattr(module, attr), '__tablename__') if hasattr(getattr(module, attr), '__tablename__')]
                
                self.log_result(f"{model_name}", "success", f"Models loaded: {len(model_classes)}")
                
            except ImportError as e:
                self.log_result(f"{model_name}", "error", f"Import failed: {str(e)}")
            except Exception as e:
                self.log_result(f"{model_name}", "error", f"Unexpected error: {str(e)}")
                
    def check_file_structure(self):
        """Check critical file and directory structure"""
        print("\n=== FILE STRUCTURE CHECK ===")
        
        critical_paths = [
            "src/reagent/agents/listing_watcher/agent.py",
            "src/reagent/agents/suburb_signal/agent.py", 
            "src/reagent/agents/buyer_matchmaker/agent.py",
            "src/reagent/agents/seller_strategy/agent.py",
            "src/reagent/agents/off_market_radar/agent.py",
            "src/reagent/agents/agent_whisperer/agent.py",
            "src/reagent/orchestration/graph.py",
            "src/reagent/core/database/engine.py",
            "src/reagent/data/models/"
        ]
        
        for path in critical_paths:
            full_path = Path(path)
            if full_path.exists():
                if full_path.is_file():
                    size = full_path.stat().st_size
                    self.log_result(f"File: {path}", "success", f"Size: {size} bytes")
                else:
                    files = list(full_path.glob("*.py"))
                    self.log_result(f"Directory: {path}", "success", f"Python files: {len(files)}")
            else:
                self.log_result(f"Missing: {path}", "error", "File/directory not found")
                self.results["issues"].append({
                    "component": "file_structure",
                    "severity": "error",
                    "message": f"Missing critical path: {path}"
                })
                
    def analyze_test_results(self):
        """Analyze overall test results"""
        print("\n=== TEST ANALYSIS ===")
        
        successful_agents = len([agent for agent in self.results["agents"].values() 
                               if agent.get("import_status") == "success"])
        total_agents = len(self.results["agents"])
        
        successful_modules = len([module for module in self.results["modules"].values()
                                if module.get("import_status") == "success"])
        total_modules = len(self.results["modules"])
        
        total_errors = len([issue for issue in self.results["issues"] if issue.get("severity") == "error"])
        total_warnings = len([issue for issue in self.results["issues"] if issue.get("severity") == "warning"])
        
        # Determine overall status
        if total_errors == 0 and successful_agents >= 5:
            self.results["test_status"] = "success"
            status_text = "SUCCESS"
        elif total_errors <= 2 and successful_agents >= 4:
            self.results["test_status"] = "partial"
            status_text = "PARTIAL SUCCESS"
        else:
            self.results["test_status"] = "failure"
            status_text = "FAILURE"
            
        self.results["summary"] = {
            "successful_agents": successful_agents,
            "total_agents": total_agents,
            "successful_modules": successful_modules,
            "total_modules": total_modules,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "overall_status": status_text
        }
        
        print(f"\n{'='*50}")
        print(f"🧪 AGENT FUNCTIONALITY TEST SUMMARY")
        print(f"{'='*50}")
        print(f"Overall Status: {status_text}")
        print(f"Agents: {successful_agents}/{total_agents} importable")
        print(f"Core Modules: {successful_modules}/{total_modules} importable")
        print(f"Issues: {total_errors} errors, {total_warnings} warnings")
        
    def run_agent_tests(self):
        """Run complete agent functionality tests"""
        print("🧪 REAGENT SYDNEY - AGENT FUNCTIONALITY TESTS")
        print("=" * 55)
        
        self.check_file_structure()
        self.test_agent_imports()
        self.test_core_modules()
        self.test_orchestration_components()
        self.test_database_models()
        self.analyze_test_results()
        
        # Save results
        report_filename = f"agent_functionality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        print(f"\nDetailed report saved to: {report_filename}")
        return self.results

def main():
    tester = AgentFunctionalityTester()
    results = tester.run_agent_tests()
    
    # Exit with appropriate code
    if results["test_status"] == "failure":
        sys.exit(2)
    elif results["test_status"] == "partial":
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()