"""Shared, ordered OpenAI-compatible LLM provider configuration.

The default remains Azure for backwards compatibility. Production can opt into a
bounded provider chain with ``LLM_PROVIDER`` plus ``LLM_FALLBACK_PROVIDERS``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import requests
from openai import APIConnectionError, APITimeoutError, AzureOpenAI, OpenAI
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {408, 409, 429}
_SUPPORTED_PROVIDERS = {
    "azure",
    "gemini",
    "cloudflare",
    "openrouter",
    "openrouter_super",
}


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    client_factory: Callable[[], Any]


class LLMChainError(RuntimeError):
    """Raised after every configured provider fails with a retryable error."""


class LLMResponseValidationError(ValueError):
    """Raised when a provider returns unusable structured output."""


class _AzureResponsesCompletions:
    """Adapt Azure's Responses API to the chat-completions shape used here."""

    def __init__(self, base_url: str, api_key: str):
        self._url = f"{base_url.rstrip('/')}/responses"
        self._api_key = api_key
        self._timeout = float(os.getenv("AZURE_OPENAI_TIMEOUT_SECONDS", "120"))
        if self._timeout <= 0:
            raise ValueError("AZURE_OPENAI_TIMEOUT_SECONDS must be greater than zero")

    def create(self, **kwargs):
        payload = {
            "model": kwargs["model"],
            "input": kwargs.get("messages", []),
        }
        if kwargs.get("max_completion_tokens") is not None:
            payload["max_output_tokens"] = kwargs["max_completion_tokens"]

        response = requests.post(
            self._url,
            headers={"api-key": self._api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMResponseValidationError(
                "Azure Responses API returned a non-JSON response"
            ) from exc
        text = data.get("output_text")
        if not isinstance(text, str):
            text = "".join(
                content.get("text", "")
                for output in data.get("output", [])
                if isinstance(output, dict)
                for content in output.get("content", [])
                if isinstance(content, dict) and content.get("type") == "output_text"
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
        )


class _AzureResponsesClient:
    def __init__(self, base_url: str, api_key: str):
        self.chat = SimpleNamespace(
            completions=_AzureResponsesCompletions(base_url, api_key)
        )


class _FallbackCompletions:
    def __init__(self, providers: list[ProviderConfig]):
        self._providers = providers

    def create(self, **kwargs):
        return self._create_with_provider_fallback(None, **kwargs)

    def create_validated(self, validator: Callable[[Any], Any], **kwargs):
        """Return validated content, falling back when a response is malformed."""
        return self._create_with_provider_fallback(validator, **kwargs)

    def _create_with_provider_fallback(self, validator, **kwargs):
        failures: list[str] = []
        for index, provider in enumerate(self._providers):
            request = dict(kwargs)
            request["model"] = provider.model
            try:
                response = provider.client_factory().chat.completions.create(**request)
                return validator(response) if validator is not None else response
            except Exception as exc:
                status = _status_code(exc)
                validation_failed = isinstance(exc, LLMResponseValidationError)
                retryable = validation_failed or _is_retryable(exc)
                failures.append(f"{provider.name}/{provider.model} ({status or type(exc).__name__})")
                logger.warning(
                    "LLM request failed provider=%s model=%s status=%s retryable=%s",
                    provider.name,
                    provider.model,
                    status or "network",
                    retryable,
                )
                if not retryable:
                    raise
                if index + 1 < len(self._providers):
                    next_provider = self._providers[index + 1]
                    logger.info(
                        "Falling back to LLM provider=%s model=%s",
                        next_provider.name,
                        next_provider.model,
                    )
                    continue
                raise LLMChainError(
                    "All configured LLM tiers failed: " + " -> ".join(failures)
                ) from exc

        raise LLMChainError("No LLM providers are configured")


class _FallbackChat:
    def __init__(self, providers: list[ProviderConfig]):
        self.completions = _FallbackCompletions(providers)


class FallbackLLMClient:
    """Small OpenAI-client facade that performs one attempt per configured tier."""

    def __init__(self, providers: list[ProviderConfig]):
        if not providers:
            raise ValueError("At least one LLM provider is required")
        self.providers = tuple(providers)
        self.chat = _FallbackChat(providers)


def _read_api_key(env_name: str, file_env_name: str) -> str | None:
    value = os.getenv(env_name)
    if value:
        return value.strip()

    key_file = os.getenv(file_env_name)
    if key_file:
        value = Path(key_file).expanduser().read_text(encoding="utf-8").strip()
        if value:
            return value
    return None


def _required_api_key(env_name: str, file_env_name: str, provider: str) -> str:
    api_key = _read_api_key(env_name, file_env_name)
    if not api_key:
        raise RuntimeError(f"{env_name} or {file_env_name} is required for {provider}")
    return api_key


def _provider_names() -> list[str]:
    primary = os.getenv("LLM_PROVIDER", "azure").strip().lower()
    fallbacks = [
        name.strip().lower()
        for name in os.getenv("LLM_FALLBACK_PROVIDERS", "").split(",")
        if name.strip()
    ]
    names = [primary, *fallbacks]
    unsupported = [name for name in names if name not in _SUPPORTED_PROVIDERS]
    if unsupported:
        raise ValueError(f"Unsupported LLM provider(s): {', '.join(unsupported)}")
    if len(names) != len(set(names)):
        raise ValueError("LLM provider chain contains duplicate tiers")
    return names


def get_llm_provider() -> str:
    return _provider_names()[0]


def _build_provider(name: str, bounded: bool) -> ProviderConfig:
    max_retries = 0 if bounded else 2

    if name == "gemini":
        key = _required_api_key("GEMINI_API_KEY", "GEMINI_API_KEY_FILE", name)
        base_url = os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        return ProviderConfig(
            name=name,
            model=model,
            client_factory=lambda: OpenAI(
                api_key=key, base_url=base_url, max_retries=max_retries
            ),
        )

    if name == "cloudflare":
        key = _required_api_key(
            "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_TOKEN_FILE", name
        )
        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        if not account_id:
            raise RuntimeError("CLOUDFLARE_ACCOUNT_ID is required for cloudflare")
        base_url = os.getenv("CLOUDFLARE_AI_BASE_URL", "").strip() or (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
        )
        model = os.getenv(
            "CLOUDFLARE_AI_MODEL",
            "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        )
        return ProviderConfig(
            name=name,
            model=model,
            client_factory=lambda: OpenAI(
                api_key=key, base_url=base_url, max_retries=max_retries
            ),
        )

    if name in {"openrouter", "openrouter_super"}:
        key = _required_api_key(
            "OPENROUTER_API_KEY", "OPENROUTER_API_KEY_FILE", name
        )
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        model_env = "OPENROUTER_MODEL" if name == "openrouter" else "OPENROUTER_SUPER_MODEL"
        default_model = (
            "nvidia/nemotron-3-ultra-550b-a55b:free"
            if name == "openrouter"
            else "nvidia/nemotron-3-super-120b-a12b:free"
        )
        model = os.getenv(model_env, default_model)
        return ProviderConfig(
            name=name,
            model=model,
            client_factory=lambda: OpenAI(
                api_key=key, base_url=base_url, max_retries=max_retries
            ),
        )

    api_key = _read_api_key("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_KEY_FILE")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    responses_base_url = os.getenv("AZURE_OPENAI_BASE_URL", "").strip()
    if not api_key or not (responses_base_url or endpoint):
        raise RuntimeError(
            "AZURE_OPENAI_API_KEY or AZURE_OPENAI_API_KEY_FILE, and either "
            "AZURE_OPENAI_BASE_URL or AZURE_OPENAI_ENDPOINT are required for azure"
        )
    model = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o")
    if responses_base_url:
        return ProviderConfig(
            name=name,
            model=model,
            client_factory=lambda: _AzureResponsesClient(responses_base_url, api_key),
        )
    return ProviderConfig(
        name=name,
        model=model,
        client_factory=lambda: AzureOpenAI(
            api_key=api_key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
            azure_endpoint=endpoint,
            max_retries=max_retries,
        ),
    )


def get_llm_client() -> FallbackLLMClient:
    """Return a compatible client with bounded ordered fallback when configured."""
    names = _provider_names()
    bounded = len(names) > 1
    return FallbackLLMClient([_build_provider(name, bounded) for name in names])


def get_llm_model(default: str | None = None) -> str | None:
    """Return the primary model name (calls may transparently use a fallback model)."""
    names = _provider_names()
    if names[0] == "azure" and not os.getenv("AZURE_OPENAI_MODEL") and default is not None:
        return default
    return _build_provider(names[0], bounded=len(names) > 1).model


def _status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _is_retryable(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            APIConnectionError,
            APITimeoutError,
            RequestsConnectionError,
            RequestsTimeout,
            TimeoutError,
            ConnectionError,
        ),
    ):
        return True
    status = _status_code(exc)
    return status in _RETRYABLE_STATUS_CODES or (status is not None and status >= 500)
