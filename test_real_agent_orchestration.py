#!/usr/bin/env python3
"""
Test script to verify the Agent Orchestrator is using real agent execution
instead of mock responses.

This script tests the multi-agent orchestration with live agent calls.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import structlog

# Add the ReAgent source directory to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from src.agents.agent_whisperer.multi_agent_orchestrator import (
    MultiAgentOrchestrator, 
    AgentCoordinationRequest,
    CoordinationStrategy,
    QueryIntent,
    IntentType
)

# Configure logging
logging = structlog.configure(
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
logger = structlog.get_logger(__name__)


async def test_single_agent_execution():
    """Test executing a single agent to verify real execution."""
    
    print("🧪 Testing Single Agent Execution...")
    
    orchestrator = MultiAgentOrchestrator(logger=logger)
    await orchestrator.initialize()
    
    try:
        # Test each agent individually
        agents_to_test = ["listing_watcher", "suburb_signal", "buyer_matchmaker", "seller_strategy", "off_market_radar"]
        
        for agent_name in agents_to_test:
            print(f"\n📋 Testing {agent_name}...")
            
            test_input = {
                "request_id": f"test_{agent_name}_{int(datetime.now().timestamp())}",
                "priority": "medium",
                "context": {"test_mode": True}
            }
            
            result = await orchestrator._call_agent(agent_name, test_input, 60)
            
            # Verify this is real execution, not mock
            if result.get("real_execution"):
                print(f"✅ {agent_name}: Real execution confirmed")
                print(f"   Success: {result.get('success')}")
                print(f"   Execution Time: {result.get('execution_time', 0):.2f}s")
                print(f"   Data Sources: {result.get('data_sources', [])}")
                if result.get('error'):
                    print(f"   Error: {result.get('error')}")
            else:
                print(f"❌ {agent_name}: Still using mock responses!")
                return False
    
    except Exception as e:
        print(f"❌ Single agent test failed: {e}")
        return False
    
    finally:
        await orchestrator.shutdown()
    
    return True


async def test_multi_agent_coordination():
    """Test multi-agent coordination with real execution."""
    
    print("\n🎭 Testing Multi-Agent Coordination...")
    
    orchestrator = MultiAgentOrchestrator(logger=logger)
    await orchestrator.initialize()
    
    try:
        # Create a test coordination request
        test_intent = QueryIntent(
            query="Find properties in Bondi Junction with market analysis",
            intent_type=IntentType.MARKET_UPDATE,
            entities={"suburb": "Bondi Junction", "state": "NSW"},
            confidence=0.9
        )
        
        coordination_request = AgentCoordinationRequest(
            primary_intent=test_intent,
            required_agents=["listing_watcher", "suburb_signal"],
            optional_agents=["buyer_matchmaker"],
            strategy=CoordinationStrategy.PARALLEL,
            timeout_seconds=120,
            allow_partial_results=True
        )
        
        print(f"🚀 Executing coordination with {len(coordination_request.required_agents + coordination_request.optional_agents)} agents...")
        
        # Execute coordination
        result = await orchestrator.coordinate_agents(coordination_request)
        
        # Analyze results
        print(f"\n📊 Coordination Results:")
        print(f"   Status: {result.get('status')}")
        print(f"   Execution Time: {result.get('execution_time', 0):.2f}s")
        print(f"   Successful Agents: {result.get('successful_agents', [])}")
        print(f"   Failed Agents: {result.get('failed_agents', [])}")
        print(f"   Success Rate: {result.get('success_rate', 0) * 100:.1f}%")
        
        # Check if agents actually executed (not mocked)
        agent_results = result.get('agent_results', {})
        real_executions = 0
        
        for agent_name, agent_result in agent_results.items():
            if agent_result.get('real_execution'):
                real_executions += 1
                print(f"   ✅ {agent_name}: Real execution")
            else:
                print(f"   ❌ {agent_name}: Mock execution detected")
        
        print(f"\n🎯 Real Executions: {real_executions}/{len(agent_results)}")
        
        return real_executions == len(agent_results) and len(agent_results) > 0
    
    except Exception as e:
        print(f"❌ Multi-agent coordination test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await orchestrator.shutdown()


async def test_error_handling():
    """Test error handling with invalid agent execution."""
    
    print("\n🚨 Testing Error Handling...")
    
    orchestrator = MultiAgentOrchestrator(logger=logger)
    await orchestrator.initialize()
    
    try:
        # Test with invalid agent name
        result = await orchestrator._call_agent("invalid_agent", {}, 30)
        
        if not result.get("success") and result.get("error"):
            print("✅ Error handling works correctly for invalid agents")
            return True
        else:
            print("❌ Error handling failed - should have returned error")
            return False
    
    except Exception as e:
        print(f"✅ Exception properly caught: {type(e).__name__}")
        return True
    
    finally:
        await orchestrator.shutdown()


async def main():
    """Main test runner."""
    
    print("🎯 ReAgent Sydney - Agent Orchestrator Real Execution Test")
    print("=" * 60)
    
    tests = [
        ("Single Agent Execution", test_single_agent_execution),
        ("Multi-Agent Coordination", test_multi_agent_coordination),
        ("Error Handling", test_error_handling)
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        print("-" * 40)
        
        try:
            if await test_func():
                print(f"✅ {test_name}: PASSED")
                passed_tests += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"🏁 Test Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Agent Orchestrator is using real execution.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the agent implementations.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)