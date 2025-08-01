"""
ReAgent - Monitoring Service

This service provides performance and satisfaction metrics for the system.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Any

from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
import structlog

from reagent.core.database.dependencies import get_db_session
from reagent.data.models.buyer_models import PropertyMatch


class MonitoringService:
    """Monitors matching performance and provides metrics."""

    def __init__(self):
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def get_matching_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get matching performance metrics."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            async with get_db_session() as session:
                # Total matches
                total_matches_result = await session.execute(
                    select(func.count(PropertyMatch.id)).where(PropertyMatch.created_at >= cutoff_date)
                )
                total_matches = total_matches_result.scalar() or 0

                # Engagement metrics
                engagement_query = select(
                    func.count(PropertyMatch.id.distinct()).label("total_matches"),
                    func.count(func.nullif(PropertyMatch.buyer_feedback, None)).label("feedback_count"),
                    func.avg(PropertyMatch.match_score).label("avg_score"),
                ).where(PropertyMatch.created_at >= cutoff_date)
                engagement_data = (await session.execute(engagement_query)).first()

                # Status distribution
                status_query = (
                    select(PropertyMatch.status, func.count(PropertyMatch.id))
                    .where(PropertyMatch.created_at >= cutoff_date)
                    .group_by(PropertyMatch.status)
                )
                status_result = await session.execute(status_query)
                status_distribution = {row[0]: row[1] for row in status_result}

                feedback_count = engagement_data.feedback_count or 0
                avg_score = engagement_data.avg_score or 0
                
                return {
                    "period_days": days,
                    "total_matches": total_matches,
                    "avg_match_score": float(avg_score),
                    "feedback_rate": (feedback_count / max(total_matches, 1)) * 100,
                    "status_distribution": status_distribution,
                    "engagement_metrics": {
                        "interested_rate": (status_distribution.get("interested", 0) / max(total_matches, 1)) * 100,
                        "contacted_rate": (status_distribution.get("contacted", 0) / max(total_matches, 1)) * 100,
                        "not_interested_rate": (status_distribution.get("not_interested", 0) / max(total_matches, 1)) * 100,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
        except Exception as e:
            self.logger.error("Failed to get matching metrics", error=str(e))
            return {"error": str(e)}

    async def get_buyer_satisfaction_metrics(self, buyer_id: Optional[str] = None) -> Dict[str, Any]:
        """Get buyer satisfaction metrics based on feedback."""
        try:
            async with get_db_session() as session:
                query = select(PropertyMatch).where(
                    and_(
                        PropertyMatch.created_at >= datetime.utcnow() - timedelta(days=30),
                        PropertyMatch.buyer_feedback.isnot(None),
                    )
                )
                if buyer_id:
                    query = query.where(PropertyMatch.buyer_id == buyer_id)

                result = await session.execute(query)
                matches_with_feedback = result.scalars().all()

                if not matches_with_feedback:
                    return {"message": "No feedback data available"}

                # Simple sentiment analysis
                positive_words = {"love", "perfect", "interested", "great", "excellent"}
                negative_words = {"no", "not interested", "pass", "terrible", "bad"}
                
                positive_feedback = 0
                negative_feedback = 0

                for match in matches_with_feedback:
                    feedback = (match.buyer_feedback or "").lower()
                    if any(word in feedback for word in positive_words):
                        positive_feedback += 1
                    elif any(word in feedback for word in negative_words):
                        negative_feedback += 1
                
                total_feedback = len(matches_with_feedback)
                neutral_feedback = total_feedback - positive_feedback - negative_feedback
                avg_score = sum(m.match_score for m in matches_with_feedback) / total_feedback

                return {
                    "total_feedback": total_feedback,
                    "positive_feedback": positive_feedback,
                    "neutral_feedback": neutral_feedback,
                    "negative_feedback": negative_feedback,
                    "satisfaction_rate": (positive_feedback / total_feedback) * 100,
                    "avg_match_score_on_feedback": float(avg_score),
                    "buyer_id": buyer_id,
                    "timestamp": datetime.utcnow().isoformat(),
                }
        except Exception as e:
            self.logger.error("Failed to get satisfaction metrics", error=str(e))
            return {"error": str(e)}

# Global service instance
monitoring_service = MonitoringService()

# Convenience function
async def get_matching_performance_metrics(days: int = 7) -> Dict[str, Any]:
    """Get matching performance metrics."""
    return await monitoring_service.get_matching_metrics(days)
