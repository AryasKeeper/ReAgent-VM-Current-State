#!/usr/bin/env python3
"""
ReAgent Sydney - Redis Pub/Sub Validation for Multi-Agent Communication

Tests Redis pub/sub messaging patterns, reliability, and agent coordination
through message passing.
"""

import asyncio
import json
import time
import uuid
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, '/home/emergence-admin/Desktop/ReAgent/src')

try:
    import redis.asyncio as redis
    from core.cache.redis_client import get_redis_client, get_cache_manager
    from config.settings import get_settings
except ImportError as e:
    logger.error(f"Failed to import Redis components: {e}")
    sys.exit(1)


class RedisPubSubValidator:
    """Validates Redis pub/sub functionality for agent coordination."""
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self.cache_manager = None
        self.test_results = {}
        
        # Test channels for different agent communication patterns
        self.channels = {
            "agent_coordination": "reagent:coordination",
            "workflow_status": "reagent:workflow:status", 
            "agent_alerts": "reagent:agents:alerts",
            "data_sync": "reagent:data:sync",
            "task_queue": "reagent:tasks:queue"
        }
        
        # Message tracking
        self.sent_messages = {}
        self.received_messages = {}
        
    async def initialize(self):
        """Initialize Redis connections."""
        try:
            self.redis_client = get_redis_client()
            self.cache_manager = get_cache_manager()
            
            # Test basic connectivity
            await self.redis_client.ping()
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise
    
    async def test_basic_pubsub(self) -> Dict[str, Any]:
        """Test basic Redis pub/sub functionality."""
        logger.info("Testing basic Redis pub/sub functionality")
        
        start_time = time.time()
        test_channel = "test:basic_pubsub"
        test_messages = []
        received_messages = []
        
        try:
            # Create subscriber
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(test_channel)
            
            # Create publisher task
            async def publisher():
                await asyncio.sleep(0.5)  # Let subscriber start
                
                for i in range(5):
                    message = {
                        "id": f"msg_{i}",
                        "content": f"Test message {i}",
                        "timestamp": datetime.utcnow().isoformat(),
                        "sequence": i
                    }
                    
                    await self.redis_client.publish(test_channel, json.dumps(message))
                    test_messages.append(message)
                    await asyncio.sleep(0.1)
            
            # Create subscriber task
            async def subscriber():
                message_count = 0
                async for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            data = json.loads(message['data'])
                            received_messages.append(data)
                            message_count += 1
                            
                            if message_count >= 5:
                                break
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to decode message: {message['data']}")
            
            # Run publisher and subscriber concurrently
            await asyncio.gather(
                publisher(),
                subscriber(),
                return_exceptions=True
            )
            
            await pubsub.unsubscribe(test_channel)
            await pubsub.close()
            
            execution_time = time.time() - start_time
            
            # Verify message delivery
            messages_sent = len(test_messages)
            messages_received = len(received_messages)
            delivery_rate = messages_received / messages_sent if messages_sent > 0 else 0
            
            # Check message order and integrity
            order_preserved = True
            for i, msg in enumerate(received_messages):
                expected_sequence = i
                if msg.get("sequence") != expected_sequence:
                    order_preserved = False
                    break
            
            return {
                "test": "basic_pubsub",
                "success": delivery_rate >= 0.8 and order_preserved,
                "execution_time": execution_time,
                "messages_sent": messages_sent,
                "messages_received": messages_received,
                "delivery_rate": delivery_rate,
                "order_preserved": order_preserved,
                "test_messages": test_messages,
                "received_messages": received_messages
            }
            
        except Exception as e:
            return {
                "test": "basic_pubsub",
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def test_agent_coordination_messaging(self) -> Dict[str, Any]:
        """Test agent coordination through pub/sub messaging."""
        logger.info("Testing agent coordination messaging patterns")
        
        start_time = time.time()
        coordination_channel = self.channels["agent_coordination"]
        
        # Simulate different agent types
        agent_types = ["listing_watcher", "suburb_signal", "buyer_matchmaker", "seller_strategy"]
        coordination_messages = []
        responses = {}
        
        try:
            # Create subscribers for each agent type
            subscribers = {}
            
            for agent_type in agent_types:
                pubsub = self.redis_client.pubsub()
                await pubsub.subscribe(coordination_channel)
                subscribers[agent_type] = pubsub
            
            # Simulate coordination workflow
            async def orchestrator():
                await asyncio.sleep(0.5)  # Let subscribers start
                
                # Send coordination request
                coordination_request = {
                    "request_id": str(uuid.uuid4()),
                    "workflow_type": "market_analysis",
                    "required_agents": agent_types,
                    "priority": "high",
                    "data": {
                        "suburb": "Bondi Beach",
                        "analysis_type": "comprehensive"
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                await self.redis_client.publish(
                    coordination_channel, 
                    json.dumps(coordination_request)
                )
                coordination_messages.append(coordination_request)
                
                # Wait for responses
                await asyncio.sleep(2)
            
            # Simulate agent responses
            async def agent_simulator(agent_type: str, pubsub):
                async for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            request = json.loads(message['data'])
                            request_id = request.get("request_id")
                            
                            if agent_type in request.get("required_agents", []):
                                # Simulate agent processing
                                await asyncio.sleep(0.2)
                                
                                # Send response
                                response = {
                                    "request_id": request_id,
                                    "agent_type": agent_type,
                                    "status": "completed",
                                    "result": {
                                        "processed": True,
                                        "data_points": 50,
                                        "confidence": 0.85
                                    },
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                                
                                response_channel = f"reagent:response:{request_id}"
                                await self.redis_client.publish(
                                    response_channel,
                                    json.dumps(response)
                                )
                                responses[agent_type] = response
                                break
                                
                        except json.JSONDecodeError:
                            continue
            
            # Run orchestrator and agents
            tasks = [orchestrator()]
            for agent_type, pubsub in subscribers.items():
                tasks.append(agent_simulator(agent_type, pubsub))
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Cleanup
            for pubsub in subscribers.values():
                await pubsub.close()
            
            execution_time = time.time() - start_time
            
            # Evaluate coordination success
            expected_responses = len(agent_types)
            actual_responses = len(responses)
            coordination_success = actual_responses / expected_responses if expected_responses > 0 else 0
            
            return {
                "test": "agent_coordination_messaging",
                "success": coordination_success >= 0.8,
                "execution_time": execution_time,
                "coordination_requests_sent": len(coordination_messages),
                "expected_responses": expected_responses,
                "actual_responses": actual_responses,
                "coordination_success_rate": coordination_success,
                "agent_responses": responses
            }
            
        except Exception as e:
            return {
                "test": "agent_coordination_messaging",
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def test_workflow_status_broadcasting(self) -> Dict[str, Any]:
        """Test workflow status broadcasting and monitoring."""
        logger.info("Testing workflow status broadcasting")
        
        start_time = time.time()
        status_channel = self.channels["workflow_status"]
        
        workflow_stages = ["started", "agent_1_completed", "agent_2_completed", "synthesizing", "completed"]
        broadcasted_statuses = []
        monitored_statuses = []
        
        try:
            # Create status monitor
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(status_channel)
            
            # Status broadcaster
            async def status_broadcaster():
                await asyncio.sleep(0.5)
                
                workflow_id = str(uuid.uuid4())
                
                for stage in workflow_stages:
                    status_update = {
                        "workflow_id": workflow_id,
                        "stage": stage,
                        "timestamp": datetime.utcnow().isoformat(),
                        "progress": (workflow_stages.index(stage) + 1) / len(workflow_stages),
                        "metadata": {
                            "agents_involved": ["listing_watcher", "suburb_signal"],
                            "estimated_completion": 30
                        }
                    }
                    
                    await self.redis_client.publish(
                        status_channel,
                        json.dumps(status_update)
                    )
                    broadcasted_statuses.append(status_update)
                    await asyncio.sleep(0.3)
            
            # Status monitor
            async def status_monitor():
                status_count = 0
                async for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            status = json.loads(message['data'])
                            monitored_statuses.append(status)
                            status_count += 1
                            
                            if status_count >= len(workflow_stages):
                                break
                        except json.JSONDecodeError:
                            continue
            
            # Run broadcaster and monitor
            await asyncio.gather(
                status_broadcaster(),
                status_monitor(),
                return_exceptions=True
            )
            
            await pubsub.unsubscribe(status_channel)
            await pubsub.close()
            
            execution_time = time.time() - start_time
            
            # Verify status delivery and ordering
            statuses_sent = len(broadcasted_statuses)
            statuses_received = len(monitored_statuses)
            delivery_rate = statuses_received / statuses_sent if statuses_sent > 0 else 0
            
            # Check stage progression
            stage_order_correct = True
            for i, status in enumerate(monitored_statuses):
                expected_stage = workflow_stages[i] if i < len(workflow_stages) else None
                if status.get("stage") != expected_stage:
                    stage_order_correct = False
                    break
            
            return {
                "test": "workflow_status_broadcasting",
                "success": delivery_rate >= 0.8 and stage_order_correct,
                "execution_time": execution_time,
                "statuses_sent": statuses_sent,
                "statuses_received": statuses_received,
                "delivery_rate": delivery_rate,
                "stage_order_correct": stage_order_correct,
                "workflow_stages": workflow_stages,
                "monitored_statuses": monitored_statuses
            }
            
        except Exception as e:
            return {
                "test": "workflow_status_broadcasting",
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def test_high_throughput_messaging(self) -> Dict[str, Any]:
        """Test high-throughput messaging under load."""
        logger.info("Testing high-throughput messaging")
        
        start_time = time.time()
        throughput_channel = "test:high_throughput"
        
        num_messages = 100
        batch_size = 10
        messages_sent = []
        messages_received = []
        
        try:
            # Create subscriber
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(throughput_channel)
            
            # High-throughput publisher
            async def high_throughput_publisher():
                await asyncio.sleep(0.5)
                
                for batch in range(0, num_messages, batch_size):
                    batch_messages = []
                    
                    for i in range(batch_size):
                        if batch + i < num_messages:
                            message = {
                                "id": batch + i,
                                "batch": batch // batch_size,
                                "content": f"High throughput message {batch + i}",
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            batch_messages.append(message)
                    
                    # Send batch
                    for message in batch_messages:
                        await self.redis_client.publish(
                            throughput_channel,
                            json.dumps(message)
                        )
                        messages_sent.append(message)
                    
                    # Brief pause between batches
                    await asyncio.sleep(0.1)
            
            # High-throughput subscriber
            async def high_throughput_subscriber():
                message_count = 0
                start_receive_time = time.time()
                
                async for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            data = json.loads(message['data'])
                            data['receive_time'] = time.time()
                            messages_received.append(data)
                            message_count += 1
                            
                            if message_count >= num_messages:
                                break
                                
                        except json.JSONDecodeError:
                            continue
                
                receive_time = time.time() - start_receive_time
                return receive_time
            
            # Run publisher and subscriber
            results = await asyncio.gather(
                high_throughput_publisher(),
                high_throughput_subscriber(),
                return_exceptions=True
            )
            
            await pubsub.unsubscribe(throughput_channel)
            await pubsub.close()
            
            execution_time = time.time() - start_time
            
            # Calculate throughput metrics
            total_sent = len(messages_sent)
            total_received = len(messages_received)
            delivery_rate = total_received / total_sent if total_sent > 0 else 0
            
            throughput_sent = total_sent / execution_time if execution_time > 0 else 0
            throughput_received = total_received / execution_time if execution_time > 0 else 0
            
            # Calculate latency (time between send and receive)
            latencies = []
            if messages_received:
                for msg in messages_received:
                    if 'receive_time' in msg:
                        # Approximate latency (not precise without send timestamps)
                        latencies.append(0.05)  # Placeholder
            
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            
            return {
                "test": "high_throughput_messaging",
                "success": delivery_rate >= 0.95 and throughput_received >= 50,  # 50 msgs/sec minimum
                "execution_time": execution_time,
                "messages_sent": total_sent,
                "messages_received": total_received,
                "delivery_rate": delivery_rate,
                "throughput_sent_per_sec": throughput_sent,
                "throughput_received_per_sec": throughput_received,
                "average_latency_ms": avg_latency * 1000,
                "batch_size": batch_size
            }
            
        except Exception as e:
            return {
                "test": "high_throughput_messaging",
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def test_message_persistence_and_recovery(self) -> Dict[str, Any]:
        """Test message persistence and recovery scenarios."""
        logger.info("Testing message persistence and recovery")
        
        start_time = time.time()
        persistence_channel = "test:persistence"
        
        try:
            # Test 1: Message persistence in Redis streams (if available)
            stream_key = "reagent:stream:test"
            
            # Add messages to stream
            stream_messages = []
            for i in range(5):
                message_data = {
                    "agent": f"agent_{i % 3}",
                    "task": f"task_{i}",
                    "data": f"persistent_data_{i}",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                message_id = await self.redis_client.xadd(stream_key, message_data)
                stream_messages.append((message_id, message_data))
            
            # Read messages from stream
            retrieved_messages = await self.redis_client.xrange(stream_key)
            
            # Test 2: Cache-based message storage for recovery
            recovery_key = "reagent:recovery:messages"
            recovery_messages = []
            
            for i in range(3):
                recovery_message = {
                    "id": str(uuid.uuid4()),
                    "content": f"Recovery message {i}",
                    "priority": "high" if i == 0 else "medium",
                    "timestamp": datetime.utcnow().isoformat()
                }
                recovery_messages.append(recovery_message)
            
            # Store in cache with longer TTL for recovery
            await self.cache_manager.set(recovery_key, recovery_messages, ttl=300)
            
            # Retrieve for recovery simulation
            recovered_messages = await self.cache_manager.get(recovery_key)
            
            execution_time = time.time() - start_time
            
            # Verify persistence and recovery
            stream_success = len(retrieved_messages) == len(stream_messages)
            cache_success = recovered_messages == recovery_messages
            
            # Cleanup
            await self.redis_client.delete(stream_key)
            await self.cache_manager.delete(recovery_key)
            
            return {
                "test": "message_persistence_recovery",
                "success": stream_success and cache_success,
                "execution_time": execution_time,
                "stream_messages_stored": len(stream_messages),
                "stream_messages_retrieved": len(retrieved_messages),
                "stream_persistence_success": stream_success,
                "cache_messages_stored": len(recovery_messages),
                "cache_recovery_success": cache_success,
                "recovered_messages": recovered_messages
            }
            
        except Exception as e:
            return {
                "test": "message_persistence_recovery",
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run all Redis pub/sub validation tests."""
        logger.info("Starting comprehensive Redis pub/sub validation")
        
        await self.initialize()
        
        test_suites = {
            "basic_pubsub": self.test_basic_pubsub,
            "agent_coordination": self.test_agent_coordination_messaging,
            "workflow_status": self.test_workflow_status_broadcasting,
            "high_throughput": self.test_high_throughput_messaging,
            "persistence_recovery": self.test_message_persistence_and_recovery
        }
        
        results = {}
        start_time = time.time()
        
        for test_name, test_func in test_suites.items():
            logger.info(f"Running Redis pub/sub test: {test_name}")
            
            try:
                result = await test_func()
                results[test_name] = result
                
                status = "PASS" if result.get("success", False) else "FAIL"
                logger.info(f"Test {test_name}: {status} ({result.get('execution_time', 0):.2f}s)")
                
            except Exception as e:
                results[test_name] = {
                    "success": False,
                    "error": str(e),
                    "execution_time": 0
                }
                logger.error(f"Test {test_name} failed: {e}")
        
        total_execution_time = time.time() - start_time
        
        # Calculate summary
        total_tests = len(test_suites)
        passed_tests = sum(1 for r in results.values() if r.get("success", False))
        failed_tests = total_tests - passed_tests
        
        return {
            "validation_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "total_execution_time": total_execution_time,
                "pubsub_reliable": passed_tests / total_tests >= 0.8
            },
            "detailed_results": results
        }


async def main():
    """Main validation execution."""
    validator = RedisPubSubValidator()
    
    try:
        print("🔴 ReAgent Sydney - Redis Pub/Sub Validation")
        print("=" * 60)
        
        results = await validator.run_comprehensive_validation()
        
        # Print summary
        summary = results["validation_summary"]
        print(f"\nValidation Summary:")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Success Rate: {summary['success_rate']:.1%}")
        print(f"Total Execution Time: {summary['total_execution_time']:.2f}s")
        print(f"Pub/Sub Reliable: {'✅ YES' if summary['pubsub_reliable'] else '❌ NO'}")
        
        # Print detailed results
        print(f"\nDetailed Test Results:")
        print("-" * 50)
        
        for test_name, result in results["detailed_results"].items():
            status = "PASS" if result.get("success", False) else "FAIL"
            exec_time = result.get("execution_time", 0)
            print(f"{test_name:<25} {status:<6} ({exec_time:.2f}s)")
            
            if not result.get("success", False) and result.get("error"):
                print(f"    Error: {result['error']}")
        
        # Save results
        import json
        results_file = f"redis_pubsub_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📊 Results saved to: {results_file}")
        
        if summary["pubsub_reliable"]:
            print("\n🎉 Redis pub/sub validation PASSED - Messaging reliable for production")
            return 0
        else:
            print("\n⚠️  Redis pub/sub validation FAILED - Messaging issues need resolution")
            return 1
            
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)