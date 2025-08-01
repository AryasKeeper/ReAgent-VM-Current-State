#!/usr/bin/env python3
"""
ReAgent Sydney - API Configuration Validation Script

Tests all external API connections and validates configuration.
Run this script after setting up API keys to ensure all integrations work.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import aiohttp
import structlog

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.external_apis.domain_client import DomainAPIClient
from services.external_apis.realestate_client import RealEstateAPIClient
from config.settings import get_settings


logger = structlog.get_logger(__name__)


class APIValidator:
    """Validates all external API configurations and connections."""
    
    def __init__(self):
        self.settings = get_settings()
        self.results = []
    
    async def validate_domain_api(self) -> Dict[str, Any]:
        """Validate Domain.com.au API connection."""
        result = {
            "service": "Domain.com.au",
            "status": "unknown",
            "details": {}
        }
        
        try:
            # Check if API key is configured
            if not self.settings.apis.domain_api_key or self.settings.apis.domain_api_key == "REPLACE_WITH_ACTUAL_API_KEY":
                result["status"] = "not_configured"
                result["details"]["error"] = "API key not set or still placeholder"
                return result
            
            # Test API connection
            async with DomainAPIClient() as client:
                health = await client.get_health_status()
                
                if health["status"] == "healthy":
                    result["status"] = "healthy"
                    result["details"]["rate_limit_remaining"] = health["rate_limit_remaining"]
                    result["details"]["last_check"] = health["last_check"]
                else:
                    result["status"] = "unhealthy"
                    result["details"]["error"] = health.get("error", "Unknown error")
                    
        except Exception as e:
            result["status"] = "error"
            result["details"]["error"] = str(e)
        
        return result
    
    async def validate_realestate_api(self) -> Dict[str, Any]:
        """Validate RealEstate.com.au API connection."""
        result = {
            "service": "RealEstate.com.au",
            "status": "unknown",
            "details": {}
        }
        
        try:
            # Check if API key is configured
            if not self.settings.apis.rea_api_key or self.settings.apis.rea_api_key == "REPLACE_WITH_ACTUAL_API_KEY":
                result["status"] = "not_configured"
                result["details"]["error"] = "API key not set or still placeholder"
                return result
            
            # Test API connection
            async with RealEstateAPIClient() as client:
                health = await client.get_health_status()
                
                if health["status"] == "healthy":
                    result["status"] = "healthy"
                    result["details"]["rate_limit_remaining"] = health["rate_limit_remaining"]
                    result["details"]["last_check"] = health["last_check"]
                else:
                    result["status"] = "unhealthy"
                    result["details"]["error"] = health.get("error", "Unknown error")
                    
        except Exception as e:
            result["status"] = "error"
            result["details"]["error"] = str(e)
        
        return result
    
    async def validate_openai_api(self) -> Dict[str, Any]:
        """Validate OpenAI API connection."""
        result = {
            "service": "OpenAI",
            "status": "unknown",
            "details": {}
        }
        
        try:
            # Check if API key is configured
            if not self.settings.apis.openai_api_key or self.settings.apis.openai_api_key == "REPLACE_WITH_ACTUAL_API_KEY":
                result["status"] = "not_configured"
                result["details"]["error"] = "API key not set or still placeholder"
                return result
            
            # Test API connection with simple request
            headers = {
                "Authorization": f"Bearer {self.settings.apis.openai_api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.openai.com/v1/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result["status"] = "healthy"
                        result["details"]["models_available"] = len(data.get("data", []))
                    else:
                        result["status"] = "unhealthy"
                        result["details"]["error"] = f"HTTP {response.status}: {await response.text()}"
                        
        except Exception as e:
            result["status"] = "error"
            result["details"]["error"] = str(e)
        
        return result
    
    async def validate_corelogic_api(self) -> Dict[str, Any]:
        """Validate CoreLogic API connection."""
        result = {
            "service": "CoreLogic",
            "status": "unknown",
            "details": {}
        }
        
        try:
            # Check if API key is configured
            if not self.settings.apis.corelogic_api_key or self.settings.apis.corelogic_api_key == "REPLACE_WITH_ACTUAL_API_KEY":
                result["status"] = "not_configured"
                result["details"]["error"] = "API key not set or still placeholder"
                result["details"]["note"] = "CoreLogic integration not yet implemented"
                return result
            
            result["status"] = "not_implemented"
            result["details"]["note"] = "CoreLogic client not yet implemented"
                        
        except Exception as e:
            result["status"] = "error"
            result["details"]["error"] = str(e)
        
        return result
    
    async def validate_nsw_lpi_api(self) -> Dict[str, Any]:
        """Validate NSW LPI API connection."""
        result = {
            "service": "NSW LPI",
            "status": "unknown",
            "details": {}
        }
        
        try:
            # Check if API key is configured
            if not self.settings.apis.nsw_lpi_api_key or self.settings.apis.nsw_lpi_api_key == "REPLACE_WITH_ACTUAL_API_KEY":
                result["status"] = "not_configured"
                result["details"]["error"] = "API key not set or still placeholder"
                result["details"]["note"] = "NSW LPI integration not yet implemented"
                return result
            
            result["status"] = "not_implemented"
            result["details"]["note"] = "NSW LPI client not yet implemented"
                        
        except Exception as e:
            result["status"] = "error"
            result["details"]["error"] = str(e)
        
        return result
    
    async def validate_all_apis(self) -> List[Dict[str, Any]]:
        """Validate all API connections in parallel."""
        logger.info("Starting API validation...")
        
        # Run all validations in parallel
        tasks = [
            self.validate_domain_api(),
            self.validate_realestate_api(),
            self.validate_openai_api(),
            self.validate_corelogic_api(),
            self.validate_nsw_lpi_api()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        validated_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                validated_results.append({
                    "service": f"API_{i}",
                    "status": "error",
                    "details": {"error": str(result)}
                })
            else:
                validated_results.append(result)
        
        self.results = validated_results
        return validated_results
    
    def print_results(self) -> None:
        """Print validation results in a formatted way."""
        print("\n" + "="*60)
        print("API VALIDATION RESULTS")
        print("="*60)
        
        healthy_count = 0
        total_count = len(self.results)
        
        for result in self.results:
            service = result["service"]
            status = result["status"]
            details = result["details"]
            
            # Status indicator
            if status == "healthy":
                indicator = "✅"
                healthy_count += 1
            elif status == "not_configured":
                indicator = "⚠️"
            elif status == "not_implemented":
                indicator = "🚧"
            else:
                indicator = "❌"
            
            print(f"\n{indicator} {service}: {status.upper()}")
            
            # Print details
            for key, value in details.items():
                if key == "error":
                    print(f"   Error: {value}")
                elif key == "note":
                    print(f"   Note: {value}")
                else:
                    print(f"   {key.replace('_', ' ').title()}: {value}")
        
        print("\n" + "="*60)
        print(f"SUMMARY: {healthy_count}/{total_count} APIs are healthy and ready")
        
        if healthy_count < total_count:
            print("\nNext steps:")
            for result in self.results:
                if result["status"] == "not_configured":
                    print(f"- Configure API key for {result['service']}")
                elif result["status"] == "error":
                    print(f"- Fix connection issue with {result['service']}")
        
        print("="*60 + "\n")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of validation results."""
        summary = {
            "total_apis": len(self.results),
            "healthy": 0,
            "not_configured": 0,
            "not_implemented": 0,
            "errors": 0,
            "ready_for_production": False
        }
        
        for result in self.results:
            status = result["status"]
            if status == "healthy":
                summary["healthy"] += 1
            elif status == "not_configured":
                summary["not_configured"] += 1
            elif status == "not_implemented":
                summary["not_implemented"] += 1
            else:
                summary["errors"] += 1
        
        # At least Domain and RealEstate should be healthy for production
        domain_healthy = any(r["service"] == "Domain.com.au" and r["status"] == "healthy" for r in self.results)
        rea_healthy = any(r["service"] == "RealEstate.com.au" and r["status"] == "healthy" for r in self.results)
        
        summary["ready_for_production"] = domain_healthy and rea_healthy
        
        return summary


async def main():
    """Main validation function."""
    validator = APIValidator()
    
    try:
        # Validate all APIs
        await validator.validate_all_apis()
        
        # Print results
        validator.print_results()
        
        # Get summary
        summary = validator.get_summary()
        
        # Exit with appropriate code
        if summary["ready_for_production"]:
            print("🎉 System is ready for production deployment!")
            sys.exit(0)
        else:
            print("⚠️  System needs configuration before production deployment.")
            sys.exit(1)
            
    except Exception as e:
        logger.error("API validation failed", error=str(e))
        print(f"❌ Validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())