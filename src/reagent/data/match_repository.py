"""
ReAgent - Match Repository

This module provides a repository pattern for managing property match data
in the primary database.
"""

from datetime import datetime
from typing import List, Optional, Any
from uuid import UUID

from sqlalchemy import select, and_, update
from sqlalchemy.orm import selectinload
import structlog

from reagent.core.database.dependencies import get_db_session
from reagent.data.models.buyer_models import PropertyMatch


class MatchRepository:
    """Manages storage and retrieval of property matches."""

    def __init__(self):
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def store_buyer_matches(self, buyer_id: str, matches: List[Any]) -> Dict[str, Any]:
        """Store property matches for a buyer in the database."""
        try:
            async with get_db_session() as session:
                # Supersede existing "new" matches for this buyer
                await session.execute(
                    update(PropertyMatch)
                    .where(and_(PropertyMatch.buyer_id == buyer_id, PropertyMatch.status == "new"))
                    .values(status="superseded")
                )

                # Create new match records
                new_matches = [
                    PropertyMatch(
                        buyer_id=UUID(buyer_id),
                        property_id=UUID(match.property_id),
                        match_score=match.match_score,
                        match_rank=match.match_rank,
                        match_reasons=match.match_reasons,
                        match_concerns=match.match_concerns,
                        match_explanation=match.match_explanation,
                        status="new",
                        first_presented_date=datetime.utcnow(),
                        price_assessment=match.price_assessment,
                        estimated_value=match.estimated_value,
                        scoring_details=match.scoring_details,
                    )
                    for match in matches
                ]

                if new_matches:
                    session.add_all(new_matches)
                    await session.commit()

                self.logger.info("Stored matches for buyer", buyer_id=buyer_id, count=len(new_matches))
                return {"status": "success", "matches_stored": len(new_matches), "buyer_id": buyer_id}

        except Exception as e:
            self.logger.error("Failed to store matches for buyer", buyer_id=buyer_id, error=str(e))
            return {"status": "failed", "error": str(e), "matches_stored": 0}

    async def get_buyer_matches(
        self, buyer_id: str, status: Optional[str] = None, limit: int = 20
    ) -> List[PropertyMatch]:
        """Retrieve stored matches for a buyer."""
        try:
            async with get_db_session() as session:
                query = (
                    select(PropertyMatch)
                    .options(selectinload(PropertyMatch.property), selectinload(PropertyMatch.buyer))
                    .where(PropertyMatch.buyer_id == buyer_id)
                )

                if status:
                    query = query.where(PropertyMatch.status == status)

                query = query.order_by(PropertyMatch.match_rank.asc(), PropertyMatch.match_score.desc()).limit(limit)

                result = await session.execute(query)
                return result.scalars().all()
        except Exception as e:
            self.logger.error("Failed to get matches for buyer", buyer_id=buyer_id, error=str(e))
            return []

    async def update_match_status(self, match_id: str, status: str, feedback: Optional[str] = None) -> bool:
        """Update match status and feedback."""
        try:
            async with get_db_session() as session:
                update_values = {"status": status, "last_interaction_date": datetime.utcnow()}
                if feedback:
                    update_values["buyer_feedback"] = feedback

                await session.execute(
                    update(PropertyMatch).where(PropertyMatch.id == match_id).values(**update_values)
                )
                await session.commit()
                return True
        except Exception as e:
            self.logger.error("Failed to update match", match_id=match_id, error=str(e))
            return False

# Global repository instance
match_repository = MatchRepository()

# Convenience function
async def store_buyer_matches(buyer_id: str, matches: List[Any]) -> Dict[str, Any]:
    """Store buyer matches in database."""
    return await match_repository.store_buyer_matches(buyer_id, matches)
