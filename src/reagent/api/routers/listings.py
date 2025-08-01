"""
API router for listing-related endpoints.
"""

from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class Listing(BaseModel):
    id: str
    address: str
    suburb: str
    postcode: str
    price: float
    bedrooms: int
    bathrooms: int
    car_spaces: int

@router.get("/", response_model=List[Listing])
async def search_listings(suburb: str = None, postcode: str = None, min_bedrooms: int = 0):
    """Search for property listings."""
    # In a real application, this would query the database.
    # For now, we'll return a static list.
    return [
        {
            "id": "123",
            "address": "123 Fake St",
            "suburb": "Sydney",
            "postcode": "2000",
            "price": 1000000.0,
            "bedrooms": 2,
            "bathrooms": 1,
            "car_spaces": 1
        }
    ]

@router.get("/{listing_id}", response_model=Listing)
async def get_listing(listing_id: str):
    """Get a specific listing by ID."""
    if listing_id == "123":
        return {
            "id": "123",
            "address": "123 Fake St",
            "suburb": "Sydney",
            "postcode": "2000",
            "price": 1000000.0,
            "bedrooms": 2,
            "bathrooms": 1,
            "car_spaces": 1
        }
    raise HTTPException(status_code=404, detail="Listing not found")
