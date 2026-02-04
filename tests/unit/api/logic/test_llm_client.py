"""Unit tests for LLMClient."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.logic.claude_cli_provider import (
    ClaudeCliError,
    ClaudeCliProvider,
    ClaudeCliResponse,
    ClaudeCliTimeoutError,
)
from api.logic.exceptions import ServiceUnavailableError
from api.logic.llm_client import (
    ChatMessage,
    LLMClient,
    LLMConfig,
    PROVIDER_ALIASES,
    normalize_provider,
)


class TestProviderNormalization:
    """Tests for normalize_provider() and PROVIDER_ALIASES."""

    # Test canonical names pass through unchanged
    @pytest.mark.parametrize(
        "provider,expected",
        [
            ("openai-compatible", "openai-compatible"),
            ("anthropic", "anthropic"),
            ("anthropic-token", "anthropic-token"),
        ],
    )
    def test_canonical_names(self, provider: str, expected: str) -> None:
        """Test canonical provider names pass through unchanged."""
        assert normalize_provider(provider) == expected

    # Test legacy TGI values
    @pytest.mark.parametrize(
        "provider",
        ["tgi", "TGI", "Tgi", "llm_provider_tgi", "LLM_PROVIDER_TGI"],
    )
    def test_legacy_tgi_normalizes_to_openai_compatible(self, provider: str) -> None:
        """Test legacy TGI provider values normalize to openai-compatible."""
        assert normalize_provider(provider) == "openai-compatible"

    # Test legacy vLLM values
    @pytest.mark.parametrize(
        "provider",
        ["vllm", "VLLM", "vLLM", "llm_provider_vllm", "LLM_PROVIDER_VLLM"],
    )
    def test_legacy_vllm_normalizes_to_openai_compatible(self, provider: str) -> None:
        """Test legacy vLLM provider values normalize to openai-compatible."""
        assert normalize_provider(provider) == "openai-compatible"

    # Test legacy OpenAI values
    @pytest.mark.parametrize(
        "provider",
        ["openai", "OPENAI", "OpenAI", "llm_provider_openai", "LLM_PROVIDER_OPENAI"],
    )
    def test_legacy_openai_normalizes_to_openai_compatible(self, provider: str) -> None:
        """Test legacy OpenAI provider values normalize to openai-compatible."""
        assert normalize_provider(provider) == "openai-compatible"

    # Test legacy Ollama values
    @pytest.mark.parametrize(
        "provider",
        ["ollama", "OLLAMA", "Ollama", "llm_provider_ollama", "LLM_PROVIDER_OLLAMA"],
    )
    def test_legacy_ollama_normalizes_to_openai_compatible(self, provider: str) -> None:
        """Test legacy Ollama provider values normalize to openai-compatible."""
        assert normalize_provider(provider) == "openai-compatible"

    # Test underscore variants of openai-compatible
    @pytest.mark.parametrize(
        "provider",
        [
            "openai_compatible",
            "OPENAI_COMPATIBLE",
            "llm_provider_openai_compatible",
            "LLM_PROVIDER_OPENAI_COMPATIBLE",
        ],
    )
    def test_openai_compatible_underscore_variants(self, provider: str) -> None:
        """Test underscore variants of openai-compatible normalize correctly."""
        assert normalize_provider(provider) == "openai-compatible"

    # Test Anthropic API values
    @pytest.mark.parametrize(
        "provider",
        ["anthropic", "ANTHROPIC", "llm_provider_anthropic", "LLM_PROVIDER_ANTHROPIC"],
    )
    def test_anthropic_api_normalizes_correctly(self, provider: str) -> None:
        """Test Anthropic API provider values normalize correctly."""
        assert normalize_provider(provider) == "anthropic"

    # Test Anthropic Token values
    @pytest.mark.parametrize(
        "provider",
        [
            "anthropic-token",
            "ANTHROPIC-TOKEN",
            "anthropic_token",
            "ANTHROPIC_TOKEN",
            "llm_provider_anthropic_token",
            "LLM_PROVIDER_ANTHROPIC_TOKEN",
        ],
    )
    def test_anthropic_token_normalizes_correctly(self, provider: str) -> None:
        """Test Anthropic Token provider values normalize correctly."""
        assert normalize_provider(provider) == "anthropic-token"

    # Test whitespace handling
    @pytest.mark.parametrize(
        "provider,expected",
        [
            ("  openai  ", "openai-compatible"),
            ("\tanthropic\n", "anthropic"),
            ("  anthropic-token  ", "anthropic-token"),
            (" tgi ", "openai-compatible"),
        ],
    )
    def test_whitespace_handling(self, provider: str, expected: str) -> None:
        """Test that whitespace is stripped before normalization."""
        assert normalize_provider(provider) == expected

    # Test unknown provider raises ValueError
    def test_unknown_provider_raises_value_error(self) -> None:
        """Test unknown provider raises ValueError with descriptive message."""
        with pytest.raises(ValueError) as exc_info:
            normalize_provider("unknown_provider")

        assert "Unknown LLM provider" in str(exc_info.value)
        assert "unknown_provider" in str(exc_info.value)

    def test_empty_string_raises_value_error(self) -> None:
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError):
            normalize_provider("")

    def test_whitespace_only_raises_value_error(self) -> None:
        """Test whitespace-only string raises ValueError."""
        with pytest.raises(ValueError):
            normalize_provider("   ")

    # Test PROVIDER_ALIASES coverage
    def test_provider_aliases_has_all_expected_keys(self) -> None:
        """Test PROVIDER_ALIASES dict contains all expected mappings."""
        expected_keys = {
            # OpenAI-compatible variants
            "openai-compatible",
            "openai_compatible",
            "llm_provider_openai_compatible",
            "tgi",
            "llm_provider_tgi",
            "vllm",
            "llm_provider_vllm",
            "openai",
            "llm_provider_openai",
            "ollama",
            "llm_provider_ollama",
            # Anthropic API
            "anthropic",
            "llm_provider_anthropic",
            # Anthropic Token
            "anthropic-token",
            "anthropic_token",
            "llm_provider_anthropic_token",
        }
        assert set(PROVIDER_ALIASES.keys()) == expected_keys

    def test_provider_aliases_values_are_canonical(self) -> None:
        """Test all PROVIDER_ALIASES values are canonical provider names."""
        canonical_names = {"openai-compatible", "anthropic", "anthropic-token"}
        for alias, canonical in PROVIDER_ALIASES.items():
            assert canonical in canonical_names, f"Alias '{alias}' maps to non-canonical '{canonical}'"


class TestLLMClientStreamCompletion:
    """Tests for LLMClient.stream_completion()."""

    @pytest.fixture
    def client(self) -> LLMClient:
        """Create LLMClient instance."""
        return LLMClient(timeout=30.0)

    @pytest.fixture
    def openai_config(self) -> LLMConfig:
        """Create OpenAI-compatible config."""
        return LLMConfig(
            provider="openai",
            endpoint="https://api.openai.com",
            model_id="gpt-4",
            api_key="test-key",
            max_tokens=1024,
            temperature=0.7,
        )

    @pytest.fixture
    def anthropic_config(self) -> LLMConfig:
        """Create Anthropic config."""
        return LLMConfig(
            provider="anthropic",
            endpoint="https://api.anthropic.com",
            model_id="claude-3-opus",
            api_key="test-key",
            max_tokens=1024,
            temperature=0.7,
        )

    @pytest.fixture
    def messages(self) -> list[ChatMessage]:
        """Create sample messages."""
        return [
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="Hello"),
        ]

    @pytest.mark.asyncio
    async def test_stream_openai_compatible(
        self,
        client: LLMClient,
        openai_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test streaming from OpenAI-compatible API."""
        # Mock httpx response with SSE stream
        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def mock_iter_lines():
            yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
            yield 'data: {"choices":[{"delta":{"content":" world"}}]}'
            yield "data: [DONE]"

        mock_response.aiter_lines = mock_iter_lines

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=AsyncMock())
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        client._client = mock_client

        tokens = []
        async for token in client._stream_openai_compatible(openai_config, messages):
            tokens.append(token)

        assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_stream_anthropic(
        self,
        client: LLMClient,
        anthropic_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test streaming from Anthropic API."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def mock_iter_lines():
            yield 'data: {"type":"content_block_delta","delta":{"text":"Hi"}}'
            yield 'data: {"type":"content_block_delta","delta":{"text":" there"}}'
            yield 'data: {"type":"message_stop"}'

        mock_response.aiter_lines = mock_iter_lines

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=AsyncMock())
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        client._client = mock_client

        tokens = []
        async for token in client._stream_anthropic(anthropic_config, messages):
            tokens.append(token)

        assert tokens == ["Hi", " there"]

    @pytest.mark.asyncio
    async def test_stream_anthropic_passes_temperature(
        self,
        client: LLMClient,
        messages: list[ChatMessage],
    ) -> None:
        """Test Anthropic API request includes temperature parameter."""
        config = LLMConfig(
            provider="anthropic",
            endpoint="https://api.anthropic.com",
            model_id="claude-3-opus",
            api_key="test-key",
            max_tokens=1024,
            temperature=0.3,  # Specific value to verify
        )

        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def mock_iter_lines():
            yield 'data: {"type":"message_stop"}'

        mock_response.aiter_lines = mock_iter_lines

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=AsyncMock())
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        client._client = mock_client

        tokens = []
        async for token in client._stream_anthropic(config, messages):
            tokens.append(token)

        # Verify temperature was passed in the request payload
        call_args = mock_client.stream.call_args
        json_payload = call_args.kwargs.get("json", {})
        assert json_payload.get("temperature") == 0.3

    @pytest.mark.asyncio
    async def test_unsupported_provider_raises_error(
        self,
        client: LLMClient,
        messages: list[ChatMessage],
    ) -> None:
        """Test unsupported provider raises ServiceUnavailableError."""
        bad_config = LLMConfig(
            provider="unknown_provider",
            endpoint="https://example.com",
            model_id="model",
            api_key=None,
            max_tokens=100,
            temperature=0.5,
        )

        with pytest.raises(ServiceUnavailableError) as exc_info:
            tokens = []
            async for token in client.stream_completion(bad_config, messages):
                tokens.append(token)

        assert "unknown_provider" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_error_raises_service_unavailable(
        self,
        client: LLMClient,
        openai_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test API error response raises ServiceUnavailableError."""
        mock_response = AsyncMock()
        mock_response.status_code = 500

        async def mock_aread():
            return b'{"error": "Internal server error"}'

        mock_response.aread = mock_aread

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=AsyncMock())
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        client._client = mock_client

        with pytest.raises(ServiceUnavailableError):
            tokens = []
            async for token in client._stream_openai_compatible(openai_config, messages):
                tokens.append(token)


class TestLLMClientClose:
    """Tests for LLMClient.close()."""

    @pytest.mark.asyncio
    async def test_close_closes_http_client(self) -> None:
        """Test close properly closes HTTP client."""
        client = LLMClient()
        mock_http_client = AsyncMock()
        client._client = mock_http_client

        await client.close()

        mock_http_client.aclose.assert_called_once()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_safe_when_no_client(self) -> None:
        """Test close is safe when no client initialized."""
        client = LLMClient()
        await client.close()  # Should not raise


class TestLLMClientAnthropicToken:
    """Tests for LLMClient anthropic-token provider."""

    @pytest.fixture
    def client(self) -> LLMClient:
        """Create LLMClient instance."""
        return LLMClient(timeout=30.0)

    @pytest.fixture
    def anthropic_token_config(self) -> LLMConfig:
        """Create anthropic-token config."""
        return LLMConfig(
            provider="anthropic-token",
            endpoint="",  # Not used for CLI
            model_id="opus",
            api_key="sk-ant-oat01-test-token",
            max_tokens=1024,
            temperature=0.7,
            session_key="test-session-key",
        )

    @pytest.fixture
    def messages(self) -> list[ChatMessage]:
        """Create sample messages."""
        return [
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="Hello"),
        ]

    @pytest.mark.asyncio
    async def test_stream_completion_routes_to_anthropic_token(
        self,
        client: LLMClient,
        anthropic_token_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test stream_completion routes to anthropic-token provider."""
        mock_response = ClaudeCliResponse(text="Hello from Claude CLI!")

        with patch.object(
            ClaudeCliProvider,
            "complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with patch.object(
                ClaudeCliProvider,
                "ensure_credentials_file",
            ):
                tokens = []
                async for token in client.stream_completion(
                    anthropic_token_config,
                    messages,
                ):
                    tokens.append(token)

                # Non-streaming: single yield with full response
                assert tokens == ["Hello from Claude CLI!"]

    @pytest.mark.asyncio
    async def test_complete_anthropic_token_success(
        self,
        client: LLMClient,
        anthropic_token_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test successful completion via Claude CLI."""
        mock_response = ClaudeCliResponse(
            text="Test response",
            session_id="cli-session-123",
        )

        mock_provider = MagicMock(spec=ClaudeCliProvider)
        mock_provider.complete = AsyncMock(return_value=mock_response)
        client._claude_cli = mock_provider

        result = await client._complete_anthropic_token(
            anthropic_token_config,
            messages,
        )

        assert result == "Test response"
        mock_provider.complete.assert_called_once()

        # Verify call parameters
        call_kwargs = mock_provider.complete.call_args[1]
        assert call_kwargs["token"] == "sk-ant-oat01-test-token"
        assert call_kwargs["session_key"] == "test-session-key"
        assert "You are helpful." in call_kwargs["system_prompt"]

    @pytest.mark.asyncio
    async def test_complete_anthropic_token_missing_token(
        self,
        client: LLMClient,
        messages: list[ChatMessage],
    ) -> None:
        """Test error when OAuth token is missing."""
        config = LLMConfig(
            provider="anthropic-token",
            endpoint="",
            model_id="opus",
            api_key=None,  # Missing token
            max_tokens=1024,
            temperature=0.7,
        )

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await client._complete_anthropic_token(config, messages)

        assert "missing OAuth token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_anthropic_token_timeout(
        self,
        client: LLMClient,
        anthropic_token_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test timeout error handling."""
        mock_provider = MagicMock(spec=ClaudeCliProvider)
        mock_provider.complete = AsyncMock(
            side_effect=ClaudeCliTimeoutError(30)
        )
        client._claude_cli = mock_provider

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await client._complete_anthropic_token(
                anthropic_token_config,
                messages,
            )

        assert "timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_anthropic_token_cli_error(
        self,
        client: LLMClient,
        anthropic_token_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test CLI error handling."""
        mock_provider = MagicMock(spec=ClaudeCliProvider)
        mock_provider.complete = AsyncMock(
            side_effect=ClaudeCliError("Invalid token", exit_code=1)
        )
        client._claude_cli = mock_provider

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await client._complete_anthropic_token(
                anthropic_token_config,
                messages,
            )

        assert "anthropic-token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_anthropic_token_generates_session_key(
        self,
        client: LLMClient,
        messages: list[ChatMessage],
    ) -> None:
        """Test session key generation when not provided."""
        config = LLMConfig(
            provider="anthropic-token",
            endpoint="https://example.com",
            model_id="opus",
            api_key="test-token",
            max_tokens=1024,
            temperature=0.7,
            session_key=None,  # No session key
        )

        mock_response = ClaudeCliResponse(text="OK")
        mock_provider = MagicMock(spec=ClaudeCliProvider)
        mock_provider.complete = AsyncMock(return_value=mock_response)
        client._claude_cli = mock_provider

        await client._complete_anthropic_token(config, messages)

        # Should have generated a session key
        call_kwargs = mock_provider.complete.call_args[1]
        assert call_kwargs["session_key"] is not None
        assert len(call_kwargs["session_key"]) == 16  # SHA256 hash prefix

    @pytest.mark.asyncio
    async def test_complete_anthropic_token_multi_turn(
        self,
        client: LLMClient,
        anthropic_token_config: LLMConfig,
    ) -> None:
        """Test multi-turn conversation handling."""
        messages = [
            ChatMessage(role="system", content="Be concise."),
            ChatMessage(role="user", content="Hi"),
            ChatMessage(role="assistant", content="Hello!"),
            ChatMessage(role="user", content="How are you?"),
            ChatMessage(role="assistant", content="I'm good."),
            ChatMessage(role="user", content="Great!"),
        ]

        mock_response = ClaudeCliResponse(text="Thanks!")
        mock_provider = MagicMock(spec=ClaudeCliProvider)
        mock_provider.complete = AsyncMock(return_value=mock_response)
        client._claude_cli = mock_provider

        await client._complete_anthropic_token(anthropic_token_config, messages)

        # Should include conversation context
        call_kwargs = mock_provider.complete.call_args[1]
        prompt = call_kwargs["prompt"]
        assert "User:" in prompt
        assert "Assistant:" in prompt

    def test_clear_anthropic_token_session(self, client: LLMClient) -> None:
        """Test clearing Claude CLI session."""
        mock_provider = MagicMock(spec=ClaudeCliProvider)
        client._claude_cli = mock_provider

        client.clear_anthropic_token_session("test-key")

        mock_provider.clear_session.assert_called_once_with("test-key")

    def test_clear_anthropic_token_session_no_provider(
        self,
        client: LLMClient,
    ) -> None:
        """Test clearing session when provider not initialized."""
        client._claude_cli = None
        client.clear_anthropic_token_session("test-key")  # Should not raise

    def test_get_claude_cli_provider_creates_instance(
        self,
        client: LLMClient,
    ) -> None:
        """Test lazy initialization of Claude CLI provider."""
        assert client._claude_cli is None

        provider = client._get_claude_cli_provider()

        assert provider is not None
        assert isinstance(provider, ClaudeCliProvider)
        assert client._claude_cli is provider

    def test_get_claude_cli_provider_returns_existing(
        self,
        client: LLMClient,
    ) -> None:
        """Test that existing provider is reused."""
        # Create first instance
        provider1 = client._get_claude_cli_provider()
        # Get again
        provider2 = client._get_claude_cli_provider()

        assert provider1 is provider2


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_session_key_default_none(self) -> None:
        """Test session_key defaults to None."""
        config = LLMConfig(
            provider="openai",
            endpoint="https://api.openai.com",
            model_id="gpt-4",
            api_key="key",
            max_tokens=1024,
            temperature=0.7,
        )
        assert config.session_key is None

    def test_session_key_can_be_set(self) -> None:
        """Test session_key can be provided."""
        config = LLMConfig(
            provider="anthropic-token",
            endpoint="",
            model_id="opus",
            api_key="token",
            max_tokens=1024,
            temperature=0.7,
            session_key="my-session",
        )
        assert config.session_key == "my-session"


class TestLLMClientAnthropicTokenEdgeCases:
    """Edge case tests for anthropic-token provider."""

    @pytest.fixture
    def client(self) -> LLMClient:
        """Create LLMClient instance."""
        return LLMClient(timeout=30.0)

    @pytest.fixture
    def config(self) -> LLMConfig:
        """Create anthropic-token config."""
        return LLMConfig(
            provider="anthropic-token",
            endpoint="",
            model_id="opus",
            api_key="test-token",
            max_tokens=1024,
            temperature=0.7,
            session_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_complete_anthropic_token_empty_messages(
        self,
        client: LLMClient,
        config: LLMConfig,
    ) -> None:
        """Test handling of empty messages list."""
        mock_response = ClaudeCliResponse(text="OK")
        mock_provider = MagicMock(spec=ClaudeCliProvider)
        mock_provider.complete = AsyncMock(return_value=mock_response)
        client._claude_cli = mock_provider

        result = await client._complete_anthropic_token(config, [])

        assert result == "OK"
        # Should have empty prompt
        call_kwargs = mock_provider.complete.call_args[1]
        assert call_kwargs["prompt"] == ""

    @pytest.mark.asyncio
    async def test_complete_anthropic_token_single_user_message(
        self,
        client: LLMClient,
        config: LLMConfig,
    ) -> None:
        """Test with just one user message (no system prompt)."""
        messages = [ChatMessage(role="user", content="Just one message")]

        mock_response = ClaudeCliResponse(text="Response")
        mock_provider = MagicMock(spec=ClaudeCliProvider)
        mock_provider.complete = AsyncMock(return_value=mock_response)
        client._claude_cli = mock_provider

        await client._complete_anthropic_token(config, messages)

        call_kwargs = mock_provider.complete.call_args[1]
        assert call_kwargs["prompt"] == "Just one message"
        assert call_kwargs["system_prompt"] is None

    @pytest.mark.asyncio
    async def test_complete_anthropic_token_two_turn_conversation(
        self,
        client: LLMClient,
        config: LLMConfig,
    ) -> None:
        """Test with exactly two turns (user + assistant)."""
        messages = [
            ChatMessage(role="user", content="Hi"),
            ChatMessage(role="assistant", content="Hello"),
        ]

        mock_response = ClaudeCliResponse(text="Response")
        mock_provider = MagicMock(spec=ClaudeCliProvider)
        mock_provider.complete = AsyncMock(return_value=mock_response)
        client._claude_cli = mock_provider

        await client._complete_anthropic_token(config, messages)

        # With <= 2 parts, should use last message
        call_kwargs = mock_provider.complete.call_args[1]
        assert call_kwargs["prompt"] == "Hello"


class TestStreamCompletionRouting:
    """Tests for stream_completion() routing logic."""

    @pytest.fixture
    def client(self) -> LLMClient:
        """Create LLMClient instance."""
        return LLMClient(timeout=30.0)

    @pytest.fixture
    def messages(self) -> list[ChatMessage]:
        """Create sample messages."""
        return [ChatMessage(role="user", content="Hello")]

    @pytest.mark.asyncio
    async def test_stream_completion_routes_openai_compatible(
        self,
        client: LLMClient,
        messages: list[ChatMessage],
    ) -> None:
        """Test stream_completion routes to OpenAI-compatible provider."""
        config = LLMConfig(
            provider="openai",  # Will normalize to openai-compatible
            endpoint="https://api.openai.com",
            model_id="gpt-4",
            api_key="test-key",
            max_tokens=1024,
            temperature=0.7,
        )

        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def mock_iter_lines():
            yield 'data: {"choices":[{"delta":{"content":"Hi"}}]}'
            yield "data: [DONE]"

        mock_response.aiter_lines = mock_iter_lines

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=AsyncMock())
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        client._client = mock_client

        tokens = []
        async for token in client.stream_completion(config, messages):
            tokens.append(token)

        assert tokens == ["Hi"]

    @pytest.mark.asyncio
    async def test_stream_completion_routes_anthropic(
        self,
        client: LLMClient,
        messages: list[ChatMessage],
    ) -> None:
        """Test stream_completion routes to Anthropic provider."""
        config = LLMConfig(
            provider="anthropic",
            endpoint="https://api.anthropic.com",
            model_id="claude-3-opus",
            api_key="test-key",
            max_tokens=1024,
            temperature=0.7,
        )

        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def mock_iter_lines():
            yield 'data: {"type":"content_block_delta","delta":{"text":"Hello"}}'
            yield 'data: {"type":"message_stop"}'

        mock_response.aiter_lines = mock_iter_lines

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=AsyncMock())
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        client._client = mock_client

        tokens = []
        async for token in client.stream_completion(config, messages):
            tokens.append(token)

        assert tokens == ["Hello"]


class TestEnsureClient:
    """Tests for _ensure_client() method."""

    @pytest.mark.asyncio
    async def test_ensure_client_creates_new_client(self) -> None:
        """Test _ensure_client creates new httpx.AsyncClient when none exists."""
        client = LLMClient(timeout=60.0)
        assert client._client is None

        http_client = await client._ensure_client()

        assert http_client is not None
        assert client._client is http_client
        # Verify it's the same instance on second call
        http_client2 = await client._ensure_client()
        assert http_client is http_client2

        # Cleanup
        await client.close()


class TestStreamingEdgeCases:
    """Tests for streaming edge cases and error handling."""

    @pytest.fixture
    def client(self) -> LLMClient:
        """Create LLMClient instance."""
        return LLMClient(timeout=30.0)

    @pytest.fixture
    def openai_config(self) -> LLMConfig:
        """Create OpenAI-compatible config."""
        return LLMConfig(
            provider="openai",
            endpoint="https://api.openai.com",
            model_id="gpt-4",
            api_key="test-key",
            max_tokens=1024,
            temperature=0.7,
        )

    @pytest.fixture
    def anthropic_config(self) -> LLMConfig:
        """Create Anthropic config."""
        return LLMConfig(
            provider="anthropic",
            endpoint="https://api.anthropic.com",
            model_id="claude-3-opus",
            api_key="test-key",
            max_tokens=1024,
            temperature=0.7,
        )

    @pytest.fixture
    def messages(self) -> list[ChatMessage]:
        """Create sample messages."""
        return [ChatMessage(role="user", content="Hello")]

    @pytest.mark.asyncio
    async def test_openai_json_decode_error_continues(
        self,
        client: LLMClient,
        openai_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test OpenAI stream handles JSON decode errors gracefully."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def mock_iter_lines():
            yield "data: {invalid json"  # Should be skipped
            yield 'data: {"choices":[{"delta":{"content":"OK"}}]}'
            yield "data: [DONE]"

        mock_response.aiter_lines = mock_iter_lines

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=AsyncMock())
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        client._client = mock_client

        tokens = []
        async for token in client._stream_openai_compatible(openai_config, messages):
            tokens.append(token)

        # Invalid JSON skipped, valid one processed
        assert tokens == ["OK"]

    @pytest.mark.asyncio
    async def test_openai_http_error_raises_service_unavailable(
        self,
        client: LLMClient,
        openai_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test OpenAI HTTP error raises ServiceUnavailableError."""
        import httpx

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(side_effect=httpx.HTTPError("Connection failed"))

        client._client = mock_client

        with pytest.raises(ServiceUnavailableError):
            tokens = []
            async for token in client._stream_openai_compatible(openai_config, messages):
                tokens.append(token)

    @pytest.mark.asyncio
    async def test_anthropic_api_error_raises_service_unavailable(
        self,
        client: LLMClient,
        anthropic_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test Anthropic API error (non-200) raises ServiceUnavailableError."""
        mock_response = AsyncMock()
        mock_response.status_code = 429  # Rate limited

        async def mock_aread():
            return b'{"error": "rate_limited"}'

        mock_response.aread = mock_aread

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=AsyncMock())
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        client._client = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            tokens = []
            async for token in client._stream_anthropic(anthropic_config, messages):
                tokens.append(token)

        assert "anthropic" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_anthropic_empty_line_skipped(
        self,
        client: LLMClient,
        anthropic_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test Anthropic stream handles empty lines correctly."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def mock_iter_lines():
            yield ""  # Empty line should be skipped
            yield ""  # Another empty line
            yield 'data: {"type":"content_block_delta","delta":{"text":"Hi"}}'
            yield ""  # Empty after data
            yield 'data: {"type":"message_stop"}'

        mock_response.aiter_lines = mock_iter_lines

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=AsyncMock())
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        client._client = mock_client

        tokens = []
        async for token in client._stream_anthropic(anthropic_config, messages):
            tokens.append(token)

        assert tokens == ["Hi"]

    @pytest.mark.asyncio
    async def test_anthropic_json_decode_error_continues(
        self,
        client: LLMClient,
        anthropic_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test Anthropic stream handles JSON decode errors gracefully."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def mock_iter_lines():
            yield "data: {invalid"  # Bad JSON, should skip
            yield 'data: {"type":"content_block_delta","delta":{"text":"OK"}}'
            yield 'data: {"type":"message_stop"}'

        mock_response.aiter_lines = mock_iter_lines

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=AsyncMock())
        mock_client.stream.return_value.__aenter__.return_value = mock_response

        client._client = mock_client

        tokens = []
        async for token in client._stream_anthropic(anthropic_config, messages):
            tokens.append(token)

        assert tokens == ["OK"]

    @pytest.mark.asyncio
    async def test_anthropic_http_error_raises_service_unavailable(
        self,
        client: LLMClient,
        anthropic_config: LLMConfig,
        messages: list[ChatMessage],
    ) -> None:
        """Test Anthropic HTTP error raises ServiceUnavailableError."""
        import httpx

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(side_effect=httpx.HTTPError("Connection failed"))

        client._client = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            tokens = []
            async for token in client._stream_anthropic(anthropic_config, messages):
                tokens.append(token)

        assert "anthropic" in str(exc_info.value)


class TestGlobalFunctions:
    """Tests for global LLM client functions."""

    def test_get_llm_client_creates_instance(self) -> None:
        """Test get_llm_client creates singleton."""
        import api.logic.llm_client as module

        # Reset global state
        module._llm_client = None

        client = module.get_llm_client()
        assert client is not None
        assert isinstance(client, LLMClient)

        # Second call returns same instance
        client2 = module.get_llm_client()
        assert client is client2

        # Cleanup
        module._llm_client = None

    @pytest.mark.asyncio
    async def test_close_llm_client(self) -> None:
        """Test close_llm_client closes and clears singleton."""
        import api.logic.llm_client as module

        # Setup: create a client with mock HTTP client
        module._llm_client = LLMClient()
        mock_http = AsyncMock()
        module._llm_client._client = mock_http

        await module.close_llm_client()

        mock_http.aclose.assert_called_once()
        assert module._llm_client is None

    @pytest.mark.asyncio
    async def test_close_llm_client_when_none(self) -> None:
        """Test close_llm_client is safe when no client exists."""
        import api.logic.llm_client as module

        module._llm_client = None
        await module.close_llm_client()  # Should not raise
