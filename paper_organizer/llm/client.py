"""LLM client wrapper around litellm for paper-organizer.

Supports two modes:
  shared — route through the paper-organizer proxy with a virtual key
  own     — call the provider directly with the user's own API key
"""

from __future__ import annotations

from typing import Any

import litellm

from paper_organizer.config import AppConfig, LLMMode, get_config, get_secret

# Provider -> base URL map for direct-API calls in "own" mode
_PROVIDER_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "openrouter": "https://openrouter.ai/api/v1",
}


def get_llm_client_kwargs(config: AppConfig) -> dict[str, Any]:
    """Return kwargs suitable for litellm.completion() / litellm.acompletion().

    Caller is responsible for merging these into their completion call, e.g.::

        kwargs = get_llm_client_kwargs(config)
        litellm.acompletion(model=model, messages=messages, **kwargs)
    """
    if config.llm.mode == LLMMode.SHARED:
        token = config.llm.shared_token or get_secret("shared_token")
        return {
            "api_base": config.llm.shared_endpoint.rstrip("/") + "/v1",
            "api_key": token,
        }

    # own mode — pick base_url from provider map
    provider = config.llm.provider.lower()
    base_url = _PROVIDER_BASE_URLS.get(provider, _PROVIDER_BASE_URLS["openai"])
    api_key = config.llm.api_key or get_secret(f"{provider}_api_key")

    kwargs: dict[str, Any] = {
        "api_base": base_url,
        "api_key": api_key,
    }

    # OpenRouter requires an extra header
    if provider == "openrouter":
        kwargs["extra_headers"] = {
            "HTTP-Referer": "https://github.com/paper-organizer",
            "X-Title": "paper-organizer",
        }

    return kwargs


def _resolve_model(model_alias: str, config: AppConfig) -> str:
    """Resolve 'fast' / 'smart' aliases to actual model strings."""
    if model_alias == "fast":
        return config.llm.fast_model
    if model_alias == "smart":
        return config.llm.smart_model
    return model_alias


async def chat(
    messages: list[dict[str, str]],
    model: str = "fast",
    config: AppConfig | None = None,
    **kwargs: Any,
) -> str:
    """Single async LLM call that returns the assistant content string.

    Args:
        messages: OpenAI-format message list, e.g. [{"role": "user", "content": "..."}].
        model:    "fast" | "smart" | any literal litellm model string.
        config:   AppConfig instance; loads from disk if None.
        **kwargs: Extra args forwarded to litellm.acompletion (temperature, max_tokens, …).

    Returns:
        The assistant's text content.

    Raises:
        litellm.exceptions.AuthenticationError: Bad API key.
        litellm.exceptions.BadRequestError: Malformed request.
        Exception: Any other litellm / network error.
    """
    if config is None:
        config = get_config()

    resolved_model = _resolve_model(model, config)
    client_kwargs = get_llm_client_kwargs(config)

    response = await litellm.acompletion(
        model=resolved_model,
        messages=messages,
        **client_kwargs,
        **kwargs,
    )

    content: str = response.choices[0].message.content or ""
    return content


def chat_sync(
    messages: list[dict[str, str]],
    model: str = "fast",
    config: AppConfig | None = None,
    **kwargs: Any,
) -> str:
    """Synchronous wrapper around :func:`chat` for non-async call sites."""
    import asyncio

    return asyncio.run(chat(messages, model=model, config=config, **kwargs))
