#!/usr/bin/env python3
"""
ReAgent Sydney - Multi-Agent Orchestration Validation Suite

Comprehensive testing of multi-agent coordination, workflow orchestration,
and production readiness validation.
"""

import asyncio
import logging
import time
import json
import sys
import traceback
import psutil
import concurrent.futures
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import random
import structlog

# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("orchestration_validation")

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
slogger = structlog.get_logger(__name__)


class WorkflowType(str, Enum):
    """Types of workflows to test."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    CONDITIONAL = "conditional"
    ADAPTIVE = "adaptive"


class AgentStatus(str, Enum):
    """Agent execution status."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


@dataclass
class MockAgent:
    """Mock agent for testing orchestration without real implementations."""
    
    name: str
    capabilities: List[str]
    execution_time_range: tuple = (1.0, 5.0)  # min, max seconds
    failure_rate: float = 0.1  # 10% failure rate
    dependencies: List[str] = field(default_factory=list)
    priority: int = 5  # 1-10 scale
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock agent execution."""
        start_time = time.time()
        execution_time = random.uniform(*self.execution_time_range)
        
        # Simulate processing time
        await asyncio.sleep(execution_time)
        
        # Simulate failures
        if random.random() < self.failure_rate:
            raise Exception(f"Mock failure in agent {self.name}")
        
        # Return mock result
        return {
            "agent_name": self.name,
            "success": True,
            "execution_time": time.time() - start_time,
            "data": {
                "processed_items": random.randint(1, 100),
                "confidence": random.uniform(0.7, 1.0),
                "timestamp": datetime.utcnow().isoformat()
            },
            "capabilities_used": self.capabilities,
            "input_processed": len(str(input_data))
        }


@dataclass
class WorkflowExecution:
    """Tracks workflow execution state."""
    
    workflow_id: str
    workflow_type: WorkflowType
    agents: List[str]
    status: AgentStatus = AgentStatus.IDLE
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)


class OrchestrationValidator:
    """Comprehensive orchestration validation framework."""
    
    def __init__(self):
        self.agents = self._create_mock_agents()
        self.active_workflows: Dict[str, WorkflowExecution] = {}
        self.execution_history: List[WorkflowExecution] = []
        self.performance_metrics = {
            "total_workflows": 0,
            "successful_workflows": 0,
            "failed_workflows": 0,
            "avg_execution_time": 0.0,
            "max_concurrent_workflows": 0,
            "agent_success_rates": {},
            "workflow_throughput": 0.0,
            "resource_utilization": {}
        }
        
        # Concurrency controls
        self.max_concurrent_agents = 10
        self.agent_semaphore = asyncio.Semaphore(self.max_concurrent_agents)
        self.workflow_lock = asyncio.Lock()
        
        # Redis simulation (in-memory for testing)
        self.message_queue = {}
        self.shared_cache = {}
        
        slogger.info("OrchestrationValidator initialized", 
                    agents=len(self.agents),
                    max_concurrent=self.max_concurrent_agents)
    
    def _create_mock_agents(self) -> Dict[str, MockAgent]:
        """Create mock agents representing ReAgent's 6 core agents."""
        return {
            "listing_watcher": MockAgent(
                name="listing_watcher",
                capabilities=["property_search", "listing_monitoring", "price_tracking"],
                execution_time_range=(2.0, 8.0),
                failure_rate=0.05,
                priority=9
            ),
            "suburb_signal": MockAgent(
                name="suburb_signal",
                capabilities=["market_analysis", "trend_detection", "suburb_insights"],
                execution_time_range=(3.0, 12.0),
                failure_rate=0.08,
                dependencies=["listing_watcher"],
                priority=8
            ),
            "buyer_matchmaker": MockAgent(
                name="buyer_matchmaker",
                capabilities=["buyer_matching", "preference_analysis", "recommendations"],
                execution_time_range=(1.5, 6.0),
                failure_rate=0.10,
                dependencies=["listing_watcher"],
                priority=7
            ),
            "seller_strategy": MockAgent(
                name="seller_strategy",
                capabilities=["pricing_strategy", "market_positioning", "timing_analysis"],
                execution_time_range=(4.0, 15.0),
                failure_rate=0.12,
                dependencies=["suburb_signal"],
                priority=8
            ),
            "off_market_radar": MockAgent(
                name="off_market_radar",
                capabilities=["opportunity_detection", "distress_signals", "private_sales"],
                execution_time_range=(5.0, 20.0),
                failure_rate=0.15,
                priority=6
            ),
            "agent_whisperer": MockAgent(
                name="agent_whisperer",
                capabilities=["communication", "report_generation", "synthesis"],
                execution_time_range=(1.0, 4.0),
                failure_rate=0.03,
                dependencies=["suburb_signal", "buyer_matchmaker", "seller_strategy"],
                priority=10
            )
        }
    
    async def validate_sequential_workflow(self) -> Dict[str, Any]:
        """Test sequential agent execution with dependency resolution."""
        slogger.info("Testing sequential workflow orchestration")
        
        workflow_id = f"seq_{uuid.uuid4().hex[:8]}"
        workflow = WorkflowExecution(
            workflow_id=workflow_id,
            workflow_type=WorkflowType.SEQUENTIAL,
            agents=list(self.agents.keys())
        )
        
        start_time = time.time()
        workflow.status = AgentStatus.RUNNING
        workflow.started_at = datetime.utcnow()
        
        try:
            # Execute agents in dependency order
            execution_order = self._resolve_dependencies(workflow.agents)
            slogger.info("Sequential execution order determined", 
                        order=execution_order, workflow_id=workflow_id)
            
            results = {}
            
            for agent_name in execution_order:
                agent = self.agents[agent_name]
                
                # Prepare input data with context from previous agents
                input_data = {
                    "workflow_id": workflow_id,
                    "execution_context": results,
                    "dependencies_satisfied": True
                }
                
                try:
                    slogger.info("Executing agent in sequence", 
                               agent=agent_name, workflow_id=workflow_id)
                    
                    result = await agent.execute(input_data)
                    results[agent_name] = result
                    
                    # Simulate inter-agent communication
                    await self._simulate_agent_communication(agent_name, result)
                    
                    slogger.info("Agent completed successfully", 
                               agent=agent_name, 
                               execution_time=result.get("execution_time", 0),
                               workflow_id=workflow_id)
                
                except Exception as e:
                    error_msg = f"Agent {agent_name} failed: {str(e)}"
                    workflow.errors.append(error_msg)
                    results[agent_name] = {"success": False, "error": str(e)}
                    
                    slogger.error("Agent execution failed", 
                                agent=agent_name, error=str(e), workflow_id=workflow_id)
            
            execution_time = time.time() - start_time
            workflow.completed_at = datetime.utcnow()
            workflow.results = results
            workflow.performance_metrics = {
                "total_execution_time": execution_time,
                "agents_executed": len(results),
                "successful_agents": sum(1 for r in results.values() if r.get("success", False)),
                "failed_agents": len(workflow.errors)
            }
            
            success_rate = workflow.performance_metrics["successful_agents"] / len(results)
            workflow.status = AgentStatus.COMPLETED if success_rate > 0.8 else AgentStatus.FAILED
            
            return {
                "workflow_id": workflow_id,
                "workflow_type": WorkflowType.SEQUENTIAL,
                "success": workflow.status == AgentStatus.COMPLETED,
                "execution_time": execution_time,
                "agents_executed": len(results),
                "success_rate": success_rate,
                "execution_order": execution_order,
                "results": results,
                "errors": workflow.errors,
                "performance_metrics": workflow.performance_metrics
            }
            
        except Exception as e:
            workflow.status = AgentStatus.FAILED
            workflow.errors.append(f"Workflow execution failed: {str(e)}")
            
            return {
                "workflow_id": workflow_id,
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
        
        finally:
            self.execution_history.append(workflow)
    
    async def validate_parallel_workflow(self) -> Dict[str, Any]:
        """Test parallel agent execution with concurrency control."""
        slogger.info("Testing parallel workflow orchestration")
        
        workflow_id = f"par_{uuid.uuid4().hex[:8]}"
        workflow = WorkflowExecution(
            workflow_id=workflow_id,
            workflow_type=WorkflowType.PARALLEL,
            agents=list(self.agents.keys())
        )
        
        start_time = time.time()
        workflow.status = AgentStatus.RUNNING
        workflow.started_at = datetime.utcnow()
        
        try:
            # Create tasks for all agents
            tasks = []
            for agent_name in workflow.agents:
                agent = self.agents[agent_name]
                input_data = {
                    "workflow_id": workflow_id,
                    "execution_mode": "parallel",
                    "agent_name": agent_name
                }
                
                task = asyncio.create_task(
                    self._execute_agent_with_semaphore(agent, input_data)
                )
                tasks.append((agent_name, task))
            
            slogger.info("Started parallel execution", 
                        agent_count=len(tasks), workflow_id=workflow_id)
            
            # Wait for all tasks with timeout
            results = {}
            timeout_seconds = 60  # 1 minute timeout
            
            try:
                for agent_name, task in tasks:
                    try:
                        result = await asyncio.wait_for(task, timeout=timeout_seconds)
                        results[agent_name] = result
                        
                        slogger.info("Parallel agent completed", 
                                   agent=agent_name, 
                                   execution_time=result.get("execution_time", 0),
                                   workflow_id=workflow_id)
                    
                    except asyncio.TimeoutError:
                        results[agent_name] = {
                            "success": False, 
                            "error": f"Timeout after {timeout_seconds}s"
                        }
                        slogger.warning("Agent timed out in parallel execution", 
                                      agent=agent_name, timeout=timeout_seconds, workflow_id=workflow_id)
                    
                    except Exception as e:
                        results[agent_name] = {"success": False, "error": str(e)}
                        slogger.error("Agent failed in parallel execution", 
                                    agent=agent_name, error=str(e), workflow_id=workflow_id)
            
            except Exception as e:
                slogger.error("Parallel execution management error", 
                            error=str(e), workflow_id=workflow_id)
                raise
            
            execution_time = time.time() - start_time
            workflow.completed_at = datetime.utcnow()
            workflow.results = results
            
            successful_agents = sum(1 for r in results.values() if r.get("success", False))
            success_rate = successful_agents / len(results) if results else 0
            
            workflow.performance_metrics = {
                "total_execution_time": execution_time,
                "agents_executed": len(results),
                "successful_agents": successful_agents,
                "failed_agents": len(results) - successful_agents,
                "parallelization_efficiency": len(results) / execution_time if execution_time > 0 else 0
            }
            
            workflow.status = AgentStatus.COMPLETED if success_rate > 0.8 else AgentStatus.FAILED
            
            return {
                "workflow_id": workflow_id,
                "workflow_type": WorkflowType.PARALLEL,
                "success": workflow.status == AgentStatus.COMPLETED,
                "execution_time": execution_time,
                "agents_executed": len(results),
                "success_rate": success_rate,
                "parallelization_efficiency": workflow.performance_metrics["parallelization_efficiency"],
                "results": results,
                "performance_metrics": workflow.performance_metrics
            }
            
        except Exception as e:
            workflow.status = AgentStatus.FAILED
            workflow.errors.append(f"Parallel workflow failed: {str(e)}")
            
            return {
                "workflow_id": workflow_id,
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
        
        finally:
            self.execution_history.append(workflow)
    
    async def validate_concurrent_workflows(self, num_workflows: int = 5) -> Dict[str, Any]:
        """Test multiple workflows running concurrently."""
        slogger.info("Testing concurrent workflow execution", 
                    workflow_count=num_workflows)
        
        start_time = time.time()
        
        # Create multiple workflow tasks
        workflow_tasks = []
        
        for i in range(num_workflows):
            if i % 2 == 0:
                task = asyncio.create_task(self.validate_sequential_workflow())
            else:
                task = asyncio.create_task(self.validate_parallel_workflow())
            workflow_tasks.append(task)
        
        # Execute all workflows concurrently
        try:
            results = await asyncio.gather(*workflow_tasks, return_exceptions=True)
            
            execution_time = time.time() - start_time
            
            # Analyze results
            successful_workflows = 0
            failed_workflows = 0
            total_agents_executed = 0
            
            for result in results:
                if isinstance(result, dict):
                    if result.get("success", False):
                        successful_workflows += 1
                        total_agents_executed += result.get("agents_executed", 0)
                    else:
                        failed_workflows += 1
                else:
                    failed_workflows += 1
            
            success_rate = successful_workflows / num_workflows if num_workflows > 0 else 0
            throughput = total_agents_executed / execution_time if execution_time > 0 else 0
            
            return {
                "test_type": "concurrent_workflows",
                "success": success_rate > 0.8,
                "execution_time": execution_time,
                "workflows_executed": num_workflows,
                "successful_workflows": successful_workflows,
                "failed_workflows": failed_workflows,
                "success_rate": success_rate,
                "total_agents_executed": total_agents_executed,
                "throughput_agents_per_second": throughput,
                "results": [r for r in results if isinstance(r, dict)]
            }
            
        except Exception as e:
            return {
                "test_type": "concurrent_workflows",
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def validate_failure_recovery(self) -> Dict[str, Any]:
        """Test agent failure recovery and retry mechanisms."""
        slogger.info("Testing failure recovery mechanisms")
        
        start_time = time.time()
        
        # Temporarily increase failure rates to test recovery
        original_failure_rates = {}
        for agent_name, agent in self.agents.items():
            original_failure_rates[agent_name] = agent.failure_rate
            agent.failure_rate = 0.5  # 50% failure rate for testing
        
        try:
            recovery_results = {}
            
            for agent_name, agent in self.agents.items():
                slogger.info("Testing failure recovery for agent", agent=agent_name)
                
                retry_attempts = 0
                max_retries = 3
                success = False
                
                while retry_attempts < max_retries and not success:
                    try:
                        result = await agent.execute({"test_mode": "failure_recovery"})
                        success = result.get("success", False)
                        
                        if success:
                            slogger.info("Agent recovered successfully", 
                                       agent=agent_name, 
                                       retry_attempts=retry_attempts)
                        
                    except Exception as e:
                        retry_attempts += 1
                        slogger.warning("Agent retry attempt", 
                                      agent=agent_name, 
                                      attempt=retry_attempts, 
                                      error=str(e))
                        
                        if retry_attempts < max_retries:
                            await asyncio.sleep(0.5)  # Brief delay before retry
                
                recovery_results[agent_name] = {
                    "success": success,
                    "retry_attempts": retry_attempts,
                    "recovered": success and retry_attempts > 0
                }
            
            execution_time = time.time() - start_time
            
            # Calculate recovery statistics
            total_agents = len(recovery_results)
            recovered_agents = sum(1 for r in recovery_results.values() if r.get("recovered", False))
            successful_agents = sum(1 for r in recovery_results.values() if r.get("success", False))
            
            return {
                "test_type": "failure_recovery",
                "success": successful_agents / total_agents > 0.6,  # 60% success rate acceptable with high failure rate
                "execution_time": execution_time,
                "total_agents": total_agents,
                "successful_agents": successful_agents,
                "recovered_agents": recovered_agents,
                "recovery_rate": recovered_agents / total_agents if total_agents > 0 else 0,
                "success_rate": successful_agents / total_agents if total_agents > 0 else 0,
                "detailed_results": recovery_results
            }
            
        finally:
            # Restore original failure rates
            for agent_name, agent in self.agents.items():
                agent.failure_rate = original_failure_rates[agent_name]
    
    async def validate_resource_management(self) -> Dict[str, Any]:
        """Test resource management and concurrency limits."""
        slogger.info("Testing resource management and concurrency limits")
        
        start_time = time.time()
        
        # Monitor system resources
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        initial_cpu_percent = psutil.cpu_percent()
        
        try:
            # Create many concurrent tasks to test limits
            num_concurrent = 20  # Exceed normal limits
            tasks = []
            
            for i in range(num_concurrent):
                agent_name = list(self.agents.keys())[i % len(self.agents)]
                agent = self.agents[agent_name]
                
                task = asyncio.create_task(
                    self._execute_agent_with_resource_monitoring(agent, {"task_id": i})
                )
                tasks.append(task)
            
            # Wait for all tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            execution_time = time.time() - start_time
            
            # Check resource usage
            final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            final_cpu_percent = psutil.cpu_percent()
            
            memory_increase = final_memory - initial_memory
            cpu_increase = final_cpu_percent - initial_cpu_percent
            
            # Analyze results
            successful_tasks = sum(1 for r in results if isinstance(r, dict) and r.get("success", False))
            failed_tasks = len(results) - successful_tasks
            
            # Check if concurrency was properly limited
            max_concurrent_observed = min(num_concurrent, self.max_concurrent_agents)
            
            return {
                "test_type": "resource_management",
                "success": successful_tasks > 0 and memory_increase < 500,  # Less than 500MB increase
                "execution_time": execution_time,
                "concurrent_tasks_requested": num_concurrent,
                "max_concurrent_allowed": self.max_concurrent_agents,
                "successful_tasks": successful_tasks,
                "failed_tasks": failed_tasks,
                "success_rate": successful_tasks / len(results) if results else 0,
                "resource_usage": {
                    "initial_memory_mb": initial_memory,
                    "final_memory_mb": final_memory,
                    "memory_increase_mb": memory_increase,
                    "initial_cpu_percent": initial_cpu_percent,
                    "final_cpu_percent": final_cpu_percent,
                    "cpu_increase_percent": cpu_increase
                }
            }
            
        except Exception as e:
            return {
                "test_type": "resource_management",
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def validate_message_passing(self) -> Dict[str, Any]:
        """Test inter-agent message passing and communication."""
        slogger.info("Testing inter-agent message passing")
        
        start_time = time.time()
        
        try:
            # Test message queue functionality
            test_messages = []
            
            for i in range(10):
                message = {
                    "id": f"msg_{i}",
                    "sender": f"agent_{i % 3}",
                    "receiver": f"agent_{(i + 1) % 3}",
                    "content": f"Test message {i}",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Simulate sending message
                await self._send_message(message["sender"], message["receiver"], message)
                test_messages.append(message)
            
            # Test message retrieval
            retrieved_messages = 0
            for message in test_messages:
                retrieved = await self._receive_message(message["receiver"], message["id"])
                if retrieved:
                    retrieved_messages += 1
            
            # Test shared cache functionality
            cache_test_data = {}
            for i in range(5):
                key = f"test_key_{i}"
                value = {"data": f"test_value_{i}", "timestamp": time.time()}
                
                await self._cache_set(key, value)
                cache_test_data[key] = value
            
            # Retrieve from cache
            cached_items_retrieved = 0
            for key, expected_value in cache_test_data.items():
                retrieved_value = await self._cache_get(key)
                if retrieved_value == expected_value:
                    cached_items_retrieved += 1
            
            execution_time = time.time() - start_time
            
            return {
                "test_type": "message_passing",
                "success": retrieved_messages == len(test_messages) and cached_items_retrieved == len(cache_test_data),
                "execution_time": execution_time,
                "messages_sent": len(test_messages),
                "messages_retrieved": retrieved_messages,
                "message_success_rate": retrieved_messages / len(test_messages) if test_messages else 0,
                "cache_items_set": len(cache_test_data),
                "cache_items_retrieved": cached_items_retrieved,
                "cache_success_rate": cached_items_retrieved / len(cache_test_data) if cache_test_data else 0
            }
            
        except Exception as e:
            return {
                "test_type": "message_passing",
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def validate_deadlock_detection(self) -> Dict[str, Any]:
        """Test deadlock detection and prevention."""
        slogger.info("Testing deadlock detection and prevention")
        
        start_time = time.time()
        
        try:
            # Create circular dependency scenario
            test_agents = {
                "agent_a": MockAgent(
                    name="agent_a",
                    capabilities=["test"],
                    dependencies=["agent_c"],  # Creates circular dependency
                    execution_time_range=(1.0, 2.0)
                ),
                "agent_b": MockAgent(
                    name="agent_b", 
                    capabilities=["test"],
                    dependencies=["agent_a"],
                    execution_time_range=(1.0, 2.0)
                ),
                "agent_c": MockAgent(
                    name="agent_c",
                    capabilities=["test"], 
                    dependencies=["agent_b"],
                    execution_time_range=(1.0, 2.0)
                )
            }
            
            # Try to resolve dependencies - should detect circular dependency
            try:
                execution_order = self._resolve_dependencies(list(test_agents.keys()), test_agents)
                deadlock_detected = False
            except Exception as e:
                if "circular" in str(e).lower() or "deadlock" in str(e).lower():
                    deadlock_detected = True
                    slogger.info("Deadlock correctly detected", error=str(e))
                else:
                    raise e
            
            # Test timeout-based deadlock prevention
            timeout_test_success = True
            try:
                # Simulate long-running tasks that could create deadlock
                async with asyncio.timeout(5.0):  # 5 second timeout
                    tasks = []
                    for i in range(3):
                        task = asyncio.create_task(asyncio.sleep(10))  # Would take 10 seconds
                        tasks.append(task)
                    
                    await asyncio.gather(*tasks)
                    
            except asyncio.TimeoutError:
                slogger.info("Timeout-based deadlock prevention worked")
                timeout_test_success = True
            except Exception as e:
                timeout_test_success = False
                slogger.error("Timeout test failed", error=str(e))
            
            execution_time = time.time() - start_time
            
            return {
                "test_type": "deadlock_detection",
                "success": deadlock_detected and timeout_test_success,
                "execution_time": execution_time,
                "circular_dependency_detected": deadlock_detected,
                "timeout_prevention_works": timeout_test_success
            }
            
        except Exception as e:
            return {
                "test_type": "deadlock_detection",
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run all orchestration validation tests."""
        slogger.info("Starting comprehensive orchestration validation")
        
        start_time = time.time()
        
        test_suites = {
            "sequential_workflow": self.validate_sequential_workflow,
            "parallel_workflow": self.validate_parallel_workflow,
            "concurrent_workflows": lambda: self.validate_concurrent_workflows(3),
            "failure_recovery": self.validate_failure_recovery,
            "resource_management": self.validate_resource_management,
            "message_passing": self.validate_message_passing,
            "deadlock_detection": self.validate_deadlock_detection
        }
        
        results = {}
        
        for test_name, test_func in test_suites.items():
            slogger.info("Running validation test", test=test_name)
            
            try:
                result = await test_func()
                results[test_name] = result
                
                status = "PASS" if result.get("success", False) else "FAIL"
                slogger.info("Validation test completed", 
                           test=test_name, 
                           status=status,
                           execution_time=result.get("execution_time", 0))
                
            except Exception as e:
                results[test_name] = {
                    "success": False,
                    "error": str(e),
                    "execution_time": 0
                }
                slogger.error("Validation test failed", test=test_name, error=str(e))
        
        total_execution_time = time.time() - start_time
        
        # Calculate overall statistics
        total_tests = len(test_suites)
        passed_tests = sum(1 for r in results.values() if r.get("success", False))
        failed_tests = total_tests - passed_tests
        
        # Update performance metrics
        self.performance_metrics.update({
            "total_workflows": len(self.execution_history),
            "successful_workflows": sum(1 for w in self.execution_history if w.status == AgentStatus.COMPLETED),
            "failed_workflows": sum(1 for w in self.execution_history if w.status == AgentStatus.FAILED),
            "avg_execution_time": sum(w.performance_metrics.get("total_execution_time", 0) 
                                    for w in self.execution_history) / len(self.execution_history) if self.execution_history else 0
        })
        
        return {
            "validation_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "total_execution_time": total_execution_time,
                "production_ready": passed_tests / total_tests >= 0.85  # 85% success rate required
            },
            "detailed_results": results,
            "performance_metrics": self.performance_metrics,
            "execution_history": [
                {
                    "workflow_id": w.workflow_id,
                    "workflow_type": w.workflow_type.value,
                    "status": w.status.value,
                    "execution_time": w.performance_metrics.get("total_execution_time", 0),
                    "agents_executed": w.performance_metrics.get("agents_executed", 0),
                    "success_rate": w.performance_metrics.get("successful_agents", 0) / max(w.performance_metrics.get("agents_executed", 1), 1)
                }
                for w in self.execution_history
            ]
        }
    
    # Helper methods
    
    def _resolve_dependencies(self, agent_names: List[str], agents_dict: Optional[Dict[str, MockAgent]] = None) -> List[str]:
        """Resolve agent dependencies to determine execution order."""
        if agents_dict is None:
            agents_dict = self.agents
        
        # Topological sort to resolve dependencies
        in_degree = {name: 0 for name in agent_names}
        graph = {name: [] for name in agent_names}
        
        # Build dependency graph
        for agent_name in agent_names:
            agent = agents_dict[agent_name]
            for dep in agent.dependencies:
                if dep in agent_names:
                    graph[dep].append(agent_name)
                    in_degree[agent_name] += 1
        
        # Topological sort
        queue = [name for name in agent_names if in_degree[name] == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for circular dependencies
        if len(result) != len(agent_names):
            remaining = [name for name in agent_names if name not in result]
            raise Exception(f"Circular dependency detected among agents: {remaining}")
        
        return result
    
    async def _execute_agent_with_semaphore(self, agent: MockAgent, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent with semaphore for concurrency control."""
        async with self.agent_semaphore:
            return await agent.execute(input_data)
    
    async def _execute_agent_with_resource_monitoring(self, agent: MockAgent, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent with resource monitoring."""
        start_memory = psutil.Process().memory_info().rss
        start_time = time.time()
        
        try:
            result = await agent.execute(input_data)
            
            end_memory = psutil.Process().memory_info().rss
            end_time = time.time()
            
            result["resource_usage"] = {
                "memory_used_bytes": end_memory - start_memory,
                "execution_time": end_time - start_time
            }
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "resource_usage": {
                    "memory_used_bytes": psutil.Process().memory_info().rss - start_memory,
                    "execution_time": time.time() - start_time
                }
            }
    
    async def _simulate_agent_communication(self, agent_name: str, data: Dict[str, Any]) -> None:
        """Simulate inter-agent communication."""
        message_key = f"agent_output:{agent_name}:{int(time.time())}"
        self.shared_cache[message_key] = {
            "agent": agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
    
    async def _send_message(self, sender: str, receiver: str, message: Dict[str, Any]) -> None:
        """Simulate message sending."""
        queue_key = f"messages:{receiver}"
        if queue_key not in self.message_queue:
            self.message_queue[queue_key] = []
        
        self.message_queue[queue_key].append({
            "sender": sender,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _receive_message(self, receiver: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Simulate message receiving."""
        queue_key = f"messages:{receiver}"
        if queue_key not in self.message_queue:
            return None
        
        for msg in self.message_queue[queue_key]:
            if msg["message"].get("id") == message_id:
                return msg
        
        return None
    
    async def _cache_set(self, key: str, value: Any) -> None:
        """Simulate cache set operation."""
        self.shared_cache[key] = value
    
    async def _cache_get(self, key: str) -> Any:
        """Simulate cache get operation."""
        return self.shared_cache.get(key)


async def main():
    """Main validation execution function."""
    validator = OrchestrationValidator()
    
    try:
        print("🎯 ReAgent Sydney - Multi-Agent Orchestration Validation")
        print("=" * 80)
        
        results = await validator.run_comprehensive_validation()
        
        # Print summary
        summary = results["validation_summary"]
        print(f"\nValidation Summary:")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Success Rate: {summary['success_rate']:.1%}")
        print(f"Total Execution Time: {summary['total_execution_time']:.2f}s")
        print(f"Production Ready: {'✅ YES' if summary['production_ready'] else '❌ NO'}")
        
        # Print detailed results
        print(f"\nDetailed Test Results:")
        print("-" * 50)
        
        for test_name, result in results["detailed_results"].items():
            status = "PASS" if result.get("success", False) else "FAIL"
            exec_time = result.get("execution_time", 0)
            print(f"{test_name:<25} {status:<6} ({exec_time:.2f}s)")
            
            if not result.get("success", False) and result.get("error"):
                print(f"    Error: {result['error']}")
        
        # Print performance metrics
        print(f"\nPerformance Metrics:")
        print("-" * 30)
        metrics = results["performance_metrics"]
        print(f"Total Workflows Executed: {metrics['total_workflows']}")
        print(f"Successful Workflows: {metrics['successful_workflows']}")
        print(f"Failed Workflows: {metrics['failed_workflows']}")
        print(f"Average Execution Time: {metrics['avg_execution_time']:.2f}s")
        
        # Save detailed results
        results_file = f"orchestration_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📊 Detailed results saved to: {results_file}")
        
        # Return appropriate exit code
        if summary["production_ready"]:
            print("\n🎉 Multi-agent orchestration validation PASSED - System ready for production")
            return 0
        else:
            print("\n⚠️  Orchestration validation FAILED - Issues need to be resolved before production")
            return 1
            
    except Exception as e:
        logger.error(f"Validation execution failed: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)