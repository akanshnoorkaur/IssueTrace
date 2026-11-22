from __future__ import annotations
"""
AI Service — Google Gemini Abstraction Layer

This is the single point of contact with the Gemini API.
All AI features go through this service, which provides:
- Graceful degradation when API key is missing
- Structured output via Pydantic models
- Error handling and logging
- Reusable interface for all engines

Uses the official google-genai SDK.
"""

import json
import logging
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AIServiceError(Exception):
    """Raised when the AI service encounters an error."""
    pass


class AIServiceUnavailableError(AIServiceError):
    """Raised when AI features are requested but no API key is configured."""
    pass


class AIService:
    """Reusable AI service layer wrapping Google Gemini.
    
    This class handles:
    - Client initialization (only when API key is present)
    - Graceful degradation (available flag)
    - Structured output with Pydantic validation
    - Error handling and retries
    
    Usage:
        ai = AIService(api_key="...", model="gemini-3.8-flash")
        result = await ai.generate_structured(
            prompt="Extract claims from...",
            system_prompt="You are a claim extractor...",
            response_schema=ClaimExtractionResult,
        )
    """
    
    def __init__(self, api_key: str | None = None, model: str = "gemini-3.8-flash"):
        self.model_name = model
        self.available = api_key is not None and len(api_key) > 0
        self._client = None
        
        if self.available:
            try:
                from google import genai
                self._client = genai.Client(api_key=api_key)
                logger.info("AI Service initialized with model: %s", model)
            except ImportError:
                logger.error("google-genai package not installed")
                self.available = False
            except Exception as e:
                logger.error("Failed to initialize Gemini client: %s", e)
                self.available = False
        else:
            logger.warning(
                "AI Service unavailable: No GEMINI_API_KEY configured. "
                "AI features will be disabled. Set GEMINI_API_KEY in your .env file."
            )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str | None:
        """Generate a free-form text response from Gemini.
        
        Returns None if AI is unavailable.
        """
        if not self.available or not self._client:
            logger.warning("AI generate called but service is unavailable")
            return None
        
        try:
            from google.genai import types
            
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,  # Low temperature for analytical tasks
            )
            
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            
            return response.text
            
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            raise AIServiceError(f"AI generation failed: {e}") from e
    
    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_prompt: str | None = None,
    ) -> T | None:
        """Generate a structured response validated against a Pydantic model.
        
        This uses Gemini's structured output capability:
        1. Sends the prompt with a JSON schema
        2. Gemini returns JSON matching the schema
        3. We validate it with Pydantic
        
        Returns None if AI is unavailable.
        """
        if not self.available or not self._client:
            logger.warning("AI generate_structured called but service is unavailable")
            return None
        
        try:
            from google.genai import types
            
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.2,
            )
            
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            
            # Parse the JSON response
            raw_text = response.text
            if not raw_text:
                logger.warning("Gemini returned empty response")
                return None
            
            # Validate with Pydantic
            parsed = json.loads(raw_text)
            return response_schema.model_validate(parsed)
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini JSON response: %s", e)
            raise AIServiceError(f"Invalid JSON from AI: {e}") from e
        except ValidationError as e:
            logger.error("Gemini response failed Pydantic validation: %s", e)
            raise AIServiceError(f"AI response validation failed: {e}") from e
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            raise AIServiceError(f"AI generation failed: {e}") from e
