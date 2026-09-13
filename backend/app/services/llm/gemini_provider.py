"""
SafeVision AI — Gemini LLM Provider (Phase 9)

Uses the Google Generative AI SDK (google-genai) to call Gemini models.

Configuration:
  GEMINI_API_KEY — required, read from environment/config
  GEMINI_MODEL — model name (default: gemini-2.0-flash)

The API key is never logged, returned, or exposed.
"""

from __future__ import annotations

import structlog

from app.config import get_settings
from app.services.llm import LLMProvider, LLMRequest, LLMResponse

log = structlog.get_logger()


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider."""

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return get_settings().gemini_model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate via Google Gemini API.

        Returns LLMResponse — never raises.
        """
        settings = get_settings()

        if not settings.gemini_api_key:
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.model_name,
                success=False,
                error="GEMINI_API_KEY not configured",
            )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.gemini_api_key)

            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=request.user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=request.system_prompt,
                    temperature=request.temperature,
                    max_output_tokens=request.max_output_tokens,
                ),
            )

            content = response.text or ""

            log.info(
                "gemini_generation_complete",
                model=settings.gemini_model,
                content_len=len(content),
            )

            return LLMResponse(
                content=content,
                provider=self.name,
                model=settings.gemini_model,
                success=True,
                metadata={
                    "content_length": len(content),
                },
            )

        except Exception as e:
            log.error("gemini_generation_failed", error=str(e))
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.model_name,
                success=False,
                error=f"Gemini API error: {e}",
            )

    def health_check(self) -> bool:
        """Check if Gemini is configured with an API key."""
        settings = get_settings()
        return bool(settings.gemini_api_key)
