"""
SafeVision AI — OpenRouter LLM Provider (Phase 14)

Uses the OpenRouter API (OpenAI-compatible chat completions) for multimodal
AI safety reasoning via Gemma 4.

Configuration:
  OPENROUTER_API_KEY — required, read from environment/config
  OPENROUTER_MODEL — model name (default: google/gemma-4-26b-a4b-it:free)
  OPENROUTER_BASE_URL — API base (default: https://openrouter.ai/api/v1)

Supports multimodal input: text + images (base64 JPEG).

The API key is never logged, returned, or exposed.
"""

from __future__ import annotations

import base64
import json

import httpx
import structlog

from app.config import get_settings
from app.services.llm import LLMProvider, LLMRequest, LLMResponse

log = structlog.get_logger()


class OpenRouterProvider(LLMProvider):
    """OpenRouter multimodal LLM provider (OpenAI-compatible chat completions)."""

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def model_name(self) -> str:
        return get_settings().openrouter_model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate via OpenRouter Chat Completions API.

        Supports multimodal input when request.images is non-empty.
        Returns LLMResponse — never raises.
        """
        settings = get_settings()

        if not settings.openrouter_api_key:
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.model_name,
                success=False,
                error="OPENROUTER_API_KEY not configured",
            )

        url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"

        # Build user content: text-only or multimodal
        user_content = self._build_user_content(request)

        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://safevision.ai",
            "X-Title": "SafeVision AI",
        }

        try:
            with httpx.Client(timeout=request.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)

            if resp.status_code == 401:
                return LLMResponse(
                    content="",
                    provider=self.name,
                    model=settings.openrouter_model,
                    success=False,
                    error="OpenRouter authentication failed — check API key configuration",
                )

            if resp.status_code == 429:
                return LLMResponse(
                    content="",
                    provider=self.name,
                    model=settings.openrouter_model,
                    success=False,
                    error="OpenRouter rate limit exceeded",
                )

            if resp.status_code != 200:
                # Sanitize error — never include auth details
                error_text = resp.text[:300] if resp.text else "Unknown error"
                return LLMResponse(
                    content="",
                    provider=self.name,
                    model=settings.openrouter_model,
                    success=False,
                    error=f"OpenRouter HTTP {resp.status_code}: {error_text}",
                )

            try:
                data = resp.json()
            except (json.JSONDecodeError, ValueError):
                return LLMResponse(
                    content="",
                    provider=self.name,
                    model=settings.openrouter_model,
                    success=False,
                    error="OpenRouter returned malformed JSON",
                )

            # Extract content from OpenAI-compatible response
            choices = data.get("choices", [])
            if not choices:
                return LLMResponse(
                    content="",
                    provider=self.name,
                    model=settings.openrouter_model,
                    success=False,
                    error="OpenRouter returned no choices",
                )

            content = choices[0].get("message", {}).get("content", "")
            actual_model = data.get("model", settings.openrouter_model)

            log.info(
                "openrouter_generation_complete",
                model=actual_model,
                content_len=len(content),
                multimodal=bool(request.images),
            )

            return LLMResponse(
                content=content,
                provider=self.name,
                model=actual_model,
                success=True,
                metadata={
                    "content_length": len(content),
                    "multimodal": bool(request.images),
                    "usage": data.get("usage"),
                },
            )

        except httpx.TimeoutException:
            log.error("openrouter_timeout", model=settings.openrouter_model)
            return LLMResponse(
                content="",
                provider=self.name,
                model=settings.openrouter_model,
                success=False,
                error=f"OpenRouter request timed out after {request.timeout_seconds}s",
            )

        except httpx.ConnectError:
            log.error("openrouter_unavailable", base_url=settings.openrouter_base_url)
            return LLMResponse(
                content="",
                provider=self.name,
                model=settings.openrouter_model,
                success=False,
                error="OpenRouter API unreachable",
            )

        except Exception as e:
            log.error("openrouter_generation_failed", error=str(e))
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.model_name,
                success=False,
                error=f"OpenRouter error: {e}",
            )

    def health_check(self) -> bool:
        """Check if OpenRouter is configured with an API key."""
        settings = get_settings()
        return bool(settings.openrouter_api_key)

    @staticmethod
    def _build_user_content(request: LLMRequest) -> str | list[dict]:
        """
        Build the user content for the chat message.

        Returns a plain string for text-only requests, or a multimodal
        content array with image_url entries for multimodal requests.
        """
        if not request.images:
            return request.user_prompt

        # Multimodal: content array with text + images
        content: list[dict] = [
            {"type": "text", "text": request.user_prompt},
        ]

        for image_bytes in request.images:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                },
            })

        return content
