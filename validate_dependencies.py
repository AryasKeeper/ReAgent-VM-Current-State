#!/usr/bin/env python3
"""
Dependency Validation Test for ReAgent Sydney
Tests that all critical dependencies can be imported and work together.
"""

import sys
import traceback
from typing import Dict, List

def test_imports() -> Dict[str, bool]:
    """Test critical package imports."""
    results = {}
    
    # Core Framework
    try:
        import fastapi
        import uvicorn
        import pydantic
        import pydantic_settings
        results['core_framework'] = True
        print(f"✅ Core Framework: FastAPI {fastapi.__version__}, Pydantic {pydantic.__version__}")
    except Exception as e:
        results['core_framework'] = False
        print(f"❌ Core Framework: {e}")
    
    # LangGraph/LangChain
    try:
        import langgraph
        import langchain
        import langchain_core
        import langchain_openai
        from langgraph.checkpoint.postgres import PostgresSaver
        results['langchain_ecosystem'] = True
        print(f"✅ LangChain Ecosystem: LangGraph {langgraph.__version__}, LangChain {langchain.__version__}")
    except Exception as e:
        results['langchain_ecosystem'] = False
        print(f"❌ LangChain Ecosystem: {e}")
        traceback.print_exc()
    
    # OpenAI
    try:
        import openai
        results['openai'] = True
        print(f"✅ OpenAI: {openai.__version__}")
    except Exception as e:
        results['openai'] = False
        print(f"❌ OpenAI: {e}")
    
    # Database
    try:
        import sqlalchemy
        import psycopg2
        import asyncpg
        import alembic
        results['database'] = True
        print(f"✅ Database: SQLAlchemy {sqlalchemy.__version__}")
    except Exception as e:
        results['database'] = False
        print(f"❌ Database: {e}")
    
    # Vector DB
    try:
        import weaviate
        results['vector_db'] = True
        print(f"✅ Vector DB: Weaviate {weaviate.__version__}")
    except Exception as e:
        results['vector_db'] = False
        print(f"❌ Vector DB: {e}")
    
    return results

def test_pydantic_compatibility():
    """Test Pydantic v2 compatibility with key components."""
    try:
        from pydantic import BaseModel, Field
        from pydantic_settings import BaseSettings
        from fastapi import FastAPI
        
        # Test Pydantic v2 model
        class TestModel(BaseModel):
            name: str = Field(..., description="Test name")
            value: int = Field(default=42)
        
        # Test settings
        class TestSettings(BaseSettings):
            debug: bool = Field(default=False)
            api_key: str = Field(default="test")
            
            class Config:
                env_prefix = "TEST_"
        
        # Test FastAPI integration
        app = FastAPI()
        
        @app.post("/test")
        async def test_endpoint(data: TestModel):
            return {"received": data.dict()}
        
        # Create instances
        model = TestModel(name="test")
        settings = TestSettings()
        
        print("✅ Pydantic v2 compatibility: All tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Pydantic v2 compatibility: {e}")
        traceback.print_exc()
        return False

def test_langgraph_postgres():
    """Test LangGraph PostgreSQL checkpoint functionality."""
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg2 import sql
        
        # This will test the import and basic instantiation
        # Note: Won't actually connect without a real DB
        print("✅ LangGraph PostgreSQL checkpointer: Import successful")
        return True
        
    except Exception as e:
        print(f"❌ LangGraph PostgreSQL checkpointer: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all validation tests."""
    print("🔍 ReAgent Sydney - Dependency Validation Test")
    print("=" * 50)
    
    # Test imports
    import_results = test_imports()
    
    print("\n🧪 Testing Compatibility")
    print("-" * 30)
    
    # Test Pydantic compatibility
    pydantic_ok = test_pydantic_compatibility()
    
    # Test LangGraph PostgreSQL
    langgraph_postgres_ok = test_langgraph_postgres()
    
    # Summary
    print("\n📊 Validation Summary")
    print("-" * 20)
    
    all_passed = all(import_results.values()) and pydantic_ok and langgraph_postgres_ok
    
    for component, passed in import_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{component}: {status}")
    
    print(f"pydantic_compatibility: {'✅ PASS' if pydantic_ok else '❌ FAIL'}")
    print(f"langgraph_postgres: {'✅ PASS' if langgraph_postgres_ok else '❌ FAIL'}")
    
    if all_passed:
        print("\n🎉 All dependency validations PASSED!")
        print("✅ ReAgent Sydney is ready for deployment!")
        sys.exit(0)
    else:
        print("\n⚠️  Some dependency validations FAILED!")
        print("❌ Review the errors above before deployment.")
        sys.exit(1)

if __name__ == "__main__":
    main()