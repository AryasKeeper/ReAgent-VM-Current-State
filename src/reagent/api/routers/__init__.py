"""API Routers for ReAgent Sydney."""

from fastapi import APIRouter
from . import agents, listings, buyers, health

router = APIRouter()

router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(listings.router, prefix="/listings", tags=["listings"])
router.include_router(buyers.router, prefix="/buyers", tags=["buyers"])
router.include_router(health.router, prefix="/health", tags=["health"])

__all__ = ["router"]
