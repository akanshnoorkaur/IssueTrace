from __future__ import annotations
"""
FastAPI Dependency Injection

Provides shared service instances to API route handlers.
"""

from app.config import get_settings, Settings
from app.services.ai_service import AIService
from app.services.database_service import DatabaseService


def get_ai_service() -> AIService:
    """Get the AI service instance."""
    settings = get_settings()
    return AIService(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )


def get_database_service() -> DatabaseService:
    """Get the database service instance."""
    return DatabaseService()
