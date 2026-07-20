"""Shared LLM client configuration with Azure-compatible rollback defaults."""

import os
from pathlib import Path

from openai import AzureOpenAI, OpenAI


def _read_api_key(env_name: str, file_env_name: str) -> str | None:
    value = os.getenv(env_name)
    if value:
        return value.strip()

    key_file = os.getenv(file_env_name)
    if key_file:
        return Path(key_file).expanduser().read_text(encoding="utf-8").strip()
    return None


def get_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "azure").strip().lower()


def get_llm_client():
    """Return an OpenAI-compatible client selected by LLM_PROVIDER.

    Existing Azure settings remain the default so rollback only requires removing
    or changing LLM_PROVIDER.
    """
    provider = get_llm_provider()
    if provider == "openrouter":
        api_key = _read_api_key("OPENROUTER_API_KEY", "OPENROUTER_API_KEY_FILE")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY or OPENROUTER_API_KEY_FILE is required")
        return OpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )

    if provider == "azure":
        return AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def get_llm_model(default: str | None = None) -> str | None:
    if get_llm_provider() == "openrouter":
        return os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
    return os.getenv("AZURE_OPENAI_MODEL", default)
