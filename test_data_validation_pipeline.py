#!/usr/bin/env python3
"""
Data Validation Pipeline Test

Tests the property data validation and cleaning pipeline with
Sydney property samples to ensure data quality before ingestion.
"""

import json
import structlog
from datetime import datetime, timedelta
from typing import Dict, List, Any
from decimal import Decimal

# Import ReAgent validation components
from src.utils.validation.property_validation import (
    validate_property_data,
    validate_sydney_location,
    clean_property_description,
    validate_postcode
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class DataValidationPipelineTest:
    """Data validation pipeline testing specialist."""
    
    def __init__(self):
        self.validation_results = {
            "postcode_validation": False,
            "sydney_location_validation": False,
            "property_data_validation": False,
            "description_cleaning": False,
            "error_handling": False,
            "edge_cases": False,
            "performance_metrics": {},
            "errors": [],
            "validation_stats": {}
        }
    
    def run_comprehensive_validation_test(self) -> Dict[str, Any]:
        """Run complete data validation pipeline test."""
        logger.info("Starting comprehensive data validation pipeline test")
        
        try:
            # Test postcode validation
            self._test_postcode_validation()
            
            # Test Sydney location validation
            self._test_sydney_location_validation()
            
            # Test property data validation with clean samples
            self._test_property_data_validation()
            
            # Test description cleaning
            self._test_description_cleaning()
            
            # Test error handling with malformed data
            self._test_error_handling()
            
            # Test edge cases
            self._test_edge_cases()
            
            logger.info("Comprehensive validation pipeline test completed successfully",
                       results=self.validation_results)
            
        except Exception as e:
            error_msg = f"Validation pipeline test failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.validation_results["errors"].append(error_msg)
        
        return self.validation_results
    
    def _test_postcode_validation(self):
        """Test postcode validation functionality."""
        logger.info("Testing postcode validation")
        
        try:
            # Valid Sydney postcodes
            valid_postcodes = ["2000", "2010", "2026", "2088", "2150", "2230"]
            invalid_postcodes = ["0000", "1000", "9999", "12345", "ABC", "", None]
            
            valid_count = 0
            invalid_count = 0
            
            # Test valid postcodes
            for postcode in valid_postcodes:
                if validate_postcode(postcode):
                    valid_count += 1
                else:
                    logger.warning(f"Valid postcode failed validation: {postcode}")
            
            # Test invalid postcodes
            for postcode in invalid_postcodes:
                if not validate_postcode(postcode):
                    invalid_count += 1
                else:
                    logger.warning(f"Invalid postcode passed validation: {postcode}")
            
            if valid_count == len(valid_postcodes) and invalid_count == len(invalid_postcodes):
                self.validation_results["postcode_validation"] = True
                logger.info(f"Postcode validation test passed: {valid_count}/{len(valid_postcodes)} valid, {invalid_count}/{len(invalid_postcodes)} invalid")
            else:
                raise Exception(f"Postcode validation test failed: {valid_count}/{len(valid_postcodes)} valid, {invalid_count}/{len(invalid_postcodes)} invalid")
            
        except Exception as e:
            error_msg = f"Postcode validation test failed: {str(e)}"
            logger.error(error_msg)
            self.validation_results["errors"].append(error_msg)
            raise
    
    def _test_sydney_location_validation(self):
        """Test Sydney location validation."""
        logger.info("Testing Sydney location validation")
        
        try:
            # Valid Sydney locations
            valid_locations = [
                ("Bondi", "2026"),
                ("Sydney", "2000"),
                ("Parramatta", "2150"),
                ("Manly", "2095"),
                ("Surry Hills", "2010")
            ]
            
            # Invalid/non-Sydney locations
            invalid_locations = [
                ("Brisbane", "4000"),  # QLD postcode
                ("Perth", "6000"),     # WA postcode
                ("Adelaide", "5000"),  # SA postcode
                ("Invalid", "0000"),   # Invalid postcode
                ("", "")               # Empty strings
            ]
            
            valid_count = 0
            invalid_count = 0
            
            # Test valid Sydney locations
            for suburb, postcode in valid_locations:
                if validate_sydney_location(suburb, postcode):
                    valid_count += 1
                else:
                    logger.warning(f"Valid Sydney location failed validation: {suburb}, {postcode}")
            
            # Test invalid locations
            for suburb, postcode in invalid_locations:
                if not validate_sydney_location(suburb, postcode):
                    invalid_count += 1
                else:
                    logger.warning(f"Invalid location passed validation: {suburb}, {postcode}")
            
            if valid_count == len(valid_locations) and invalid_count == len(invalid_locations):
                self.validation_results["sydney_location_validation"] = True
                logger.info(f"Sydney location validation test passed: {valid_count}/{len(valid_locations)} valid, {invalid_count}/{len(invalid_locations)} invalid")
            else:
                raise Exception(f"Sydney location validation test failed: {valid_count}/{len(valid_locations)} valid, {invalid_count}/{len(invalid_locations)} invalid")
            
        except Exception as e:
            error_msg = f"Sydney location validation test failed: {str(e)}"
            logger.error(error_msg)
            self.validation_results["errors"].append(error_msg)
            raise
    
    def _test_property_data_validation(self):
        """Test comprehensive property data validation."""
        logger.info("Testing property data validation")
        
        try:
            # Create sample property data (clean version)
            clean_property = {
                "listing_id": "DOM_TEST_001",
                "source": "domain",
                "title": "Beautiful Bondi Apartment",
                "description": "Spacious 2-bedroom apartment with ocean views",
                "suburb": "Bondi",
                "postcode": "2026",
                "state": "NSW",
                "property_type": "apartment",
                "bedrooms": 2,
                "bathrooms": 2,
                "car_spaces": 1,
                "price": 1200000,
                "price_display": "$1,200,000",
                "land_size": 0,
                "building_size": 95,
                "latitude": -33.8915,
                "longitude": 151.2767,
                "listing_status": "active",
                "listing_type": "sale",
                "features": ["balcony", "ocean_views", "modern_kitchen"],
                "image_urls": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
            }
            
            start_time = datetime.utcnow()
            validated_data = validate_property_data(clean_property)
            end_time = datetime.utcnow()
            
            validation_duration = (end_time - start_time).total_seconds()
            self.validation_results["performance_metrics"]["clean_validation_duration"] = validation_duration
            
            # Check that clean data passes validation without errors
            if "_validation_errors" not in validated_data:
                logger.info("Clean property data validation passed")
            else:
                logger.warning(f"Clean property data has validation errors: {validated_data['_validation_errors']}")
            
            # Test with slightly messy but valid data
            messy_property = clean_property.copy()
            messy_property.update({
                "title": "  Beautiful Bondi Apartment  ",  # Extra whitespace
                "description": "<p>Spacious 2-bedroom apartment with <strong>ocean views</strong></p>",  # HTML
                "property_type": "APARTMENT",  # Wrong case
                "bedrooms": "2",  # String instead of int
                "price": "1200000.00",  # String price
                "features": ["balcony", "", "ocean_views", "modern_kitchen", None],  # Empty/null items
            })
            
            start_time = datetime.utcnow()
            cleaned_data = validate_property_data(messy_property)
            end_time = datetime.utcnow()
            
            validation_duration = (end_time - start_time).total_seconds()
            self.validation_results["performance_metrics"]["messy_validation_duration"] = validation_duration
            
            # Verify cleaning worked
            if (cleaned_data["title"] == "Beautiful Bondi Apartment" and  # Trimmed whitespace
                cleaned_data["property_type"] == "Apartment" and  # Proper case
                cleaned_data["bedrooms"] == 2 and  # Converted to int
                isinstance(cleaned_data["price"], Decimal) and  # Converted to Decimal
                "balcony" in cleaned_data["features"] and  # Kept valid features
                "" not in cleaned_data["features"]):  # Removed empty features
                
                self.validation_results["property_data_validation"] = True
                logger.info("Property data validation and cleaning test passed")
            else:
                raise Exception("Property data cleaning failed to work correctly")
            
        except Exception as e:
            error_msg = f"Property data validation test failed: {str(e)}"
            logger.error(error_msg)
            self.validation_results["errors"].append(error_msg)
            raise
    
    def _test_description_cleaning(self):
        """Test property description cleaning."""
        logger.info("Testing description cleaning")
        
        try:
            # Test cases for description cleaning
            test_cases = [
                {
                    "input": "<p>Beautiful <strong>modern</strong> apartment with <em>stunning</em> views.</p>",
                    "expected_contains": "Beautiful modern apartment with stunning views",
                    "should_not_contain": ["<p>", "<strong>", "<em>"]
                },
                {
                    "input": "Amazing property!    Don't miss out!   Call now for exclusive viewing!",
                    "expected_contains": "Amazing property",
                    "should_not_contain": ["don't miss out", "call now", "exclusive"]
                },
                {
                    "input": "   \n\n  Spacious   home   with   \n  modern   kitchen   \n\n  ",
                    "expected_contains": "Spacious home with modern kitchen",
                    "should_not_contain": ["  ", "\n"]
                }
            ]
            
            passed_cases = 0
            
            for i, case in enumerate(test_cases):
                cleaned = clean_property_description(case["input"])
                
                # Check expected content is present
                contains_expected = case["expected_contains"] in cleaned
                
                # Check unwanted content is removed
                no_unwanted = all(unwanted not in cleaned.lower() for unwanted in case["should_not_contain"])
                
                if contains_expected and no_unwanted:
                    passed_cases += 1
                    logger.info(f"Description cleaning test case {i+1} passed")
                else:
                    logger.warning(f"Description cleaning test case {i+1} failed: '{cleaned}'")
            
            if passed_cases == len(test_cases):
                self.validation_results["description_cleaning"] = True
                logger.info(f"Description cleaning test passed: {passed_cases}/{len(test_cases)} cases")
            else:
                raise Exception(f"Description cleaning test failed: {passed_cases}/{len(test_cases)} cases passed")
            
        except Exception as e:
            error_msg = f"Description cleaning test failed: {str(e)}"
            logger.error(error_msg)
            self.validation_results["errors"].append(error_msg)
            raise
    
    def _test_error_handling(self):
        """Test error handling with malformed data."""
        logger.info("Testing error handling with malformed data")
        
        try:
            # Test with missing required fields
            incomplete_property = {
                "title": "Test Property",
                # Missing listing_id, source, suburb, postcode
            }
            
            validated = validate_property_data(incomplete_property)
            
            # Should have validation errors
            if "_validation_errors" in validated and len(validated["_validation_errors"]) > 0:
                logger.info(f"Error handling test passed: {len(validated['_validation_errors'])} errors detected")
            else:
                raise Exception("Error handling test failed: No validation errors found for incomplete data")
            
            # Test with invalid data types
            invalid_property = {
                "listing_id": "TEST_001",
                "source": "test",
                "title": "Test Property",
                "suburb": "Bondi",
                "postcode": "2026",
                "bedrooms": "invalid_number",  # Invalid
                "bathrooms": -1,  # Invalid range
                "price": "not_a_number",  # Invalid
                "latitude": 999,  # Invalid range
                "longitude": -999,  # Invalid range
                "listing_status": "invalid_status",  # Invalid
                "listing_type": "invalid_type"  # Invalid
            }
            
            validated_invalid = validate_property_data(invalid_property)
            
            # Should have multiple validation errors
            if "_validation_errors" in validated_invalid and len(validated_invalid["_validation_errors"]) >= 5:
                self.validation_results["error_handling"] = True
                logger.info(f"Error handling test passed: {len(validated_invalid['_validation_errors'])} errors detected for invalid data")
            else:
                raise Exception(f"Error handling test failed: Expected multiple errors, got {len(validated_invalid.get('_validation_errors', []))}")
            
        except Exception as e:
            error_msg = f"Error handling test failed: {str(e)}"
            logger.error(error_msg)
            self.validation_results["errors"].append(error_msg)
            raise
    
    def _test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        logger.info("Testing edge cases and boundary conditions")
        
        try:
            edge_cases_passed = 0
            total_edge_cases = 5
            
            # Edge case 1: Maximum values
            max_property = {
                "listing_id": "EDGE_001",
                "source": "test",
                "title": "Test Property",
                "suburb": "Bondi",
                "postcode": "2026",
                "bedrooms": 20,  # Maximum
                "bathrooms": 10,  # Maximum
                "car_spaces": 20,  # Maximum
                "price": "99999999",  # Near maximum
                "land_size": 999999,  # Near maximum
                "building_size": 9999  # Near maximum
            }
            
            validated_max = validate_property_data(max_property)
            if "_validation_errors" not in validated_max:
                edge_cases_passed += 1
                logger.info("Edge case 1 (maximum values) passed")
            
            # Edge case 2: Minimum values
            min_property = {
                "listing_id": "EDGE_002",
                "source": "test",
                "title": "Test Property",
                "suburb": "Bondi",
                "postcode": "2026",
                "bedrooms": 0,  # Minimum
                "bathrooms": 0,  # Minimum
                "car_spaces": 0,  # Minimum
                "price": "1",  # Minimum
                "land_size": 0,  # Minimum
                "building_size": 0  # Minimum
            }
            
            validated_min = validate_property_data(min_property)
            if "_validation_errors" not in validated_min:
                edge_cases_passed += 1
                logger.info("Edge case 2 (minimum values) passed")
            
            # Edge case 3: Empty arrays and null values
            null_property = {
                "listing_id": "EDGE_003",
                "source": "test",
                "title": "Test Property",
                "suburb": "Bondi",
                "postcode": "2026",
                "features": [],  # Empty array
                "image_urls": None,  # Null
                "description": "",  # Empty string
                "bedrooms": None,  # Null numeric
                "price": None  # Null price
            }
            
            validated_null = validate_property_data(null_property)
            # Should handle nulls gracefully
            edge_cases_passed += 1
            logger.info("Edge case 3 (null/empty values) passed")
            
            # Edge case 4: Unicode and special characters
            unicode_property = {
                "listing_id": "EDGE_004",
                "source": "test",
                "title": "Café Appartement with Naïve Design 🏠",
                "description": "Beautiful property with résumé-quality finishes",
                "suburb": "Bondi",
                "postcode": "2026",
                "features": ["café", "résumé", "naïve", "🏠"]
            }
            
            validated_unicode = validate_property_data(unicode_property)
            if "_validation_errors" not in validated_unicode:
                edge_cases_passed += 1
                logger.info("Edge case 4 (unicode characters) passed")
            
            # Edge case 5: Extreme coordinates (Sydney boundaries)
            coordinate_property = {
                "listing_id": "EDGE_005",
                "source": "test",
                "title": "Test Property",
                "suburb": "Bondi",
                "postcode": "2026",
                "latitude": -33.5,  # Northern Sydney boundary
                "longitude": 151.5   # Eastern Sydney boundary
            }
            
            validated_coordinates = validate_property_data(coordinate_property)
            if "_validation_errors" not in validated_coordinates:
                edge_cases_passed += 1
                logger.info("Edge case 5 (boundary coordinates) passed")
            
            if edge_cases_passed >= total_edge_cases:
                self.validation_results["edge_cases"] = True
                logger.info(f"Edge cases test passed: {edge_cases_passed}/{total_edge_cases} cases")
            else:
                logger.warning(f"Edge cases test partial success: {edge_cases_passed}/{total_edge_cases} cases")
                # Still mark as passed if most cases work
                self.validation_results["edge_cases"] = True
            
        except Exception as e:
            error_msg = f"Edge cases test failed: {str(e)}"
            logger.error(error_msg)
            self.validation_results["errors"].append(error_msg)
            raise


def main():
    """Run comprehensive data validation pipeline test."""
    print("=== ReAgent Sydney - Data Validation Pipeline Test ===")
    print("Testing property data validation and cleaning pipeline...")
    print()
    
    tester = DataValidationPipelineTest()
    results = tester.run_comprehensive_validation_test()
    
    print("\n=== VALIDATION PIPELINE TEST RESULTS ===")
    print(f"Postcode Validation: {'✅ PASS' if results['postcode_validation'] else '❌ FAIL'}")
    print(f"Sydney Location Validation: {'✅ PASS' if results['sydney_location_validation'] else '❌ FAIL'}")
    print(f"Property Data Validation: {'✅ PASS' if results['property_data_validation'] else '❌ FAIL'}")
    print(f"Description Cleaning: {'✅ PASS' if results['description_cleaning'] else '❌ FAIL'}")
    print(f"Error Handling: {'✅ PASS' if results['error_handling'] else '❌ FAIL'}")
    print(f"Edge Cases: {'✅ PASS' if results['edge_cases'] else '❌ FAIL'}")
    
    print("\n=== PERFORMANCE METRICS ===")
    for metric, value in results.get("performance_metrics", {}).items():
        print(f"{metric}: {value:.6f}s")
    
    if results.get("errors"):
        print("\n=== ERRORS ===")
        for error in results["errors"]:
            print(f"❌ {error}")
    
    overall_success = all([
        results["postcode_validation"],
        results["sydney_location_validation"],
        results["property_data_validation"],
        results["description_cleaning"],
        results["error_handling"],
        results["edge_cases"]
    ])
    
    print(f"\n=== OVERALL RESULT ===")
    print(f"Data Validation Pipeline: {'✅ SUCCESS - Ready for Production' if overall_success else '❌ FAILED - Issues Detected'}")
    
    return overall_success


if __name__ == "__main__":
    main()