"""
SafeVision AI — Ollama LLM Provider (Phase 9)

Uses the Ollama HTTP API for local model inference.

Configuration:
  OLLAMA_BASE_URL — Ollama server URL (default: http://localhost:11434)
  OLLAMA_MODEL — model name (default: qwen2.5:7b-instruct-q4_K_M)

Lazy invocation — does NOT load or connect to Ollama unless called.
"""

from __future__ import annotations

import json

import httpx
import structlog

from app.config import get_settings
from app.services.llm import LLMProvider, LLMRequest, LLMResponse

log = structlog.get_logger()


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider via HTTP API."""

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return get_settings().ollama_model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate via Ollama HTTP API.

        Returns LLMResponse — never raises.
        """
        settings = get_settings()
        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"

        payload = {
            "model": settings.ollama_model,
            "prompt": request.user_prompt,
            "system": request.system_prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_output_tokens,
            },
        }

        try:
            with httpx.Client(timeout=request.timeout_seconds) as client:
                resp = client.post(url, json=payload)

            if resp.status_code != 200:
                return LLMResponse(
                    content="",
                    provider=self.name,
                    model=settings.ollama_model,
                    success=False,
                    error=(
                        f"Ollama HTTP {resp.status_code}: "
                        f"{resp.text[:200]}"
                    ),
                )

            try:
                data = resp.json()
            except (json.JSONDecodeError, ValueError):
                return LLMResponse(
                    content="",
                    provider=self.name,
                    model=settings.ollama_model,
                    success=False,
                    error="Ollama returned malformed JSON",
                )

            content = data.get("response", "")

            log.info(
                "ollama_generation_complete",
                model=settings.ollama_model,
                content_len=len(content),
            )

            return LLMResponse(
                content=content,
                provider=self.name,
                model=settings.ollama_model,
                success=True,
                metadata={
                    "content_length": len(content),
                    "total_duration": data.get("total_duration"),
                    "eval_count": data.get("eval_count"),
                },
            )

        except httpx.TimeoutException:
            log.error("ollama_timeout", model=settings.ollama_model)
            return LLMResponse(
                content="",
                provider=self.name,
                model=settings.ollama_model,
                success=False,
                error=f"Ollama request timed out after {request.timeout_seconds}s",
            )

        except httpx.ConnectError:
            log.error(
                "ollama_unavailable",
                base_url=settings.ollama_base_url,
            )
            return LLMResponse(
                content="",
                provider=self.name,
                model=settings.ollama_model,
                success=False,
                error=f"Ollama server unavailable at {settings.ollama_base_url}",
            )

        except Exception as e:
            log.error("ollama_generation_failed", error=str(e))
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.model_name,
                success=False,
                error=f"Ollama error: {e}",
            )

    def health_check(self) -> bool:
        """Check if Ollama server is reachable."""
        settings = get_settings()
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(settings.ollama_base_url)
            return resp.status_code == 200
        except Exception:
            return False
