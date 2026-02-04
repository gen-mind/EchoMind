"""
LLM provider client for chat completion.

Supports three provider types:
- openai-compatible: Any OpenAI-compatible API (TGI, vLLM, OpenAI, Ollama, etc.)
- anthropic: Anthropic Messages API (streaming, pay-per-token)
- anthropic-token: Claude CLI with Max subscription OAuth token

Provider names are normalized to handle legacy values from database.
"""

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from api.logic.claude_cli_provider import (
    ClaudeCliConfig,
    ClaudeCliError,
    ClaudeCliProvider,
    ClaudeCliTimeoutError,
)
from api.logic.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)

# Provider normalization map (legacy values -> canonical names)
# Handles both old enum names (LLM_PROVIDER_TGI) and short names (tgi)
PROVIDER_ALIASES: dict[str, str] = {
    # OpenAI-compatible providers
    "openai-compatible": "openai-compatible",
    "openai_compatible": "openai-compatible",
    "llm_provider_openai_compatible": "openai-compatible",
    # Legacy TGI
    "tgi": "openai-compatible",
    "llm_provider_tgi": "openai-compatible",
    # Legacy vLLM
    "vllm": "openai-compatible",
    "llm_provider_vllm": "openai-compatible",
    # Legacy OpenAI
    "openai": "openai-compatible",
    "llm_provider_openai": "openai-compatible",
    # Legacy Ollama
    "ollama": "openai-compatible",
    "llm_provider_ollama": "openai-compatible",
    # Anthropic API
    "anthropic": "anthropic",
    "llm_provider_anthropic": "anthropic",
    # Anthropic Token (Claude CLI)
    "anthropic-token": "anthropic-token",
    "anthropic_token": "anthropic-token",
    "llm_provider_anthropic_token": "anthropic-token",
}


def normalize_provider(provider: str) -> str:
    """
    Normalize provider name to canonical form.

    Handles legacy enum names (LLM_PROVIDER_TGI) and short names (tgi).

    Args:
        provider: Raw provider string from database or API.

    Returns:
        Canonical provider name: openai-compatible, anthropic, or anthropic-token.

    Raises:
        ValueError: If provider is not recognized.
    """
    normalized = provider.lower().strip()
    canonical = PROVIDER_ALIASES.get(normalized)
    if canonical:
        return canonical
    raise ValueError(f"Unknown LLM provider: {provider}")


@dataclass
class LLMConfig:
    """LLM configuration from database."""

    provider: str
    endpoint: str
    model_id: str
    api_key: str | None
    max_tokens: int
    temperature: float
    session_key: str | None = None  # For anthropic-token provider session tracking


@dataclass
class ChatMessage:
    """Chat message for LLM context."""

    role: str
    content: str


class LLMClient:
    """
    Async HTTP client for LLM providers.

    Supports:
    - OpenAI (and compatible APIs like Azure, Anyscale)
    - Anthropic (API with streaming)
    - Anthropic Token (Claude CLI with Max subscription, non-streaming)
    - Ollama
    - TGI/vLLM (OpenAI-compatible)

    Attributes:
        timeout: HTTP request timeout in seconds.
    """

    def __init__(self, timeout: float = 120.0) -> None:
        """
        Initialize LLM client.

        Args:
            timeout: Request timeout in seconds.
        """
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._claude_cli: ClaudeCliProvider | None = None

    def _get_claude_cli_provider(self) -> ClaudeCliProvider:
        """Get or create Claude CLI provider instance."""
        if self._claude_cli is None:
            self._claude_cli = ClaudeCliProvider(
                config=ClaudeCliConfig(timeout_seconds=int(self._timeout))
            )
        return self._claude_cli

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True,
            )
        return self._client

    async def stream_completion(
        self,
        config: LLMConfig,
        messages: list[ChatMessage],
    ) -> AsyncIterator[str]:
        """
        Stream chat completion tokens from LLM.

        Args:
            config: LLM configuration.
            messages: Chat messages for context.

        Yields:
            String tokens as they are generated.

        Raises:
            ServiceUnavailableError: If LLM service fails.

        Note:
            For anthropic-token provider, the full response is yielded at once
            (no streaming) since Claude CLI does not support streaming output.
        """
        try:
            provider = normalize_provider(config.provider)
        except ValueError:
            logger.error("❌ Unsupported LLM provider: %s", config.provider)
            raise ServiceUnavailableError(f"LLM provider '{config.provider}'")

        if provider == "openai-compatible":
            async for token in self._stream_openai_compatible(config, messages):
                yield token
        elif provider == "anthropic":
            async for token in self._stream_anthropic(config, messages):
                yield token
        elif provider == "anthropic-token":
            # Non-streaming: yield complete response
            text = await self._complete_anthropic_token(config, messages)
            yield text

    async def _stream_openai_compatible(
        self,
        config: LLMConfig,
        messages: list[ChatMessage],
    ) -> AsyncIterator[str]:
        """
        Stream from OpenAI-compatible API.

        Works with: OpenAI, Azure OpenAI, TGI, vLLM, Ollama.
        """
        client = await self._ensure_client()

        # Build endpoint URL
        endpoint = config.endpoint.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint = f"{endpoint}/v1/chat/completions"

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        payload = {
            "model": config.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "stream": True,
        }

        logger.info(
            "🤖 Streaming from %s (%s)",
            config.provider,
            config.model_id,
        )

        try:
            async with client.stream(
                "POST",
                endpoint,
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    logger.error(
                        "❌ LLM API error %d: %s",
                        response.status_code,
                        error_body.decode()[:500],
                    )
                    raise ServiceUnavailableError(f"LLM ({config.provider})")

                async for line in response.aiter_lines():
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPError as e:
            logger.error("❌ HTTP error calling LLM: %s", e)
            raise ServiceUnavailableError(f"LLM ({config.provider})") from e

    async def _stream_anthropic(
        self,
        config: LLMConfig,
        messages: list[ChatMessage],
    ) -> AsyncIterator[str]:
        """Stream from Anthropic API."""
        client = await self._ensure_client()

        endpoint = config.endpoint.rstrip("/")
        if not endpoint.endswith("/messages"):
            endpoint = f"{endpoint}/v1/messages"

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if config.api_key:
            headers["x-api-key"] = config.api_key

        # Convert messages to Anthropic format
        system_message = ""
        anthropic_messages = []
        for m in messages:
            if m.role == "system":
                system_message = m.content
            else:
                anthropic_messages.append({"role": m.role, "content": m.content})

        payload: dict[str, Any] = {
            "model": config.model_id,
            "messages": anthropic_messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "stream": True,
        }
        if system_message:
            payload["system"] = system_message

        logger.info("🤖 Streaming from Anthropic (%s)", config.model_id)

        try:
            async with client.stream(
                "POST",
                endpoint,
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    logger.error(
                        "❌ Anthropic API error %d: %s",
                        response.status_code,
                        error_body.decode()[:500],
                    )
                    raise ServiceUnavailableError("LLM (anthropic)")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            event_type = data.get("type", "")
                            if event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                text = delta.get("text", "")
                                if text:
                                    yield text
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPError as e:
            logger.error("❌ HTTP error calling Anthropic: %s", e)
            raise ServiceUnavailableError("LLM (anthropic)") from e

    async def _complete_anthropic_token(
        self,
        config: LLMConfig,
        messages: list[ChatMessage],
    ) -> str:
        """
        Complete using Claude CLI with Max subscription OAuth token.

        This method uses the Claude CLI instead of the HTTP API. It does not
        support streaming - the complete response is returned after execution.

        Args:
            config: LLM configuration. Requires api_key (OAuth token) and
                optionally session_key for conversation continuity.
            messages: Chat messages for context.

        Returns:
            Complete response text.

        Raises:
            ServiceUnavailableError: If Claude CLI execution fails.
        """
        if not config.api_key:
            logger.error("❌ anthropic-token provider requires OAuth token in api_key")
            raise ServiceUnavailableError("LLM (anthropic-token): missing OAuth token")

        # Extract system prompt and user messages
        system_prompt: str | None = None
        user_content_parts: list[str] = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            elif msg.role in ("user", "assistant"):
                # Include conversation context
                prefix = "User: " if msg.role == "user" else "Assistant: "
                user_content_parts.append(f"{prefix}{msg.content}")

        # Build the prompt - for continuing conversation, include history
        # For single message, just use the last user message
        if len(user_content_parts) <= 2:
            # Simple case: just the last user message
            prompt = messages[-1].content if messages else ""
        else:
            # Multi-turn: combine into prompt
            prompt = "\n\n".join(user_content_parts)

        # Generate session key if not provided
        session_key = config.session_key
        if not session_key:
            # Use a hash of endpoint + model as fallback session key
            # This means sessions won't persist across calls without explicit key
            import hashlib
            session_key = hashlib.sha256(
                f"{config.endpoint}:{config.model_id}".encode()
            ).hexdigest()[:16]

        logger.info(
            "🤖 Calling Claude CLI (%s) with session_key=%s",
            config.model_id,
            session_key,
        )

        try:
            provider = self._get_claude_cli_provider()
            response = await provider.complete(
                prompt=prompt,
                token=config.api_key,
                session_key=session_key,
                system_prompt=system_prompt,
                model=config.model_id,
            )
            return response.text

        except ClaudeCliTimeoutError as e:
            logger.error("❌ Claude CLI timed out: %s", e)
            raise ServiceUnavailableError("LLM (anthropic-token): timeout") from e
        except ClaudeCliError as e:
            logger.error("❌ Claude CLI error: %s", e)
            raise ServiceUnavailableError(
                f"LLM (anthropic-token): {e.message[:100]}"
            ) from e

    def clear_anthropic_token_session(self, session_key: str) -> None:
        """
        Clear Claude CLI session for a given session key.

        Call this when a user wants to start a fresh conversation.

        Args:
            session_key: The session key to clear.
        """
        if self._claude_cli:
            self._claude_cli.clear_session(session_key)

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("✅ LLM client closed")


# Global client instance
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get the global LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


async def close_llm_client() -> None:
    """Close the global LLM client."""
    global _llm_client
    if _llm_client is not None:
        await _llm_client.close()
        _llm_client = None
