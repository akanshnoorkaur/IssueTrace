from __future__ import annotations
"""Tests for the AI service layer."""

import pytest
from app.services.ai_service import AIService, AIServiceUnavailableError


class TestAIServiceInitialization:
    """Test AI service initialization with and without API key."""
    
    def test_unavailable_without_key(self):
        """Service should be unavailable without API key."""
        ai = AIService(api_key=None)
        assert ai.available is False
    
    def test_unavailable_with_empty_key(self):
        """Service should be unavailable with empty string key."""
        ai = AIService(api_key="")
        assert ai.available is False
    
    def test_model_name_stored(self):
        """Model name should be stored correctly."""
        ai = AIService(api_key=None, model="test-model")
        assert ai.model_name == "test-model"
    
    def test_default_model(self):
        """Default model should be gemini-3.8-flash."""
        ai = AIService(api_key=None)
        assert ai.model_name == "gemini-3.8-flash"


class TestAIServiceGenerate:
    """Test AI service generation methods."""
    
    @pytest.mark.asyncio
    async def test_generate_returns_none_when_unavailable(self):
        """generate() should return None when service is unavailable."""
        ai = AIService(api_key=None)
        result = await ai.generate("test prompt")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_structured_returns_none_when_unavailable(self):
        """generate_structured() should return None when service is unavailable."""
        from pydantic import BaseModel
        
        class TestSchema(BaseModel):
            value: str
        
        ai = AIService(api_key=None)
        result = await ai.generate_structured(
            prompt="test", response_schema=TestSchema
        )
        assert result is None
