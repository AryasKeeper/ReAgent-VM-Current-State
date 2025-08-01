"""
API router for buyer-related endpoints.
"""

from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class Buyer(BaseModel):
    id: str
    name: str
    email: str
    max_price: float
    min_bedrooms: int
    preferred_suburbs: List[str]

@router.get("/", response_model=List[Buyer])
async def list_buyers():
    """List all buyers."""
    # In a real application, this would query the database.
    # For now, we'll return a static list.
    return [
        {
            "id": "456",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "max_price": 1200000.0,
            "min_bedrooms": 2,
            "preferred_suburbs": ["Sydney", "Pyrmont"]
        }
    ]

@router.get("/{buyer_id}", response_model=Buyer)
async def get_buyer(buyer_id: str):
    """Get a specific buyer by ID."""
    if buyer_id == "456":
        return {
            "id": "456",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "max_price": 1200000.0,
            "min_bedrooms": 2,
            "preferred_suburbs": ["Sydney", "Pyrmont"]
        }
    raise HTTPException(status_code=404, detail="Buyer not found")
