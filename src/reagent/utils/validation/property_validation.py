"""
Property data validation utilities for ReAgent Sydney.
"""

import re
from typing import Dict, Any, List, Optional
from decimal import Decimal
from reagent.utils.logging import get_logger


def validate_postcode(postcode: str) -> bool:
    """
    Validate Australian postcode format.
    
    Args:
        postcode: Postcode string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not postcode or not isinstance(postcode, str):
        return False
    
    # Australian postcodes are 4 digits
    if not re.match(r'^\d{4}$', postcode.strip()):
        return False
    
    # Check if it's a valid Australian postcode range (1000-9999 excluding unused ranges)
    postcode_int = int(postcode.strip())
    # Valid Australian postcode ranges by state:
    # NSW: 1000-1999 (limited), 2000-2999 (main Sydney), 3000-3999 (some areas)
    # VIC: 3000-3999, 8000-8999
    # QLD: 4000-4999, 9000-9999
    # etc.
    return 1001 <= postcode_int <= 9998


def validate_property_data(property_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and clean property data.
    
    Args:
        property_data: Raw property data dictionary
        
    Returns:
        Validated and cleaned property data
        
    Raises:
        ValueError: If required fields are missing or invalid
    """
    validated_data = property_data.copy()
    errors = []
    
    # Required fields
    required_fields = ["listing_id", "source", "title", "suburb", "postcode"]
    for field in required_fields:
        if not validated_data.get(field):
            errors.append(f"Missing required field: {field}")
    
    # Clean and validate specific fields
    if "postcode" in validated_data:
        postcode = str(validated_data["postcode"]).strip()
        if not validate_postcode(postcode):
            errors.append(f"Invalid postcode: {postcode}")
        else:
            validated_data["postcode"] = postcode
    
    # Validate numeric fields
    numeric_fields = {
        "bedrooms": (0, 20),
        "bathrooms": (0, 10),
        "car_spaces": (0, 20),
        "land_size": (0, 1000000),  # sq meters
        "building_size": (0, 10000)  # sq meters
    }
    
    for field, (min_val, max_val) in numeric_fields.items():
        if field in validated_data and validated_data[field] is not None:
            try:
                value = int(validated_data[field])
                if not min_val <= value <= max_val:
                    errors.append(f"{field} out of range: {value}")
                else:
                    validated_data[field] = value
            except (ValueError, TypeError):
                errors.append(f"Invalid {field}: {validated_data[field]}")
                validated_data[field] = None
    
    # Validate price
    if "price" in validated_data and validated_data["price"] is not None:
        try:
            price = Decimal(str(validated_data["price"]))
            if price < 0:
                errors.append("Price cannot be negative")
            elif price > Decimal("100000000"):  # 100M limit
                errors.append("Price exceeds maximum limit")
            else:
                validated_data["price"] = price
        except (ValueError, TypeError, Exception):  # Catch all decimal conversion errors
            errors.append(f"Invalid price: {validated_data['price']}")
            validated_data["price"] = None
    
    # Validate coordinates
    if "latitude" in validated_data and validated_data["latitude"] is not None:
        try:
            lat = float(validated_data["latitude"])
            if not -90 <= lat <= 90:
                errors.append(f"Invalid latitude: {lat}")
            else:
                validated_data["latitude"] = lat
        except (ValueError, TypeError):
            errors.append(f"Invalid latitude: {validated_data['latitude']}")
            validated_data["latitude"] = None
    
    if "longitude" in validated_data and validated_data["longitude"] is not None:
        try:
            lng = float(validated_data["longitude"])
            if not -180 <= lng <= 180:
                errors.append(f"Invalid longitude: {lng}")
            else:
                validated_data["longitude"] = lng
        except (ValueError, TypeError):
            errors.append(f"Invalid longitude: {validated_data['longitude']}")
            validated_data["longitude"] = None
    
    # Validate property type
    valid_property_types = {
        "house", "unit", "apartment", "townhouse", "villa", 
        "duplex", "terrace", "studio", "land", "other"
    }
    if "property_type" in validated_data and validated_data["property_type"]:
        prop_type = validated_data["property_type"].lower().strip()
        if prop_type not in valid_property_types:
            logger = get_logger(__name__)
            validated_data["property_type"] = "other"
        else:
            validated_data["property_type"] = prop_type.title()
    
    # Validate listing status
    valid_statuses = {"active", "sold", "withdrawn", "off_market"}
    if "listing_status" in validated_data and validated_data["listing_status"]:
        status = validated_data["listing_status"].lower().strip()
        if status not in valid_statuses:
            errors.append(f"Invalid listing status: {status}")
        else:
            validated_data["listing_status"] = status
    
    # Validate listing type
    valid_types = {"sale", "rent", "auction", "expressions_of_interest"}
    if "listing_type" in validated_data and validated_data["listing_type"]:
        list_type = validated_data["listing_type"].lower().strip()
        if list_type not in valid_types:
            errors.append(f"Invalid listing type: {list_type}")
        else:
            validated_data["listing_type"] = list_type
    
    # Clean string fields
    string_fields = [
        "title", "description", "address_line_1", "address_line_2", 
        "suburb", "state", "country"
    ]
    for field in string_fields:
        if field in validated_data and validated_data[field]:
            validated_data[field] = str(validated_data[field]).strip()
            if len(validated_data[field]) == 0:
                validated_data[field] = None
    
    # Validate arrays
    array_fields = ["features", "image_urls", "floorplan_urls", "video_urls"]
    for field in array_fields:
        if field in validated_data and validated_data[field]:
            if not isinstance(validated_data[field], list):
                validated_data[field] = []
            else:
                # Clean array items
                validated_data[field] = [
                    str(item).strip() for item in validated_data[field] 
                    if item and str(item).strip()
                ]
    
    # Log validation results
    if errors:
        logger.warning(
            "Property data validation errors",
            listing_id=validated_data.get("listing_id"),
            errors=errors
        )
        # For now, we'll return the data with errors noted
        # In production, you might want to raise an exception
        validated_data["_validation_errors"] = errors
    else:
        logger.debug(
            "Property data validated successfully",
            listing_id=validated_data.get("listing_id")
        )
    
    return validated_data


def validate_sydney_location(suburb: str, postcode: str) -> bool:
    """
    Validate that a location is within Sydney metro area.
    
    Args:
        suburb: Suburb name
        postcode: Postcode
        
    Returns:
        True if location is in Sydney metro
    """
    if not validate_postcode(postcode):
        return False
    
    postcode_int = int(postcode.strip())
    
    # Sydney metro postcodes are roughly 2000-2999
    # Plus some outer areas like 1001-1999 and 3000-3999
    sydney_ranges = [
        (1001, 1999),  # Some inner areas (excluding 1000)
        (2000, 2999),  # Main Sydney metro
        (3000, 3999),  # Some outer areas like Blacktown
    ]
    
    return any(start <= postcode_int <= end for start, end in sydney_ranges)


def clean_property_description(description: str) -> str:
    """
    Clean and standardize property description text.
    
    Args:
        description: Raw description text
        
    Returns:
        Cleaned description text
    """
    if not description:
        return ""
    
    # Remove HTML tags
    description = re.sub(r'<[^>]+>', '', description)
    
    # Normalize whitespace first
    description = re.sub(r'\s+', ' ', description).strip()
    
    # Remove common spam phrases (case insensitive, with word boundaries)
    spam_phrases = [
        r"\bcall now\b", r"\bdon't miss out\b", r"\bact fast\b", r"\blimited time\b",
        r"\bexclusive offer\b", r"\bmust sell\b", r"\burgent sale\b", 
        r"\bexclusive viewing\b", r"\bfor exclusive\b"
    ]
    
    for phrase_pattern in spam_phrases:
        description = re.sub(
            phrase_pattern, 
            "", 
            description, 
            flags=re.IGNORECASE
        )
    
    # Clean up multiple spaces and punctuation artifacts
    description = re.sub(r'\s+', ' ', description).strip()
    description = re.sub(r'[.!]\s*[.!]+', '.', description)  # Clean up multiple punctuation
    description = re.sub(r'^\s*[.!,]\s*', '', description)   # Remove leading punctuation
    description = re.sub(r'\s*[.!,]\s*$', '.', description)  # Normalize ending punctuation
    
    return description.strip()