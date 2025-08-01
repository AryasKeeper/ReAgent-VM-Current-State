#!/usr/bin/env python3
"""
Environment Variable Validation Script
Validates and debugs Docker Compose environment variable propagation

Author: Cloud-Native Infrastructure Engineer
Purpose: Debug and fix environment variable issues in container orchestration
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class EnvironmentValidator:
    """Validates environment variables for Docker Compose deployment."""
    
    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)
        self.required_vars = {
            "POSTGRES_PASSWORD": "Database authentication",
            "OPENAI_API_KEY": "OpenAI API access",
            "WEAVIATE_API_KEY": "Weaviate authentication (production)",
            "REDIS_PASSWORD": "Redis authentication (production)",
            "SECRET_KEY": "Application security"
        }
        self.optional_vars = {
            "DOMAIN_API_KEY": "Domain.com.au API",
            "REA_API_KEY": "RealEstate.com.au API", 
            "CORELOGIC_API_KEY": "CoreLogic API",
            "NSW_LPI_API_KEY": "NSW Land Property Information API",
            "GRAFANA_PASSWORD": "Grafana admin password"
        }
        
    def load_env_file(self) -> Dict[str, str]:
        """Load environment variables from .env file."""
        env_vars = {}
        
        if not self.env_file.exists():
            print(f"❌ Environment file {self.env_file} not found!")
            return env_vars
            
        try:
            with open(self.env_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                        
                    # Parse KEY=VALUE pairs
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
                        print(f"⚠️  Invalid line {line_num}: {line}")
                        
        except Exception as e:
            print(f"❌ Error reading {self.env_file}: {e}")
            
        return env_vars
    
    def validate_env_vars(self, env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
        """Validate required and optional environment variables."""
        issues = []
        all_valid = True
        
        print("🔍 Environment Variable Validation")
        print("=" * 50)
        
        # Check required variables
        print("\n📋 Required Variables:")
        for var, description in self.required_vars.items():
            if var not in env_vars:
                issues.append(f"Missing required variable: {var} ({description})")
                print(f"❌ {var}: MISSING - {description}")
                all_valid = False
            elif not env_vars[var]:
                issues.append(f"Empty required variable: {var} ({description})")
                print(f"⚠️  {var}: EMPTY - {description}")
                all_valid = False
            else:
                # Mask sensitive values
                masked_value = self._mask_sensitive_value(var, env_vars[var])
                print(f"✅ {var}: {masked_value} - {description}")
        
        # Check optional variables
        print("\n📋 Optional Variables:")
        for var, description in self.optional_vars.items():
            if var not in env_vars:
                print(f"⚪ {var}: NOT SET - {description}")
            elif not env_vars[var]:
                print(f"⚠️  {var}: EMPTY - {description}")
            else:
                masked_value = self._mask_sensitive_value(var, env_vars[var])
                print(f"✅ {var}: {masked_value} - {description}")
        
        return all_valid, issues
    
    def _mask_sensitive_value(self, key: str, value: str) -> str:
        """Mask sensitive values for logging."""
        if not value:
            return "EMPTY"
            
        if "API_KEY" in key or "PASSWORD" in key or "SECRET" in key:
            if len(value) <= 8:
                return "***"
            return f"{value[:4]}...{value[-4:]}"
        
        return value
    
    def test_docker_compose_parsing(self) -> bool:
        """Test Docker Compose configuration parsing."""
        print("\n🐳 Docker Compose Configuration Test")
        print("=" * 50)
        
        try:
            # Test configuration parsing
            result = subprocess.run(
                ["docker", "compose", "config", "--services"],
                capture_output=True,
                text=True,
                cwd=self.env_file.parent
            )
            
            if result.returncode == 0:
                services = result.stdout.strip().split('\n')
                print(f"✅ Configuration parsed successfully")
                print(f"📦 Services found: {', '.join(services)}")
                
                # Check for warnings in stderr
                if result.stderr:
                    print(f"\n⚠️  Warnings detected:")
                    for line in result.stderr.strip().split('\n'):
                        if line.strip():
                            print(f"   {line}")
                
                return True
            else:
                print(f"❌ Configuration parsing failed:")
                print(f"   {result.stderr}")
                return False
                
        except FileNotFoundError:
            print("❌ Docker Compose not found. Please install Docker Compose.")
            return False
        except Exception as e:
            print(f"❌ Error testing Docker Compose: {e}")
            return False
    
    def test_container_environment(self, service: str = "weaviate") -> bool:
        """Test environment variables inside a running container."""
        print(f"\n🔧 Container Environment Test ({service})")
        print("=" * 50)
        
        try:
            # Check if container is running
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name=reagent-{service}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True
            )
            
            if not result.stdout.strip():
                print(f"⚪ Container reagent-{service} is not running")
                return False
                
            container_name = result.stdout.strip()
            print(f"📦 Testing container: {container_name}")
            
            # Get environment variables from container
            result = subprocess.run(
                ["docker", "exec", container_name, "env"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                env_vars = {}
                for line in result.stdout.strip().split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
                
                # Check critical variables
                critical_vars = ["OPENAI_API_KEY", "WEAVIATE_API_KEY"]
                for var in critical_vars:
                    if var in env_vars:
                        masked_value = self._mask_sensitive_value(var, env_vars[var])
                        if env_vars[var]:
                            print(f"✅ {var}: {masked_value}")
                        else:
                            print(f"❌ {var}: EMPTY")
                    else:
                        print(f"❌ {var}: NOT FOUND")
                
                return True
            else:
                print(f"❌ Failed to get environment from container: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing container environment: {e}")
            return False
    
    def generate_fixed_env_file(self, env_vars: Dict[str, str]) -> bool:
        """Generate a fixed .env file with proper values."""
        print("\n🔧 Generating Fixed Environment File")
        print("=" * 50)
        
        # Generate WEAVIATE_API_KEY if missing
        if "WEAVIATE_API_KEY" not in env_vars or not env_vars["WEAVIATE_API_KEY"]:
            import secrets
            weaviate_key = f"reagent-{secrets.token_urlsafe(32)}"
            env_vars["WEAVIATE_API_KEY"] = weaviate_key
            print(f"✅ Generated WEAVIATE_API_KEY: {self._mask_sensitive_value('WEAVIATE_API_KEY', weaviate_key)}")
        
        # Generate SECRET_KEY if missing
        if "SECRET_KEY" not in env_vars or not env_vars["SECRET_KEY"]:
            import secrets
            secret_key = secrets.token_urlsafe(32)
            env_vars["SECRET_KEY"] = secret_key
            print(f"✅ Generated SECRET_KEY: {self._mask_sensitive_value('SECRET_KEY', secret_key)}")
        
        # Generate REDIS_PASSWORD if missing
        if "REDIS_PASSWORD" not in env_vars or not env_vars["REDIS_PASSWORD"]:
            import secrets
            redis_password = secrets.token_urlsafe(16)
            env_vars["REDIS_PASSWORD"] = redis_password
            print(f"✅ Generated REDIS_PASSWORD: {self._mask_sensitive_value('REDIS_PASSWORD', redis_password)}")
        
        try:
            # Create backup of original file
            if self.env_file.exists():
                backup_file = self.env_file.with_suffix('.env.backup')
                subprocess.run(["cp", str(self.env_file), str(backup_file)])
                print(f"📋 Backup created: {backup_file}")
            
            # Write updated .env file
            with open(self.env_file, 'w') as f:
                f.write("# ReAgent Sydney - Environment Configuration\n")
                f.write("# Auto-generated with missing variables filled\n")
                f.write(f"# Generated: {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}\n\n")
                
                # Database Configuration
                f.write("# Database Configuration\n")
                f.write(f"POSTGRES_PASSWORD={env_vars.get('POSTGRES_PASSWORD', 'reagent_dev_password')}\n")
                f.write(f"POSTGRES_DB={env_vars.get('POSTGRES_DB', 'reagent')}\n")
                f.write(f"POSTGRES_USER={env_vars.get('POSTGRES_USER', 'reagent')}\n\n")
                
                # Cache Configuration
                f.write("# Redis Configuration\n")
                f.write(f"REDIS_URL={env_vars.get('REDIS_URL', 'redis://redis:6379/0')}\n")
                f.write(f"REDIS_PASSWORD={env_vars.get('REDIS_PASSWORD', '')}\n\n")
                
                # Vector Database Configuration  
                f.write("# Vector Database Configuration\n")
                f.write(f"WEAVIATE_URL={env_vars.get('WEAVIATE_URL', 'http://weaviate:8080')}\n")
                f.write(f"WEAVIATE_API_KEY={env_vars.get('WEAVIATE_API_KEY', '')}\n\n")
                
                # API Keys
                f.write("# OpenAI API Configuration (REQUIRED)\n")
                f.write(f"OPENAI_API_KEY={env_vars.get('OPENAI_API_KEY', '')}\n\n")
                
                f.write("# External Real Estate APIs\n")
                f.write(f"DOMAIN_API_KEY={env_vars.get('DOMAIN_API_KEY', '')}\n")
                f.write(f"REA_API_KEY={env_vars.get('REA_API_KEY', '')}\n")
                f.write(f"CORELOGIC_API_KEY={env_vars.get('CORELOGIC_API_KEY', '')}\n")
                f.write(f"NSW_LPI_API_KEY={env_vars.get('NSW_LPI_API_KEY', '')}\n\n")
                
                # Security
                f.write("# Security\n")
                f.write(f"SECRET_KEY={env_vars.get('SECRET_KEY', '')}\n\n")
                
                # Application Configuration
                f.write("# Application Configuration\n")
                f.write(f"ENVIRONMENT={env_vars.get('ENVIRONMENT', 'development')}\n")
                f.write(f"DEBUG={env_vars.get('DEBUG', 'true')}\n")
                f.write(f"LOG_LEVEL={env_vars.get('LOG_LEVEL', 'INFO')}\n\n")
                
                # Monitoring
                f.write("# Monitoring\n")
                f.write(f"GRAFANA_PASSWORD={env_vars.get('GRAFANA_PASSWORD', 'admin')}\n")
                f.write(f"SENTRY_DSN={env_vars.get('SENTRY_DSN', '')}\n\n")
                
                # Network Configuration
                f.write("# Network Configuration\n")
                f.write(f"ALLOWED_HOSTS={env_vars.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')}\n")
                f.write(f"CORS_ORIGINS={env_vars.get('CORS_ORIGINS', 'http://localhost:3000')}\n")
                f.write(f"API_PORT={env_vars.get('API_PORT', '8000')}\n")
                
            print(f"✅ Updated environment file: {self.env_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error generating fixed environment file: {e}")
            return False
    
    def run_validation(self) -> bool:
        """Run complete environment validation and fixes."""
        print("🚀 ReAgent Environment Variable Validation")
        print("=" * 60)
        
        # Load environment variables
        env_vars = self.load_env_file()
        if not env_vars:
            print("❌ No environment variables loaded!")
            return False
        
        # Validate variables
        all_valid, issues = self.validate_env_vars(env_vars)
        
        if not all_valid:
            print(f"\n❌ Found {len(issues)} environment issues:")
            for issue in issues:
                print(f"   • {issue}")
                
            # Offer to fix
            response = input("\n🔧 Generate fixed .env file? (y/N): ").lower()
            if response == 'y':
                if self.generate_fixed_env_file(env_vars):
                    print("\n✅ Environment file updated. Please review and restart containers.")
                    return True
        
        # Test Docker Compose parsing
        compose_ok = self.test_docker_compose_parsing()
        
        # Test container environment if running
        container_ok = self.test_container_environment()
        
        print(f"\n📊 Validation Summary:")
        print(f"   Environment file: {'✅' if all_valid else '❌'}")
        print(f"   Docker Compose:   {'✅' if compose_ok else '❌'}")
        print(f"   Container test:   {'✅' if container_ok else '⚪'}")
        
        return all_valid and compose_ok


def main():
    """Main execution function."""
    validator = EnvironmentValidator()
    success = validator.run_validation()
    
    if success:
        print("\n🎉 Environment validation completed successfully!")
        return 0
    else:
        print("\n⚠️  Environment validation found issues. Please fix and retry.")
        return 1


if __name__ == "__main__":
    sys.exit(main())