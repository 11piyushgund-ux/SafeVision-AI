"""
SafeVision AI — LLM Provider Interface (Phase 9)

Abstract base class for LLM providers.
All providers (Gemini, Ollama) implement this interface.
The orchestrator uses only this interface — never provider-specific code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMRequest:
    """Normalized request to an LLM provider."""

    system_prompt: str
    user_prompt: str
    temperature: float = 0.3
    max_output_tokens: int = 2048
    timeout_seconds: int = 60
    # Optional image bytes for multimodal providers (Phase 14).
    # Providers that don't support images safely ignore this field.
    images: list[bytes] = field(default_factory=list)


@dataclass
class LLMResponse:
    """Normalized response from an LLM provider."""

    content: str
    provider: str           # "gemini" | "ollama"
    model: str              # Actual model used
    success: bool = True
    error: str | None = None
    # Generation metadata
    metadata: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """
    Abstract LLM provider interface.

    All providers must implement generate() and health_check().
    The orchestrator only depends on this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name: 'gemini' or 'ollama'."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Currently configured model name."""

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate a completion from the LLM.

        Args:
            request: Normalized LLM request.

        Returns:
            LLMResponse with content on success, error on failure.
            Must NEVER raise — return LLMResponse(success=False) instead.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the provider is available and configured.

        Returns True if the provider can accept requests.
        """
