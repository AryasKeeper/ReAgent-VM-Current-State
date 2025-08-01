#!/usr/bin/env python3
"""
ReAgent Sydney Load Testing Suite

Comprehensive load testing to validate 50+ concurrent users 
with <2s response times across all API endpoints.
"""

import asyncio
import aiohttp
import time
import json
import statistics
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LoadTestResult:
    """Load test result metrics."""
    endpoint: str
    method: str
    concurrent_users: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float
    errors: List[str]


@dataclass 
class RequestResult:
    """Individual request result."""
    success: bool
    response_time: float
    status_code: int
    error: Optional[str] = None


class LoadTester:
    """Comprehensive load testing framework for ReAgent Sydney."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=50,  # Per-host connection limit
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={"User-Agent": "ReAgent-LoadTester/1.0"}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> RequestResult:
        """Make a single HTTP request and measure performance."""
        start_time = time.time()
        
        try:
            url = f"{self.base_url}{endpoint}"
            
            async with self.session.request(
                method, 
                url, 
                json=data,
                params=params
            ) as response:
                # Read response to ensure full request completion
                await response.read()
                
                response_time = time.time() - start_time
                
                return RequestResult(
                    success=response.status < 400,
                    response_time=response_time,
                    status_code=response.status,
                    error=None if response.status < 400 else f"HTTP {response.status}"
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            return RequestResult(
                success=False,
                response_time=response_time,
                status_code=0,
                error=str(e)
            )
    
    async def concurrent_user_test(
        self, 
        endpoint: str,
        method: str = "GET",
        concurrent_users: int = 50,
        requests_per_user: int = 10,
        data_generator: Optional[callable] = None,
        params_generator: Optional[callable] = None
    ) -> LoadTestResult:
        """
        Run concurrent user load test on a specific endpoint.
        
        Args:
            endpoint: API endpoint to test
            method: HTTP method
            concurrent_users: Number of concurrent users
            requests_per_user: Requests per user
            data_generator: Function to generate request data
            params_generator: Function to generate request parameters
        """
        logger.info(
            f"Starting load test: {method} {endpoint} "
            f"({concurrent_users} users, {requests_per_user} req/user)"
        )
        
        async def user_session(user_id: int) -> List[RequestResult]:
            """Simulate a single user's requests."""
            results = []
            
            for request_num in range(requests_per_user):
                # Generate dynamic data/params if needed
                data = data_generator(user_id, request_num) if data_generator else None
                params = params_generator(user_id, request_num) if params_generator else None
                
                result = await self.make_request(method, endpoint, data, params)
                results.append(result)
                
                # Small delay between requests (realistic user behavior)
                await asyncio.sleep(0.1)
            
            return results
        
        # Execute concurrent user sessions
        start_time = time.time()
        
        tasks = [user_session(user_id) for user_id in range(concurrent_users)]
        user_results = await asyncio.gather(*tasks)
        
        total_duration = time.time() - start_time
        
        # Flatten results
        all_results = [result for user in user_results for result in user]
        
        # Calculate metrics
        successful_results = [r for r in all_results if r.success]
        failed_results = [r for r in all_results if not r.success]
        
        response_times = [r.response_time for r in successful_results]
        
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            p99_response_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p95_response_time = p99_response_time = 0
        
        total_requests = len(all_results)
        successful_requests = len(successful_results)
        failed_requests = len(failed_results)
        requests_per_second = total_requests / total_duration if total_duration > 0 else 0
        error_rate = (failed_requests / total_requests) * 100 if total_requests > 0 else 0
        
        errors = list(set(r.error for r in failed_results if r.error))
        
        return LoadTestResult(
            endpoint=endpoint,
            method=method,
            concurrent_users=concurrent_users,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate,
            errors=errors
        )


def generate_property_search_params(user_id: int, request_num: int) -> Dict:
    """Generate realistic property search parameters."""
    suburbs = ["bondi", "surry-hills", "paddington", "newtown", "manly"]
    property_types = ["apartment", "house", "townhouse"]
    
    return {
        "suburb": suburbs[user_id % len(suburbs)],
        "property_type": property_types[request_num % len(property_types)],
        "min_price": 500000 + (user_id * 10000),
        "max_price": 1000000 + (user_id * 20000),
        "bedrooms": 1 + (request_num % 4),
        "limit": 20
    }


def generate_buyer_profile_data(user_id: int, request_num: int) -> Dict:
    """Generate realistic buyer profile data."""
    return {
        "name": f"Test Buyer {user_id}_{request_num}",
        "email": f"buyer_{user_id}_{request_num}@test.com",
        "phone": f"04{user_id:02d}{request_num:06d}",
        "min_price": 400000 + (user_id * 5000),
        "max_price": 800000 + (user_id * 10000),
        "preferred_suburbs": ["bondi", "surry-hills"],
        "property_types": ["apartment", "house"],
        "bedrooms": 2 + (user_id % 3),
        "preferences": {
            "parking": True,
            "outdoor_space": request_num % 2 == 0,
            "pet_friendly": user_id % 3 == 0
        }
    }


def generate_market_analysis_params(user_id: int, request_num: int) -> Dict:
    """Generate market analysis parameters."""
    suburbs = ["2000", "2010", "2015", "2021", "2095"]  # Sydney postcodes
    return {
        "postcode": suburbs[user_id % len(suburbs)],
        "period": "30d",
        "metrics": ["price_trend", "volume", "days_on_market"]
    }


async def run_comprehensive_load_tests() -> List[LoadTestResult]:
    """Run comprehensive load tests across all ReAgent endpoints."""
    
    test_scenarios = [
        # Core API endpoints
        {
            "endpoint": "/health",
            "method": "GET",
            "concurrent_users": 100,  # High concurrency for health checks
            "requests_per_user": 5,
            "description": "Health check endpoint"
        },
        {
            "endpoint": "/",
            "method": "GET", 
            "concurrent_users": 50,
            "requests_per_user": 10,
            "description": "Root endpoint"
        },
        
        # Property search endpoints
        {
            "endpoint": "/api/v1/listings/search",
            "method": "GET",
            "concurrent_users": 60,
            "requests_per_user": 15,
            "params_generator": generate_property_search_params,
            "description": "Property search with filters"
        },
        {
            "endpoint": "/api/v1/listings",
            "method": "GET",
            "concurrent_users": 40,
            "requests_per_user": 20,
            "description": "Basic property listing"
        },
        
        # Buyer management endpoints
        {
            "endpoint": "/api/v1/buyers",
            "method": "POST", 
            "concurrent_users": 30,
            "requests_per_user": 5,
            "data_generator": generate_buyer_profile_data,
            "description": "Create buyer profiles"
        },
        {
            "endpoint": "/api/v1/buyers",
            "method": "GET",
            "concurrent_users": 50,
            "requests_per_user": 10,
            "description": "List buyer profiles"
        },
        
        # Agent endpoints
        {
            "endpoint": "/api/v1/agents/listing-watcher/status",
            "method": "GET",
            "concurrent_users": 20,
            "requests_per_user": 8,
            "description": "Listing Watcher status"
        },
        {
            "endpoint": "/api/v1/agents/suburb-signal/trends", 
            "method": "GET",
            "concurrent_users": 25,
            "requests_per_user": 12,
            "params_generator": generate_market_analysis_params,
            "description": "Suburb Signal trend analysis"
        },
        {
            "endpoint": "/api/v1/agents/buyer-matchmaker/matches",
            "method": "GET", 
            "concurrent_users": 35,
            "requests_per_user": 8,
            "description": "Buyer property matching"
        },
        
        # High-load mixed scenario
        {
            "endpoint": "/api/v1/listings/search",
            "method": "GET",
            "concurrent_users": 80,  # Peak load test
            "requests_per_user": 25,
            "params_generator": generate_property_search_params,
            "description": "Peak load property search"
        }
    ]
    
    results = []
    
    async with LoadTester() as tester:
        for i, scenario in enumerate(test_scenarios):
            logger.info(f"Running test {i+1}/{len(test_scenarios)}: {scenario['description']}")
            
            result = await tester.concurrent_user_test(
                endpoint=scenario["endpoint"],
                method=scenario["method"],
                concurrent_users=scenario["concurrent_users"],
                requests_per_user=scenario["requests_per_user"],
                data_generator=scenario.get("data_generator"),
                params_generator=scenario.get("params_generator")
            )
            
            results.append(result)
            
            # Brief pause between test scenarios
            await asyncio.sleep(2)
    
    return results


def analyze_performance_results(results: List[LoadTestResult]) -> Dict[str, Any]:
    """Analyze load test results and generate performance report."""
    
    total_requests = sum(r.total_requests for r in results)
    total_successful = sum(r.successful_requests for r in results)
    total_failed = sum(r.failed_requests for r in results)
    
    avg_response_times = [r.avg_response_time for r in results if r.successful_requests > 0]
    p95_response_times = [r.p95_response_time for r in results if r.successful_requests > 0]
    
    # Performance thresholds
    sub_2s_endpoints = len([r for r in results if r.avg_response_time < 2.0])
    sub_1s_endpoints = len([r for r in results if r.avg_response_time < 1.0])
    
    slow_endpoints = [
        {"endpoint": r.endpoint, "avg_time": r.avg_response_time}
        for r in results if r.avg_response_time >= 2.0
    ]
    
    high_error_endpoints = [
        {"endpoint": r.endpoint, "error_rate": r.error_rate}
        for r in results if r.error_rate > 5.0
    ]
    
    return {
        "summary": {
            "total_endpoints_tested": len(results),
            "total_requests": total_requests,
            "successful_requests": total_successful,
            "failed_requests": total_failed,
            "overall_success_rate": (total_successful / total_requests) * 100 if total_requests > 0 else 0
        },
        "performance": {
            "avg_response_time_overall": statistics.mean(avg_response_times) if avg_response_times else 0,
            "avg_p95_response_time": statistics.mean(p95_response_times) if p95_response_times else 0,
            "sub_2s_endpoints": sub_2s_endpoints,
            "sub_1s_endpoints": sub_1s_endpoints,
            "performance_target_met": sub_2s_endpoints == len(results)
        },
        "issues": {
            "slow_endpoints": slow_endpoints,
            "high_error_endpoints": high_error_endpoints
        }
    }


def generate_load_test_report(results: List[LoadTestResult], analysis: Dict[str, Any]) -> str:
    """Generate comprehensive load test report."""
    
    report = f"""
# ReAgent Sydney Load Test Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- **Total Endpoints Tested:** {analysis['summary']['total_endpoints_tested']}
- **Total Requests:** {analysis['summary']['total_requests']:,}
- **Success Rate:** {analysis['summary']['overall_success_rate']:.1f}%
- **Performance Target (<2s):** {'✅ PASSED' if analysis['performance']['performance_target_met'] else '❌ FAILED'}

## Performance Metrics
- **Average Response Time:** {analysis['performance']['avg_response_time_overall']:.3f}s
- **95th Percentile Response Time:** {analysis['performance']['avg_p95_response_time']:.3f}s
- **Endpoints Under 2s:** {analysis['performance']['sub_2s_endpoints']}/{analysis['summary']['total_endpoints_tested']}
- **Endpoints Under 1s:** {analysis['performance']['sub_1s_endpoints']}/{analysis['summary']['total_endpoints_tested']}

## Detailed Results
"""
    
    for result in results:
        status = "✅ PASS" if result.avg_response_time < 2.0 and result.error_rate < 5.0 else "❌ FAIL"
        
        report += f"""
### {result.method} {result.endpoint}
- **Status:** {status}
- **Concurrent Users:** {result.concurrent_users}
- **Total Requests:** {result.total_requests:,}
- **Success Rate:** {((result.successful_requests / result.total_requests) * 100):.1f}%
- **Avg Response Time:** {result.avg_response_time:.3f}s
- **95th Percentile:** {result.p95_response_time:.3f}s
- **Requests/Second:** {result.requests_per_second:.1f}
"""
        
        if result.errors:
            report += f"- **Errors:** {', '.join(result.errors[:3])}\n"
    
    # Performance issues
    if analysis['issues']['slow_endpoints']:
        report += "\n## ⚠️ Performance Issues\n"
        for endpoint in analysis['issues']['slow_endpoints']:
            report += f"- {endpoint['endpoint']}: {endpoint['avg_time']:.3f}s\n"
    
    if analysis['issues']['high_error_endpoints']:
        report += "\n## ❌ High Error Rate Endpoints\n"
        for endpoint in analysis['issues']['high_error_endpoints']:
            report += f"- {endpoint['endpoint']}: {endpoint['error_rate']:.1f}% error rate\n"
    
    report += "\n## Recommendations\n"
    
    if not analysis['performance']['performance_target_met']:
        report += "- Optimize slow endpoints to achieve <2s response time target\n"
        report += "- Consider implementing additional caching layers\n"
        report += "- Review database query performance and indexing\n"
    
    if analysis['issues']['high_error_endpoints']:
        report += "- Investigate and fix endpoints with high error rates\n"
        report += "- Implement better error handling and retry mechanisms\n"
    
    report += "- Monitor resource utilization during peak loads\n"
    report += "- Consider horizontal scaling for high-traffic endpoints\n"
    
    return report


async def main():
    """Run comprehensive load testing suite."""
    logger.info("Starting ReAgent Sydney Load Testing Suite...")
    
    # Run load tests
    results = await run_comprehensive_load_tests()
    
    # Analyze results  
    analysis = analyze_performance_results(results)
    
    # Generate report
    report = generate_load_test_report(results, analysis)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save detailed JSON results
    with open(f"load_test_results_{timestamp}.json", "w") as f:
        json.dump({
            "results": [asdict(r) for r in results],
            "analysis": analysis,
            "timestamp": timestamp
        }, f, indent=2)
    
    # Save human-readable report
    with open(f"load_test_report_{timestamp}.md", "w") as f:
        f.write(report)
    
    # Print summary
    print(report)
    
    logger.info(f"Load testing completed. Results saved to load_test_results_{timestamp}.json")


if __name__ == "__main__":
    asyncio.run(main())