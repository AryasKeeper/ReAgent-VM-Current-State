#!/usr/bin/env python3
"""
Test Weaviate OpenAI Integration Validation
Tests if environment variables are properly configured and OpenAI API key works
"""

import requests
import json
import sys
import os

def test_weaviate_connection():
    """Test basic Weaviate connection"""
    try:
        response = requests.get("http://localhost:8080/v1/meta")
        if response.status_code == 200:
            print("✅ Weaviate connection successful")
            meta = response.json()
            print(f"   Version: {meta.get('version', 'unknown')}")
            print(f"   Modules: {list(meta.get('modules', {}).keys())}")
            return True
        else:
            print(f"❌ Weaviate connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Weaviate connection error: {e}")
        return False

def test_openai_vectorizer():
    """Test OpenAI vectorizer by creating a test schema"""
    schema = {
        "class": "TestEmbedding",
        "description": "Test class for OpenAI embedding validation",
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
                "name": "content",
                "dataType": ["text"],
                "description": "Test content for embedding",
                "moduleConfig": {
                    "text2vec-openai": {
                        "skip": False,
                        "vectorizePropertyName": False
                    }
                }
            }
        ]
    }
    
    try:
        # Create schema
        response = requests.post(
            "http://localhost:8080/v1/schema",
            headers={"Content-Type": "application/json"},
            data=json.dumps(schema)
        )
        
        if response.status_code == 200:
            print("✅ Test schema created successfully")
        elif response.status_code == 422 and "already exists" in response.text:
            print("ℹ️  Test schema already exists, continuing...")
        else:
            print(f"❌ Schema creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
        # Test object creation with vectorization
        test_object = {
            "class": "TestEmbedding",
            "properties": {
                "content": "This is a test property for validating OpenAI embeddings integration."
            }
        }
        
        response = requests.post(
            "http://localhost:8080/v1/objects",
            headers={"Content-Type": "application/json"},
            data=json.dumps(test_object)
        )
        
        if response.status_code == 200:
            print("✅ Test object created and vectorized successfully")
            obj_data = response.json()
            if obj_data.get('vector'):
                print(f"   Vector dimension: {len(obj_data['vector'])}")
                return True
            else:
                print("❌ Object created but no vector generated")
                return False
        else:
            print(f"❌ Object creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
            # Check if it's an API key issue
            if "401" in str(response.status_code) or "unauthorized" in response.text.lower():
                print("🔑 This appears to be an OpenAI API key authentication issue")
            
            return False
            
    except Exception as e:
        print(f"❌ OpenAI vectorizer test error: {e}")
        return False

def cleanup_test_schema():
    """Clean up test schema"""
    try:
        response = requests.delete("http://localhost:8080/v1/schema/TestEmbedding")
        if response.status_code == 200:
            print("🧹 Test schema cleaned up")
        elif response.status_code == 404:
            print("ℹ️  Test schema not found (already cleaned)")
        else:
            print(f"⚠️  Schema cleanup warning: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Schema cleanup error: {e}")

def main():
    """Main validation test"""
    print("🔍 WEAVIATE OPENAI INTEGRATION VALIDATION")
    print("=" * 50)
    
    success = True
    
    print("\n1. Testing Weaviate Connection...")
    if not test_weaviate_connection():
        success = False
    
    print("\n2. Testing OpenAI Vectorizer...")
    if not test_openai_vectorizer():
        success = False
    
    print("\n3. Cleaning up...")
    cleanup_test_schema()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 ALL TESTS PASSED - Environment variables properly configured!")
        sys.exit(0)
    else:
        print("💥 TESTS FAILED - Environment variable issues detected")
        sys.exit(1)

if __name__ == "__main__":
    main()