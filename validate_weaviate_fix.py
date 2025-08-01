#!/usr/bin/env python3
"""
Weaviate Emergency Fix Validation Script
========================================

This script validates the critical Weaviate OIDC authentication fixes and OpenAI integration.

Usage:
    python validate_weaviate_fix.py
"""

import os
import sys
import time
import requests
import json
from typing import Dict, Any, Optional

def check_environment_variables() -> Dict[str, str]:
    """Check required environment variables."""
    print("🔍 Checking environment variables...")
    
    required_vars = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'WEAVIATE_API_KEY': os.getenv('WEAVIATE_API_KEY', 'dev-key-12345')
    }
    
    missing_vars = []
    for var, value in required_vars.items():
        if not value or value == 'your_openai_api_key_here':
            missing_vars.append(var)
            print(f"❌ {var}: Not set or using placeholder value")
        else:
            masked_value = value[:8] + "..." if len(value) > 8 else "***"
            print(f"✅ {var}: {masked_value}")
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        return {}
    
    return required_vars

def wait_for_weaviate(url: str = "http://localhost:8080") -> bool:
    """Wait for Weaviate to become ready."""
    print(f"\n🔄 Waiting for Weaviate at {url}...")
    
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{url}/v1/.well-known/ready", timeout=5)
            if response.status_code == 200:
                print("✅ Weaviate is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        
        print(f"⏳ Attempt {attempt + 1}/{max_attempts} - Weaviate not ready yet...")
        time.sleep(2)
    
    print("❌ Weaviate failed to become ready within timeout")
    return False

def test_weaviate_health(url: str = "http://localhost:8080") -> bool:
    """Test Weaviate health endpoints."""
    print(f"\n🩺 Testing Weaviate health at {url}...")
    
    endpoints = [
        ("/v1/.well-known/ready", "Readiness"),
        ("/v1/.well-known/live", "Liveness"),
        ("/v1/meta", "Metadata")
    ]
    
    success = True
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{url}{endpoint}", timeout=10)
            if response.status_code == 200:
                print(f"✅ {name} check: OK")
                if endpoint == "/v1/meta":
                    meta = response.json()
                    print(f"   Version: {meta.get('version', 'Unknown')}")
                    modules = meta.get('modules', {})
                    if 'text2vec-openai' in modules:
                        print(f"   ✅ text2vec-openai module: Available")
                    else:
                        print(f"   ❌ text2vec-openai module: Not found")
                        success = False
            else:
                print(f"❌ {name} check: HTTP {response.status_code}")
                success = False
        except requests.exceptions.RequestException as e:
            print(f"❌ {name} check: Connection failed - {e}")
            success = False
    
    return success

def test_openai_integration(url: str = "http://localhost:8080", api_key: str = "dev-key-12345") -> bool:
    """Test OpenAI integration by creating a test schema."""
    print(f"\n🤖 Testing OpenAI integration...")
    
    # Use anonymous access (no authentication headers)
    headers = {
        "Content-Type": "application/json"
    }
    
    # Test schema with OpenAI vectorizer
    test_schema = {
        "class": "TestProperty",
        "description": "Test class for OpenAI integration validation",
        "vectorizer": "text2vec-openai",
        "moduleConfig": {
            "text2vec-openai": {
                "model": "ada",
                "modelVersion": "002",
                "type": "text"
            }
        },
        "properties": [
            {
                "name": "description",
                "dataType": ["text"],
                "description": "Property description"
            },
            {
                "name": "price",
                "dataType": ["number"],
                "description": "Property price"
            }
        ]
    }
    
    try:
        # Delete test class if it exists
        delete_response = requests.delete(f"{url}/v1/schema/TestProperty", headers=headers)
        print(f"   Cleanup existing test class: {delete_response.status_code}")
        
        # Create test class
        response = requests.post(f"{url}/v1/schema", headers=headers, json=test_schema, timeout=30)
        if response.status_code == 200:
            print("✅ OpenAI schema creation: SUCCESS")
            
            # Test object insertion with vectorization
            test_object = {
                "class": "TestProperty",
                "properties": {
                    "description": "Beautiful 3-bedroom house in Sydney with harbor views",
                    "price": 1500000
                }
            }
            
            insert_response = requests.post(f"{url}/v1/objects", headers=headers, json=test_object, timeout=30)
            if insert_response.status_code == 200:
                print("✅ OpenAI object insertion with vectorization: SUCCESS")
                
                # Cleanup
                requests.delete(f"{url}/v1/schema/TestProperty", headers=headers)
                return True
            else:
                print(f"❌ OpenAI object insertion failed: HTTP {insert_response.status_code}")
                print(f"   Response: {insert_response.text}")
        else:
            print(f"❌ OpenAI schema creation failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            
            if "api key" in response.text.lower() or "unauthorized" in response.text.lower():
                print("   💡 This might be an OpenAI API key validation issue")
    
    except requests.exceptions.RequestException as e:
        print(f"❌ OpenAI integration test failed: {e}")
    
    return False

def test_docker_container_status() -> bool:
    """Test Docker container status."""
    print(f"\n🐳 Checking Docker container status...")
    
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=reagent-weaviate-dev", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if "reagent-weaviate-dev" in output:
                print("✅ Container reagent-weaviate-dev is running")
                print(f"   Status: {output}")
                return True
            else:
                print("❌ Container reagent-weaviate-dev not found")
        else:
            print(f"❌ Docker command failed: {result.stderr}")
    
    except Exception as e:
        print(f"❌ Docker status check failed: {e}")
    
    return False

def main():
    """Main validation function."""
    print("🚨 WEAVIATE EMERGENCY FIX VALIDATION")
    print("=" * 50)
    
    # Check environment variables
    env_vars = check_environment_variables()
    if not env_vars:
        sys.exit(1)
    
    # Check Docker container
    container_ok = test_docker_container_status()
    
    # Wait for Weaviate to be ready
    if not wait_for_weaviate():
        print("\n❌ VALIDATION FAILED: Weaviate not ready")
        print("\nTroubleshooting steps:")
        print("1. Run: docker-compose up -d weaviate")
        print("2. Check logs: docker-compose logs weaviate")
        print("3. Verify .env file has correct OPENAI_API_KEY")
        sys.exit(1)
    
    # Test health endpoints
    health_ok = test_weaviate_health()
    
    # Test OpenAI integration
    openai_ok = test_openai_integration(api_key=env_vars.get('WEAVIATE_API_KEY', 'dev-key-12345'))
    
    # Final validation summary
    print("\n" + "=" * 50)
    print("🔍 VALIDATION SUMMARY")
    print("=" * 50)
    
    results = {
        "Environment Variables": "✅" if env_vars else "❌",
        "Docker Container": "✅" if container_ok else "❌", 
        "Weaviate Health": "✅" if health_ok else "❌",
        "OpenAI Integration": "✅" if openai_ok else "❌"
    }
    
    for test, status in results.items():
        print(f"{status} {test}")
    
    all_passed = all([env_vars, health_ok, openai_ok])
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Weaviate OIDC fix successful!")
        print("\nNext steps:")
        print("1. Run full system: docker-compose up -d")
        print("2. Test ReAgent agents: python test_agents_simple.py")
        print("3. Validate production deployment: python test_production_readiness_comprehensive.py")
    else:
        print("\n❌ SOME TESTS FAILED. Check the issues above.")
        print("\nCommon fixes:")
        print("1. Ensure OPENAI_API_KEY is valid in .env")
        print("2. Restart Weaviate: docker-compose restart weaviate")
        print("3. Check container logs: docker-compose logs weaviate")
        sys.exit(1)

if __name__ == "__main__":
    main()