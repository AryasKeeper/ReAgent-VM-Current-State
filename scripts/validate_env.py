#!/usr/bin/env python3
"""
Environment Variable Validation and Debugging Tool
Cloud-Native Infrastructure Solution for ReAgent Sydney

This tool validates environment variables, checks Docker environment propagation,
and provides debugging capabilities for container orchestration issues.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EnvValidationResult:
    """Results of environment variable validation"""
    variable: str
    status: str  # 'present', 'missing', 'empty', 'invalid'
    value_preview: str  # First 10 chars or masked for secrets
    source: str  # 'env_file', 'environment', 'default'
    required: bool
    validation_message: str


class EnvironmentValidator:
    """
    Cloud-native environment variable validator and debugger
    
    Features:
    - Validate required environment variables
    - Check Docker container environment propagation
    - Debug .env file loading issues
    - Generate environment variable documentation
    - Validate API key formats
    """
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.env_file = self.project_root / '.env'
        self.env_example = self.project_root / '.env.example'
        
        # Define required environment variables by service
        self.required_vars = {
            'database': [
                ('POSTGRES_PASSWORD', True, 'Database password'),
                ('POSTGRES_DB', False, 'Database name'),
                ('POSTGRES_USER', False, 'Database user'),
            ],
            'redis': [
                ('REDIS_URL', False, 'Redis connection URL'),
                ('REDIS_PASSWORD', False, 'Redis password'),
            ],
            'weaviate': [
                ('WEAVIATE_URL', False, 'Weaviate connection URL'),
                ('WEAVIATE_API_KEY', False, 'Weaviate API key'),
                ('OPENAI_API_KEY', True, 'OpenAI API key for embeddings'),
            ],
            'external_apis': [
                ('DOMAIN_API_KEY', False, 'Domain.com.au API key'),
                ('REA_API_KEY', False, 'RealEstate.com.au API key'),
                ('CORELOGIC_API_KEY', False, 'CoreLogic API key'),
                ('NSW_LPI_API_KEY', False, 'NSW LPI API key'),
            ],
            'application': [
                ('SECRET_KEY', True, 'Application secret key'),
                ('ENVIRONMENT', False, 'Environment (dev/prod)'),
                ('DEBUG', False, 'Debug mode'),
                ('LOG_LEVEL', False, 'Logging level'),
            ]
        }
    
    def load_env_file(self) -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_vars = {}
        
        if not self.env_file.exists():
            print(f"⚠️  WARNING: .env file not found at {self.env_file}")
            return env_vars
        
        try:
            with open(self.env_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse KEY=VALUE
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        env_vars[key] = value
                    else:
                        print(f"⚠️  WARNING: Invalid line format in .env (line {line_num}): {line}")
        
        except Exception as e:
            print(f"❌ ERROR: Failed to load .env file: {e}")
        
        return env_vars
    
    def validate_api_key(self, key: str, value: str) -> Tuple[bool, str]:
        """Validate API key format"""
        if not value or value.lower() in ['your_key_here', 'change_me', 'placeholder']:
            return False, "Placeholder value detected"
        
        # OpenAI API key validation
        if key == 'OPENAI_API_KEY':
            if not value.startswith('sk-'):
                return False, "OpenAI API key must start with 'sk-'"
            if len(value) < 50:
                return False, "OpenAI API key appears too short"
            return True, "Valid OpenAI API key format"
        
        # Generic API key validation
        if len(value) < 10:
            return False, "API key appears too short"
        
        return True, "API key format appears valid"
    
    def mask_sensitive_value(self, key: str, value: str) -> str:
        """Mask sensitive values for display"""
        sensitive_keywords = ['password', 'key', 'secret', 'token']
        
        if any(keyword in key.lower() for keyword in sensitive_keywords):
            if len(value) <= 10:
                return '*' * len(value)
            return value[:4] + '*' * (len(value) - 8) + value[-4:]
        
        return value[:50] + '...' if len(value) > 50 else value
    
    def validate_environment(self) -> List[EnvValidationResult]:
        """Validate all environment variables"""
        results = []
        env_file_vars = self.load_env_file()
        
        print(f"🔍 Validating environment variables...")
        print(f"📁 Project root: {self.project_root}")
        print(f"📄 .env file: {'✅ Found' if self.env_file.exists() else '❌ Missing'}")
        print()
        
        for service, variables in self.required_vars.items():
            print(f"🔧 {service.upper()} SERVICE:")
            
            for var_name, required, description in variables:
                # Check multiple sources for the variable
                value = None
                source = 'missing'
                
                # 1. Check environment (runtime)
                if var_name in os.environ:
                    value = os.environ[var_name]
                    source = 'environment'
                # 2. Check .env file
                elif var_name in env_file_vars:
                    value = env_file_vars[var_name]
                    source = 'env_file'
                # 3. Check for default values
                elif var_name == 'POSTGRES_DB':
                    value = 'reagent'
                    source = 'default'
                elif var_name == 'POSTGRES_USER':
                    value = 'reagent'
                    source = 'default'
                elif var_name == 'ENVIRONMENT':
                    value = 'development'
                    source = 'default'
                
                # Determine status
                if value is None:
                    status = 'missing'
                elif value == '':
                    status = 'empty'
                else:
                    # Validate API keys
                    if 'api_key' in var_name.lower() or var_name.endswith('_KEY'):
                        is_valid, message = self.validate_api_key(var_name, value)
                        status = 'present' if is_valid else 'invalid'
                        validation_message = message
                    else:
                        status = 'present'
                        validation_message = "Present and valid"
                
                # Create result
                result = EnvValidationResult(
                    variable=var_name,
                    status=status,
                    value_preview=self.mask_sensitive_value(var_name, value or ''),
                    source=source,
                    required=required,
                    validation_message=validation_message if 'validation_message' in locals() else description
                )
                results.append(result)
                
                # Display result
                status_icon = {
                    'present': '✅',
                    'missing': '❌' if required else '⚠️',
                    'empty': '⚠️',
                    'invalid': '❌'
                }[status]
                
                print(f"  {status_icon} {var_name:<20} ({source:<12}) {result.value_preview}")
                if status in ['missing', 'empty', 'invalid'] and required:
                    print(f"     🔥 CRITICAL: {validation_message}")
                elif status in ['invalid']:
                    print(f"     ⚠️  WARNING: {validation_message}")
            
            print()
        
        return results
    
    def check_docker_environment(self, service_name: str = 'weaviate') -> Dict:
        """Check environment variables inside Docker container"""
        try:
            # Get container environment
            cmd = f"docker compose exec {service_name} env"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f"Container '{service_name}' not running or accessible",
                    'stderr': result.stderr
                }
            
            # Parse environment variables
            container_env = {}
            for line in result.stdout.strip().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    container_env[key] = value
            
            return {
                'success': True,
                'environment': container_env,
                'container': service_name
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f"Timeout checking container '{service_name}'"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to check container environment: {e}"
            }
    
    def debug_docker_compose_env(self) -> Dict:
        """Debug Docker Compose environment variable propagation"""
        print("🐳 DOCKER COMPOSE ENVIRONMENT DEBUG")
        print("=" * 60)
        
        debug_info = {
            'timestamp': datetime.now().isoformat(),
            'env_file_exists': self.env_file.exists(),
            'env_file_vars': {},
            'container_checks': {},
            'compose_config': None
        }
        
        # Load .env file variables
        if self.env_file.exists():
            debug_info['env_file_vars'] = self.load_env_file()
        
        # Check Docker Compose configuration
        try:
            cmd = "docker compose config --format json"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                debug_info['compose_config'] = json.loads(result.stdout)
                print("✅ Docker Compose configuration loaded successfully")
            else:
                print(f"❌ Failed to load Docker Compose config: {result.stderr}")
                debug_info['compose_config_error'] = result.stderr
        
        except Exception as e:
            print(f"❌ Error checking Docker Compose config: {e}")
            debug_info['compose_config_error'] = str(e)
        
        # Check container environments
        services_to_check = ['weaviate', 'api', 'postgres', 'redis']
        
        for service in services_to_check:
            print(f"\n🔍 Checking {service} container environment...")
            container_info = self.check_docker_environment(service)
            debug_info['container_checks'][service] = container_info
            
            if container_info['success']:
                env = container_info['environment']
                
                # Check critical variables for this service
                critical_vars = []
                if service == 'weaviate':
                    critical_vars = ['OPENAI_APIKEY', 'OPENAI_API_KEY', 'WEAVIATE_API_KEY']
                elif service == 'api':
                    critical_vars = ['OPENAI_API_KEY', 'DATABASE_URL', 'WEAVIATE_URL']
                elif service == 'postgres':
                    critical_vars = ['POSTGRES_PASSWORD', 'POSTGRES_DB']
                elif service == 'redis':
                    critical_vars = ['REDIS_PASSWORD']
                
                for var in critical_vars:
                    if var in env:
                        masked_value = self.mask_sensitive_value(var, env[var])
                        print(f"  ✅ {var} = {masked_value}")
                    else:
                        print(f"  ❌ {var} = <MISSING>")
            else:
                print(f"  ❌ {container_info['error']}")
        
        return debug_info
    
    def generate_report(self, output_file: str = None) -> str:
        """Generate comprehensive environment validation report"""
        validation_results = self.validate_environment()
        docker_debug = self.debug_docker_compose_env()
        
        # Generate report
        report = {
            'timestamp': datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'validation_summary': {
                'total_variables': len(validation_results),
                'present': len([r for r in validation_results if r.status == 'present']),
                'missing': len([r for r in validation_results if r.status == 'missing']),
                'empty': len([r for r in validation_results if r.status == 'empty']),
                'invalid': len([r for r in validation_results if r.status == 'invalid']),
                'critical_missing': len([r for r in validation_results if r.status == 'missing' and r.required])
            },
            'validation_results': [
                {
                    'variable': r.variable,
                    'status': r.status,
                    'value_preview': r.value_preview,
                    'source': r.source,
                    'required': r.required,
                    'message': r.validation_message
                }
                for r in validation_results
            ],
            'docker_debug': docker_debug,
            'recommendations': self.generate_recommendations(validation_results)
        }
        
        # Save report if requested
        if output_file:
            output_path = Path(output_file)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Report saved to: {output_path}")
        
        return json.dumps(report, indent=2)
    
    def generate_recommendations(self, results: List[EnvValidationResult]) -> List[str]:
        """Generate actionable recommendations based on validation results"""
        recommendations = []
        
        # Check for critical missing variables
        critical_missing = [r for r in results if r.status == 'missing' and r.required]
        if critical_missing:
            recommendations.append(
                f"🔥 CRITICAL: {len(critical_missing)} required environment variables are missing. "
                f"Add them to your .env file: {', '.join(r.variable for r in critical_missing)}"
            )
        
        # Check for invalid API keys
        invalid_keys = [r for r in results if r.status == 'invalid']
        if invalid_keys:
            recommendations.append(
                f"⚠️  WARNING: {len(invalid_keys)} API keys appear invalid. "
                f"Please verify: {', '.join(r.variable for r in invalid_keys)}"
            )
        
        # Check for placeholder values
        placeholder_vars = [r for r in results if 'placeholder' in r.validation_message.lower()]
        if placeholder_vars:
            recommendations.append(
                f"📝 UPDATE: {len(placeholder_vars)} variables still have placeholder values. "
                f"Update with real values: {', '.join(r.variable for r in placeholder_vars)}"
            )
        
        # Docker-specific recommendations
        recommendations.append("🐳 DOCKER: Add 'env_file: .env' to all services in docker-compose.yml")
        recommendations.append("🔐 SECURITY: Use Docker secrets for production deployment")
        recommendations.append("📊 MONITORING: Implement environment variable validation in startup scripts")
        
        return recommendations


def main():
    """Main entry point for environment validation tool"""
    print("🚀 REAGENT SYDNEY - ENVIRONMENT VALIDATOR")
    print("=" * 60)
    print("Cloud-Native Infrastructure Environment Debugging Tool")
    print()
    
    # Initialize validator
    validator = EnvironmentValidator()
    
    # Generate comprehensive report
    report_file = f"environment_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_json = validator.generate_report(report_file)
    
    # Display summary
    report_data = json.loads(report_json)
    summary = report_data['validation_summary']
    
    print("\n📊 VALIDATION SUMMARY")
    print("-" * 30)
    print(f"Total Variables: {summary['total_variables']}")
    print(f"✅ Present:      {summary['present']}")
    print(f"❌ Missing:      {summary['missing']}")
    print(f"⚠️  Empty:        {summary['empty']}")
    print(f"🚨 Invalid:      {summary['invalid']}")
    print(f"🔥 Critical:     {summary['critical_missing']}")
    
    print("\n💡 RECOMMENDATIONS")
    print("-" * 30)
    for i, rec in enumerate(report_data['recommendations'], 1):
        print(f"{i}. {rec}")
    
    # Exit with appropriate code
    if summary['critical_missing'] > 0:
        print(f"\n❌ CRITICAL ISSUES FOUND - Fix {summary['critical_missing']} missing required variables")
        sys.exit(1)
    elif summary['missing'] > 0 or summary['invalid'] > 0:
        print(f"\n⚠️  WARNINGS FOUND - Consider fixing {summary['missing'] + summary['invalid']} issues")
        sys.exit(0)
    else:
        print("\n✅ ALL ENVIRONMENT VARIABLES VALIDATED SUCCESSFULLY")
        sys.exit(0)


if __name__ == '__main__':
    main()