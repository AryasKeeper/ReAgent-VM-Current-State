#!/usr/bin/env python3
"""
ReAgent Sydney - Comprehensive System Health Check
Production-ready validation and monitoring for all system components
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import subprocess
import docker
import psutil
import redis
import weaviate
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/emergence-admin/Desktop/ReAgent/logs/health-check.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemHealthValidator:
    """Comprehensive system health validation for ReAgent production deployment"""
    
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.results: Dict[str, Any] = {
            'timestamp': self.start_time.isoformat(),
            'system_info': {},
            'docker_services': {},
            'database_connectivity': {},
            'api_endpoints': {},
            'performance_metrics': {},
            'validation_summary': {},
            'errors': [],
            'warnings': []
        }
        
        # Service configurations
        self.docker_services = [
            'reagent-postgres', 'reagent-redis', 'reagent-weaviate-dev',
            'reagent-api', 'reagent-agents', 'reagent-celery-worker',
            'reagent-celery-beat', 'reagent-frontend', 'reagent-prometheus',
            'reagent-grafana'
        ]
        
        self.api_endpoints = {
            'health_ready': 'http://localhost:8000/api/v1/health/ready',
            'health_live': 'http://localhost:8000/api/v1/health/live',
            'agents_status': 'http://localhost:8000/api/v1/agents/status',
            'listings_count': 'http://localhost:8000/api/v1/listings/count',
            'buyers_count': 'http://localhost:8000/api/v1/buyers/count'
        }
        
        self.database_configs = {
            'postgresql': {
                'url': 'postgresql://reagent:reagent_dev_password@localhost:5432/reagent',
                'test_query': 'SELECT 1'
            },
            'redis': {
                'url': 'redis://localhost:6379/0',
                'test_command': 'ping'
            },
            'weaviate': {
                'url': 'http://localhost:8080',
                'test_endpoint': '/v1/.well-known/ready'
            }
        }

    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Execute complete system validation suite"""
        logger.info("Starting comprehensive system health validation")
        
        try:
            # System information
            await self._collect_system_info()
            
            # Docker service validation
            await self._validate_docker_services()
            
            # Database connectivity tests
            await self._validate_database_connectivity()
            
            # API endpoint validation
            await self._validate_api_endpoints()
            
            # Performance metrics collection
            await self._collect_performance_metrics()
            
            # Generate validation summary
            self._generate_validation_summary()
            
            logger.info("Comprehensive system validation completed successfully")
            
        except Exception as e:
            error_msg = f"Critical error during system validation: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.results['errors'].append({
                'type': 'critical_validation_error',
                'message': error_msg,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        
        return self.results

    async def _collect_system_info(self):
        """Collect system information and resource usage"""
        try:
            logger.info("Collecting system information")
            
            # System resources
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Docker info
            try:
                docker_client = docker.from_env()
                docker_info = docker_client.info()
                docker_version = docker_client.version()
            except Exception as e:
                docker_info = {'error': str(e)}
                docker_version = {'error': str(e)}
            
            self.results['system_info'] = {
                'cpu_percent': cpu_percent,
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100
                },
                'docker_info': {
                    'containers_running': docker_info.get('ContainersRunning', 'unknown'),
                    'containers_total': docker_info.get('Containers', 'unknown'),
                    'images': docker_info.get('Images', 'unknown'),
                    'docker_version': docker_version.get('Version', 'unknown')
                }
            }
            
            logger.info(f"System resources - CPU: {cpu_percent}%, Memory: {memory.percent}%, Disk: {(disk.used / disk.total) * 100:.1f}%")
            
        except Exception as e:
            error_msg = f"Error collecting system info: {str(e)}"
            logger.error(error_msg)
            self.results['errors'].append({
                'type': 'system_info_error',
                'message': error_msg
            })

    async def _validate_docker_services(self):
        """Validate all Docker services are running and healthy"""
        try:
            logger.info("Validating Docker services")
            docker_client = docker.from_env()
            
            for service_name in self.docker_services:
                try:
                    container = docker_client.containers.get(service_name)
                    
                    # Get container status and health
                    status = container.status
                    attrs = container.attrs
                    health_status = attrs.get('State', {}).get('Health', {}).get('Status', 'unknown')
                    
                    # Get resource usage
                    stats = container.stats(stream=False, decode=True)
                    
                    # Calculate CPU percentage
                    cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                    system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
                    cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0 if system_delta > 0 else 0.0
                    
                    # Memory usage
                    memory_usage = stats['memory_stats'].get('usage', 0)
                    memory_limit = stats['memory_stats'].get('limit', 0)
                    memory_percent = (memory_usage / memory_limit) * 100.0 if memory_limit > 0 else 0.0
                    
                    self.results['docker_services'][service_name] = {
                        'status': status,
                        'health_status': health_status,
                        'restart_count': attrs.get('RestartCount', 0),
                        'started_at': attrs.get('State', {}).get('StartedAt'),
                        'cpu_percent': round(cpu_percent, 2),
                        'memory_usage_mb': round(memory_usage / (1024 * 1024), 2),
                        'memory_percent': round(memory_percent, 2),
                        'ports': [port for port in container.ports.keys()] if container.ports else [],
                        'image': container.image.tags[0] if container.image.tags else 'unknown'
                    }
                    
                    # Check for unhealthy services
                    if status != 'running':
                        self.results['errors'].append({
                            'type': 'service_not_running',
                            'service': service_name,
                            'status': status
                        })
                    elif health_status == 'unhealthy':
                        self.results['errors'].append({
                            'type': 'service_unhealthy',
                            'service': service_name,
                            'health_status': health_status
                        })
                    
                    logger.info(f"Service {service_name}: {status} ({health_status})")
                    
                except docker.errors.NotFound:
                    self.results['docker_services'][service_name] = {
                        'status': 'not_found',
                        'error': 'Container not found'
                    }
                    self.results['errors'].append({
                        'type': 'service_not_found',
                        'service': service_name
                    })
                    logger.error(f"Service {service_name}: not found")
                
                except Exception as e:
                    error_msg = f"Error checking service {service_name}: {str(e)}"
                    self.results['docker_services'][service_name] = {
                        'status': 'error',
                        'error': error_msg
                    }
                    self.results['errors'].append({
                        'type': 'service_check_error',
                        'service': service_name,
                        'message': error_msg
                    })
                    logger.error(error_msg)
        
        except Exception as e:
            error_msg = f"Error validating Docker services: {str(e)}"
            logger.error(error_msg)
            self.results['errors'].append({
                'type': 'docker_validation_error',
                'message': error_msg
            })

    async def _validate_database_connectivity(self):
        """Test connectivity to all databases"""
        logger.info("Validating database connectivity")
        
        # PostgreSQL validation
        await self._test_postgresql()
        
        # Redis validation
        await self._test_redis()
        
        # Weaviate validation
        await self._test_weaviate()

    async def _test_postgresql(self):
        """Test PostgreSQL connectivity and basic queries"""
        try:
            config = self.database_configs['postgresql']
            engine = create_engine(config['url'])
            
            start_time = time.time()
            with engine.connect() as conn:
                # Test basic connectivity
                result = conn.execute(text(config['test_query']))
                basic_query_time = time.time() - start_time
                
                # Test TimescaleDB functionality
                start_time = time.time()
                timescale_result = conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'"))
                timescale_available = timescale_result.fetchone() is not None
                timescale_query_time = time.time() - start_time
                
                # Test table existence
                start_time = time.time()
                tables_result = conn.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """))
                tables = [row[0] for row in tables_result.fetchall()]
                tables_query_time = time.time() - start_time
                
                # Get connection stats
                conn_stats = conn.execute(text("""
                    SELECT count(*) as active_connections
                    FROM pg_stat_activity 
                    WHERE state = 'active'
                """)).fetchone()
                
                self.results['database_connectivity']['postgresql'] = {
                    'status': 'healthy',
                    'basic_query_time_seconds': round(basic_query_time, 4),
                    'timescale_available': timescale_available,
                    'timescale_query_time_seconds': round(timescale_query_time, 4),
                    'tables_count': len(tables),
                    'tables_query_time_seconds': round(tables_query_time, 4),
                    'active_connections': conn_stats[0] if conn_stats else 0,
                    'available_tables': tables[:10]  # First 10 tables
                }
                
                logger.info(f"PostgreSQL: healthy ({len(tables)} tables, TimescaleDB: {timescale_available})")
                
        except SQLAlchemyError as e:
            error_msg = f"PostgreSQL connectivity error: {str(e)}"
            logger.error(error_msg)
            self.results['database_connectivity']['postgresql'] = {
                'status': 'error',
                'error': error_msg
            }
            self.results['errors'].append({
                'type': 'postgresql_error',
                'message': error_msg
            })
        except Exception as e:
            error_msg = f"PostgreSQL validation error: {str(e)}"
            logger.error(error_msg)
            self.results['database_connectivity']['postgresql'] = {
                'status': 'error',
                'error': error_msg
            }
            self.results['errors'].append({
                'type': 'postgresql_validation_error',
                'message': error_msg
            })

    async def _test_redis(self):
        """Test Redis connectivity and basic operations"""
        try:
            config = self.database_configs['redis']
            r = redis.from_url(config['url'])
            
            # Test basic connectivity
            start_time = time.time()
            ping_result = r.ping()
            ping_time = time.time() - start_time
            
            # Test set/get operations
            test_key = 'health_check_test'
            test_value = f'test_{int(time.time())}'
            
            start_time = time.time()
            r.set(test_key, test_value, ex=60)  # Expire in 60 seconds
            retrieved_value = r.get(test_key)
            operation_time = time.time() - start_time
            
            # Get Redis info
            redis_info = r.info()
            
            # Cleanup test key
            r.delete(test_key)
            
            self.results['database_connectivity']['redis'] = {
                'status': 'healthy',
                'ping_response': ping_result,
                'ping_time_seconds': round(ping_time, 4),
                'set_get_operation_time_seconds': round(operation_time, 4),
                'test_successful': retrieved_value.decode('utf-8') == test_value if retrieved_value else False,
                'connected_clients': redis_info.get('connected_clients', 0),
                'used_memory_human': redis_info.get('used_memory_human', 'unknown'),
                'redis_version': redis_info.get('redis_version', 'unknown'),
                'keyspace_hits': redis_info.get('keyspace_hits', 0),
                'keyspace_misses': redis_info.get('keyspace_misses', 0)
            }
            
            logger.info(f"Redis: healthy (version {redis_info.get('redis_version', 'unknown')})")
            
        except redis.RedisError as e:
            error_msg = f"Redis connectivity error: {str(e)}"
            logger.error(error_msg)
            self.results['database_connectivity']['redis'] = {
                'status': 'error',
                'error': error_msg
            }
            self.results['errors'].append({
                'type': 'redis_error',
                'message': error_msg
            })
        except Exception as e:
            error_msg = f"Redis validation error: {str(e)}"
            logger.error(error_msg)
            self.results['database_connectivity']['redis'] = {
                'status': 'error',
                'error': error_msg
            }
            self.results['errors'].append({
                'type': 'redis_validation_error',
                'message': error_msg
            })

    async def _test_weaviate(self):
        """Test Weaviate connectivity and basic operations"""
        try:
            config = self.database_configs['weaviate']
            
            # Test HTTP endpoint
            async with httpx.AsyncClient() as client:
                start_time = time.time()
                response = await client.get(f"{config['url']}{config['test_endpoint']}", timeout=10.0)
                http_response_time = time.time() - start_time
                
                # Test client connectivity
                weaviate_client = weaviate.Client(config['url'])
                
                start_time = time.time()
                is_ready = weaviate_client.is_ready()
                client_check_time = time.time() - start_time
                
                # Get schema information
                start_time = time.time()
                try:
                    schema = weaviate_client.schema.get()
                    schema_classes = [cls['class'] for cls in schema.get('classes', [])]
                except Exception:
                    schema_classes = []
                schema_query_time = time.time() - start_time
                
                # Get cluster status
                try:
                    cluster_status = weaviate_client.cluster.get_nodes_status()
                except Exception:
                    cluster_status = []
                
                self.results['database_connectivity']['weaviate'] = {
                    'status': 'healthy' if response.status_code == 200 and is_ready else 'unhealthy',
                    'http_status_code': response.status_code,
                    'http_response_time_seconds': round(http_response_time, 4),
                    'client_ready': is_ready,
                    'client_check_time_seconds': round(client_check_time, 4),
                    'schema_classes_count': len(schema_classes),
                    'schema_classes': schema_classes,
                    'schema_query_time_seconds': round(schema_query_time, 4),
                    'cluster_nodes': len(cluster_status),
                    'cluster_status': cluster_status
                }
                
                if response.status_code != 200 or not is_ready:
                    self.results['errors'].append({
                        'type': 'weaviate_unhealthy',
                        'status_code': response.status_code,
                        'client_ready': is_ready
                    })
                
                logger.info(f"Weaviate: {'healthy' if response.status_code == 200 and is_ready else 'unhealthy'} ({len(schema_classes)} classes)")
                
        except httpx.RequestError as e:
            error_msg = f"Weaviate HTTP error: {str(e)}"
            logger.error(error_msg)
            self.results['database_connectivity']['weaviate'] = {
                'status': 'error',
                'error': error_msg
            }
            self.results['errors'].append({
                'type': 'weaviate_http_error',
                'message': error_msg
            })
        except Exception as e:
            error_msg = f"Weaviate validation error: {str(e)}"
            logger.error(error_msg)
            self.results['database_connectivity']['weaviate'] = {
                'status': 'error',
                'error': error_msg
            }
            self.results['errors'].append({
                'type': 'weaviate_validation_error',
                'message': error_msg
            })

    async def _validate_api_endpoints(self):
        """Test API endpoints for responsiveness and correctness"""
        logger.info("Validating API endpoints")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for endpoint_name, url in self.api_endpoints.items():
                try:
                    start_time = time.time()
                    response = await client.get(url)
                    response_time = time.time() - start_time
                    
                    # Try to parse JSON response
                    try:
                        json_data = response.json()
                    except Exception:
                        json_data = None
                    
                    self.results['api_endpoints'][endpoint_name] = {
                        'url': url,
                        'status_code': response.status_code,
                        'response_time_seconds': round(response_time, 4),
                        'content_length': len(response.content),
                        'headers': dict(response.headers),
                        'json_parseable': json_data is not None,
                        'response_data': json_data if json_data and len(str(json_data)) < 1000 else None
                    }
                    
                    # Check for errors
                    if response.status_code >= 400:
                        self.results['errors'].append({
                            'type': 'api_endpoint_error',
                            'endpoint': endpoint_name,
                            'url': url,
                            'status_code': response.status_code
                        })
                    elif response_time > 5.0:  # Slow response warning
                        self.results['warnings'].append({
                            'type': 'slow_api_response',
                            'endpoint': endpoint_name,
                            'response_time': response_time
                        })
                    
                    logger.info(f"API {endpoint_name}: {response.status_code} ({response_time:.3f}s)")
                    
                except httpx.RequestError as e:
                    error_msg = f"API request error for {endpoint_name}: {str(e)}"
                    logger.error(error_msg)
                    self.results['api_endpoints'][endpoint_name] = {
                        'url': url,
                        'status': 'error',
                        'error': error_msg
                    }
                    self.results['errors'].append({
                        'type': 'api_request_error',
                        'endpoint': endpoint_name,
                        'message': error_msg
                    })
                except Exception as e:
                    error_msg = f"API validation error for {endpoint_name}: {str(e)}"
                    logger.error(error_msg)
                    self.results['api_endpoints'][endpoint_name] = {
                        'url': url,
                        'status': 'error',
                        'error': error_msg
                    }
                    self.results['errors'].append({
                        'type': 'api_validation_error',
                        'endpoint': endpoint_name,
                        'message': error_msg
                    })

    async def _collect_performance_metrics(self):
        """Collect system performance metrics"""
        logger.info("Collecting performance metrics")
        
        try:
            # Network I/O stats
            net_io = psutil.net_io_counters()
            
            # Disk I/O stats
            disk_io = psutil.disk_io_counters()
            
            # Process count
            process_count = len(psutil.pids())
            
            # Load average (Linux/macOS)
            try:
                load_avg = os.getloadavg()
            except (AttributeError, OSError):
                load_avg = [0, 0, 0]  # Windows fallback
            
            self.results['performance_metrics'] = {
                'network_io': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv
                },
                'disk_io': {
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count,
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes
                } if disk_io else {},
                'system_load': {
                    'load_1min': load_avg[0],
                    'load_5min': load_avg[1],
                    'load_15min': load_avg[2]
                },
                'process_count': process_count,
                'validation_duration_seconds': (datetime.now(timezone.utc) - self.start_time).total_seconds()
            }
            
            logger.info(f"Performance metrics collected - Load: {load_avg[0]:.2f}, Processes: {process_count}")
            
        except Exception as e:
            error_msg = f"Error collecting performance metrics: {str(e)}"
            logger.error(error_msg)
            self.results['errors'].append({
                'type': 'performance_metrics_error',
                'message': error_msg
            })

    def _generate_validation_summary(self):
        """Generate comprehensive validation summary"""
        logger.info("Generating validation summary")
        
        # Count services by status
        running_services = sum(1 for service in self.results['docker_services'].values() if service.get('status') == 'running')
        total_services = len(self.docker_services)
        
        # Count healthy databases
        healthy_databases = sum(1 for db in self.results['database_connectivity'].values() if db.get('status') == 'healthy')
        total_databases = len(self.database_configs)
        
        # Count successful API endpoints
        successful_apis = sum(1 for api in self.results['api_endpoints'].values() if api.get('status_code', 0) < 400)
        total_apis = len(self.api_endpoints)
        
        # System health score (0-100)
        health_score = (
            (running_services / total_services) * 40 +  # 40% weight for services
            (healthy_databases / total_databases) * 35 +  # 35% weight for databases
            (successful_apis / total_apis) * 25  # 25% weight for APIs
        ) * 100
        
        self.results['validation_summary'] = {
            'overall_health_score': round(health_score, 1),
            'total_errors': len(self.results['errors']),
            'total_warnings': len(self.results['warnings']),
            'services_status': {
                'running': running_services,
                'total': total_services,
                'percentage': round((running_services / total_services) * 100, 1)
            },
            'databases_status': {
                'healthy': healthy_databases,
                'total': total_databases,
                'percentage': round((healthy_databases / total_databases) * 100, 1)
            },
            'apis_status': {
                'successful': successful_apis,
                'total': total_apis,
                'percentage': round((successful_apis / total_apis) * 100, 1)
            },
            'validation_timestamp': datetime.now(timezone.utc).isoformat(),
            'validation_duration_seconds': round((datetime.now(timezone.utc) - self.start_time).total_seconds(), 2)
        }
        
        # Determine overall status
        if health_score >= 95:
            status = 'excellent'
        elif health_score >= 85:
            status = 'good'
        elif health_score >= 70:
            status = 'fair'
        elif health_score >= 50:
            status = 'poor'
        else:
            status = 'critical'
        
        self.results['validation_summary']['overall_status'] = status
        
        logger.info(f"Validation complete - Health Score: {health_score:.1f}% ({status})")
        logger.info(f"Services: {running_services}/{total_services}, Databases: {healthy_databases}/{total_databases}, APIs: {successful_apis}/{total_apis}")
        logger.info(f"Errors: {len(self.results['errors'])}, Warnings: {len(self.results['warnings'])}")

    def save_results(self, output_file: Optional[str] = None) -> str:
        """Save validation results to JSON file"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"/home/emergence-admin/Desktop/ReAgent/health-report-{timestamp}.json"
        
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            
            logger.info(f"Validation results saved to: {output_file}")
            return output_file
            
        except Exception as e:
            error_msg = f"Error saving results: {str(e)}"
            logger.error(error_msg)
            return ""

async def main():
    """Main execution function"""
    try:
        # Initialize validator
        validator = SystemHealthValidator()
        
        # Run comprehensive validation
        results = await validator.run_comprehensive_validation()
        
        # Save results
        output_file = validator.save_results()
        
        # Print summary
        summary = results.get('validation_summary', {})
        print(f"\n{'='*60}")
        print("REAGENT SYDNEY - SYSTEM HEALTH VALIDATION REPORT")
        print(f"{'='*60}")
        print(f"Overall Health Score: {summary.get('overall_health_score', 0):.1f}% ({summary.get('overall_status', 'unknown').upper()})")
        print(f"Validation Duration: {summary.get('validation_duration_seconds', 0):.2f} seconds")
        print(f"\nServices: {summary.get('services_status', {}).get('running', 0)}/{summary.get('services_status', {}).get('total', 0)} running ({summary.get('services_status', {}).get('percentage', 0):.1f}%)")
        print(f"Databases: {summary.get('databases_status', {}).get('healthy', 0)}/{summary.get('databases_status', {}).get('total', 0)} healthy ({summary.get('databases_status', {}).get('percentage', 0):.1f}%)")
        print(f"API Endpoints: {summary.get('apis_status', {}).get('successful', 0)}/{summary.get('apis_status', {}).get('total', 0)} successful ({summary.get('apis_status', {}).get('percentage', 0):.1f}%)")
        print(f"\nErrors: {summary.get('total_errors', 0)}")
        print(f"Warnings: {summary.get('total_warnings', 0)}")
        
        if results.get('errors'):
            print(f"\nERRORS:")
            for error in results['errors'][:5]:  # Show first 5 errors
                print(f"  - {error.get('type', 'unknown')}: {error.get('message', error.get('service', 'unknown'))}")
        
        if results.get('warnings'):
            print(f"\nWARNINGS:")
            for warning in results['warnings'][:3]:  # Show first 3 warnings
                print(f"  - {warning.get('type', 'unknown')}: {warning.get('endpoint', warning.get('message', 'unknown'))}")
        
        print(f"\nDetailed report saved to: {output_file}")
        print(f"{'='*60}")
        
        # Exit with appropriate code
        health_score = summary.get('overall_health_score', 0)
        if health_score >= 85:
            sys.exit(0)  # Success
        elif health_score >= 50:
            sys.exit(1)  # Warning
        else:
            sys.exit(2)  # Critical
            
    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Critical error in main execution: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(3)

if __name__ == "__main__":
    asyncio.run(main())