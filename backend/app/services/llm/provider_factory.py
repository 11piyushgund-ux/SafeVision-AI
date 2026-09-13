"""
SafeVision AI — LLM Provider Factory (Phase 9)

Creates and manages LLM providers based on configuration.
Supports provider switching and fallback mode.

Configuration:
  LLM_PROVIDER — which provider to use (gemini | ollama)
  LLM_MODE — primary_only | fallback
  LLM_PRIMARY_PROVIDER — primary provider name
  LLM_FALLBACK_PROVIDER — fallback provider name
"""

from __future__ import annotations

import dataclasses
import structlog

from app.config import get_settings
from app.services.llm import LLMProvider, LLMRequest, LLMResponse
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.ollama_provider import OllamaProvider
from app.services.llm.openrouter_provider import OpenRouterProvider
from app.services.llm.prompts import SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT

log = structlog.get_logger()

PRIMARY_TIMEOUT_SECONDS = 240  # 4 minutes — Gemma 4 multimodal reports take 50-90s

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "openrouter": OpenRouterProvider,
}


class ProviderError(Exception):
    """Raised when no provider can fulfill a request."""


def get_provider(name: str | None = None) -> LLMProvider:
    """
    Get a provider instance by name, or the configured default.

    Args:
        name: Provider name ('gemini' or 'ollama'). If None, uses config.

    Returns:
        LLMProvider instance.

    Raises:
        ProviderError: If the provider name is invalid.
    """
    if name is None:
        name = get_settings().llm_provider

    name = name.lower().strip()
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        msg = (
            f"Unknown LLM provider: '{name}'. "
            f"Supported: {', '.join(_PROVIDERS.keys())}"
        )
        raise ProviderError(msg)

    return provider_cls()


def generate_with_fallback(request: LLMRequest) -> LLMResponse:
    """
    Generate using configured provider(s) with optional fallback (Phase 14c).

    Primary provider executes with 5-minute timeout (Gemma multimodal needs 50-90s).
    If primary fails and fallback mode is active:
      - Ollama fallback receives request with images stripped (text-only)
      - Ollama fallback uses SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT
      - Ollama fallback retains original timeout (local inference)
      - Response metadata records attempted_provider, fallback_used, fallback_reason
    """
    settings = get_settings()
    mode = settings.llm_mode.lower()

    # Determine primary provider
    primary_name = settings.llm_primary_provider

    # Build primary-specific request with 5-minute timeout for Gemma multimodal
    primary_request = dataclasses.replace(
        request,
        timeout_seconds=PRIMARY_TIMEOUT_SECONDS,
    )

    try:
        primary = get_provider(primary_name)
    except ProviderError as e:
        return LLMResponse(
            content="",
            provider=primary_name,
            model="unknown",
            success=False,
            error=str(e),
        )

    # Try primary
    response = primary.generate(primary_request)

    if response.success or mode != "fallback":
        if response.success:
            response.metadata["fallback_used"] = False
            response.metadata["attempted_provider"] = primary_name
        else:
            log.warning(
                "primary_provider_failed",
                provider=primary_name,
                error=response.error,
                mode=mode,
            )
        return response

    # Fallback mode: try secondary
    fallback_name = settings.llm_fallback_provider
    fallback_reason = response.error or "Primary provider failed"
    log.info(
        "provider_fallback",
        primary=primary_name,
        primary_error=response.error,
        fallback=fallback_name,
    )

    # Build text-only fallback request (strip images, sanitize user prompt, text-only system prompt)
    clean_user_prompt = request.user_prompt
    multimodal_note = (
        "EVIDENCE IMAGE: The evidence JPEG captured at the moment of detection is attached.\n"
        "Bounding boxes from YOLO are drawn on the image.\n"
        "Use both the image and the structured data above for your analysis.\n"
        "Provide your structured JSON response."
    )
    text_only_note = (
        "NOTE: Operating in text-only fallback mode. No evidence image is available.\n"
        "Analyze this safety event based on the structured data above only.\n"
        "Provide your structured JSON response."
    )
    if multimodal_note in clean_user_prompt:
        clean_user_prompt = clean_user_prompt.replace(multimodal_note, text_only_note)

    fallback_request = dataclasses.replace(
        request,
        user_prompt=clean_user_prompt,
        images=[],  # strip images — Ollama is text-only
        system_prompt=SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT,
        timeout_seconds=request.timeout_seconds,  # original timeout for local Ollama
    )

    try:
        fallback = get_provider(fallback_name)
    except ProviderError as e:
        return LLMResponse(
            content="",
            provider=fallback_name,
            model="unknown",
            success=False,
            error=f"Fallback provider error: {e}",
            metadata={
                "primary_error": response.error,
                "attempted_provider": primary_name,
                "fallback_used": True,
                "fallback_reason": fallback_reason,
            },
        )

    fallback_response = fallback.generate(fallback_request)
    fallback_response.metadata["attempted_provider"] = primary_name
    fallback_response.metadata["fallback_used"] = True
    fallback_response.metadata["fallback_reason"] = fallback_reason
    fallback_response.metadata["multimodal"] = False
    if not fallback_response.success:
        fallback_response.metadata["primary_error"] = response.error

    return fallback_response

