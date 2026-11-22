from __future__ import annotations
"""
Database Service

Wraps the raw database functions with higher-level business logic.
Acts as the data access layer between API routes and SQLite.
"""

import logging
from typing import Any

from app.database import (
    save_analysis,
    get_analysis,
    get_history,
    get_stats,
)

logger = logging.getLogger(__name__)


class DatabaseService:
    """High-level database operations for the analysis pipeline."""
    
    async def save(self, analysis_id: str, data: dict[str, Any]) -> None:
        """Save a completed analysis."""
        await save_analysis(analysis_id, data)
        logger.info("Analysis saved: %s", analysis_id)
    
    async def get(self, analysis_id: str) -> dict[str, Any] | None:
        """Retrieve an analysis by ID."""
        return await get_analysis(analysis_id)
    
    async def list_history(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List analysis history."""
        return await get_history(limit=limit, offset=offset)
    
    async def get_dashboard_stats(self) -> dict[str, int]:
        """Get dashboard summary statistics."""
        return await get_stats()
