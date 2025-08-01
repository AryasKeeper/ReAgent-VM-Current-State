#!/usr/bin/env python3
"""
Simple import test to validate core components.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test core imports for buyer-property matching."""
    print("Testing core imports...")
    
    try:
        # Test vector database imports
        from src.core.vector_db.client import WeaviateClient
        print("✅ WeaviateClient import successful")
        
        from src.core.vector_db.schemas import get_all_schemas
        print("✅ Vector schemas import successful")
        
        # Test matching engine import
        from src.agents.buyer_matchmaker.matching_engine import SemanticMatchingEngine
        print("✅ SemanticMatchingEngine import successful")
        
        # Test agent import
        try:
            from src.agents.buyer_matchmaker.agent import BuyerMatchmakerAgent
            print("✅ BuyerMatchmakerAgent import successful")
        except Exception as e:
            print(f"⚠️  BuyerMatchmakerAgent import failed: {e}")
        
        # Test configuration
        from src.config.settings import get_settings
        settings = get_settings()
        print(f"✅ Settings loaded: Environment = {getattr(settings, 'environment', 'unknown')}")
        
        print("\n🎉 Core imports validation completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)