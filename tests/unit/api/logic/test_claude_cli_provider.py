"""Unit tests for ClaudeCliProvider with 100% coverage."""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.logic.claude_cli_provider import (
    DEFAULT_CREDENTIALS_PATH,
    DEFAULT_TIMEOUT_SECONDS,
    ENV_KEYS_TO_CLEAR,
    MODEL_ALIASES,
    TOOLS_DISABLED_INSTRUCTION,
    ClaudeCliConfig,
    ClaudeCliCredentialsError,
    ClaudeCliError,
    ClaudeCliProvider,
    ClaudeCliResponse,
    ClaudeCliTimeoutError,
)


class TestClaudeCliConfig:
    """Tests for ClaudeCliConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ClaudeCliConfig()
        assert config.model == "opus"
        assert config.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
        assert config.credentials_path == DEFAULT_CREDENTIALS_PATH

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        custom_path = Path("/custom/path/.credentials.json")
        config = ClaudeCliConfig(
            model="sonnet",
            timeout_seconds=60,
            credentials_path=custom_path,
        )
        assert config.model == "sonnet"
        assert config.timeout_seconds == 60
        assert config.credentials_path == custom_path


class TestClaudeCliResponse:
    """Tests for ClaudeCliResponse dataclass."""

    def test_minimal_response(self) -> None:
        """Test response with only text."""
        response = ClaudeCliResponse(text="Hello, world!")
        assert response.text == "Hello, world!"
        assert response.session_id is None
        assert response.usage is None

    def test_full_response(self) -> None:
        """Test response with all fields."""
        response = ClaudeCliResponse(
            text="Hello!",
            session_id="session-123",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        assert response.text == "Hello!"
        assert response.session_id == "session-123"
        assert response.usage == {"input_tokens": 10, "output_tokens": 5}


class TestClaudeCliError:
    """Tests for Claude CLI exception classes."""

    def test_base_error(self) -> None:
        """Test ClaudeCliError base exception."""
        error = ClaudeCliError("Something went wrong", exit_code=1, stderr="Error output")
        assert error.message == "Something went wrong"
        assert error.exit_code == 1
        assert error.stderr == "Error output"
        assert str(error) == "Something went wrong"

    def test_base_error_minimal(self) -> None:
        """Test ClaudeCliError with only message."""
        error = ClaudeCliError("Simple error")
        assert error.message == "Simple error"
        assert error.exit_code is None
        assert error.stderr is None

    def test_timeout_error(self) -> None:
        """Test ClaudeCliTimeoutError."""
        error = ClaudeCliTimeoutError(300)
        assert error.timeout_seconds == 300
        assert "300s" in error.message

    def test_credentials_error(self) -> None:
        """Test ClaudeCliCredentialsError."""
        error = ClaudeCliCredentialsError("Cannot write file")
        assert error.message == "Cannot write file"


class TestClaudeCliProviderInit:
    """Tests for ClaudeCliProvider initialization."""

    def test_default_init(self) -> None:
        """Test initialization with defaults."""
        provider = ClaudeCliProvider()
        assert provider._config.model == "opus"
        assert provider.credentials_path == DEFAULT_CREDENTIALS_PATH
        assert provider._sessions == {}
        assert provider._credentials_written is False

    def test_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = ClaudeCliConfig(model="haiku", timeout_seconds=60)
        provider = ClaudeCliProvider(config=config)
        assert provider._config.model == "haiku"
        assert provider._config.timeout_seconds == 60

    def test_credentials_path_override(self) -> None:
        """Test credentials path override takes precedence."""
        config = ClaudeCliConfig(credentials_path=Path("/config/path"))
        override_path = Path("/override/path")
        provider = ClaudeCliProvider(config=config, credentials_path=override_path)
        assert provider.credentials_path == override_path


class TestNormalizeModel:
    """Tests for normalize_model method."""

    @pytest.fixture
    def provider(self) -> ClaudeCliProvider:
        """Create provider instance."""
        return ClaudeCliProvider()

    @pytest.mark.parametrize(
        "input_model,expected",
        [
            ("opus", "opus"),
            ("OPUS", "opus"),
            ("Opus", "opus"),
            ("opus-4.5", "opus"),
            ("opus-4", "opus"),
            ("claude-opus-4-5", "opus"),
            ("claude-opus-4", "opus"),
            ("sonnet", "sonnet"),
            ("sonnet-4.5", "sonnet"),
            ("sonnet-4.1", "sonnet"),
            ("sonnet-4.0", "sonnet"),
            ("claude-sonnet-4-5", "sonnet"),
            ("haiku", "haiku"),
            ("haiku-3.5", "haiku"),
            ("claude-haiku-3-5", "haiku"),
            ("unknown-model", "unknown-model"),  # Passthrough for unknown
            ("  opus  ", "opus"),  # Whitespace handling
        ],
    )
    def test_model_normalization(
        self,
        provider: ClaudeCliProvider,
        input_model: str,
        expected: str,
    ) -> None:
        """Test model normalization for various inputs."""
        assert provider.normalize_model(input_model) == expected


class TestEnsureCredentialsFile:
    """Tests for ensure_credentials_file method."""

    @pytest.fixture
    def provider(self, tmp_path: Path) -> ClaudeCliProvider:
        """Create provider with temp credentials path."""
        creds_path = tmp_path / ".claude" / ".credentials.json"
        return ClaudeCliProvider(credentials_path=creds_path)

    def test_creates_new_credentials_file(self, provider: ClaudeCliProvider) -> None:
        """Test creating new credentials file."""
        token = "sk-ant-oat01-test-token"
        provider.ensure_credentials_file(token)

        assert provider.credentials_path.exists()
        assert provider._credentials_written is True

        content = json.loads(provider.credentials_path.read_text())
        assert content["claudeAiOauth"]["accessToken"] == token
        assert content["claudeAiOauth"]["refreshToken"] is None
        assert "expiresAt" in content["claudeAiOauth"]

        # Check file permissions (Unix only)
        if os.name != "nt":
            mode = provider.credentials_path.stat().st_mode & 0o777
            assert mode == 0o600

    def test_reuses_existing_matching_token(
        self,
        provider: ClaudeCliProvider,
        tmp_path: Path,
    ) -> None:
        """Test reusing existing file with matching token."""
        token = "sk-ant-oat01-test-token"

        # Create directory and file first
        provider.credentials_path.parent.mkdir(parents=True)
        provider.credentials_path.write_text(
            json.dumps(
                {
                    "claudeAiOauth": {
                        "accessToken": token,
                        "refreshToken": "refresh",
                        "expiresAt": 9999999999999,
                    }
                }
            )
        )
        mtime_before = provider.credentials_path.stat().st_mtime

        # Should not rewrite
        provider.ensure_credentials_file(token)

        assert provider._credentials_written is True
        # File should not be modified (same mtime within tolerance)
        mtime_after = provider.credentials_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_rewrites_on_token_mismatch(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test rewriting file when token differs."""
        old_token = "old-token"
        new_token = "new-token"

        # Create with old token
        provider.credentials_path.parent.mkdir(parents=True)
        provider.credentials_path.write_text(
            json.dumps(
                {
                    "claudeAiOauth": {
                        "accessToken": old_token,
                        "expiresAt": 9999999999999,
                    }
                }
            )
        )

        # Write with new token
        provider.ensure_credentials_file(new_token)

        content = json.loads(provider.credentials_path.read_text())
        assert content["claudeAiOauth"]["accessToken"] == new_token

    def test_rewrites_on_corrupt_file(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test rewriting corrupt credentials file."""
        provider.credentials_path.parent.mkdir(parents=True)
        provider.credentials_path.write_text("not valid json {{{")

        token = "new-token"
        provider.ensure_credentials_file(token)

        content = json.loads(provider.credentials_path.read_text())
        assert content["claudeAiOauth"]["accessToken"] == token

    def test_handles_missing_claudeAiOauth_key(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test handling file with wrong structure."""
        provider.credentials_path.parent.mkdir(parents=True)
        provider.credentials_path.write_text(json.dumps({"other": "data"}))

        token = "new-token"
        provider.ensure_credentials_file(token)

        content = json.loads(provider.credentials_path.read_text())
        assert content["claudeAiOauth"]["accessToken"] == token

    def test_raises_on_directory_creation_failure(
        self,
        tmp_path: Path,
    ) -> None:
        """Test error when directory cannot be created."""
        # Create a file where directory should be
        blocker = tmp_path / ".claude"
        blocker.write_text("blocking file")

        provider = ClaudeCliProvider(
            credentials_path=blocker / ".credentials.json"
        )

        with pytest.raises(ClaudeCliCredentialsError) as exc_info:
            provider.ensure_credentials_file("token")

        assert "Failed to create credentials directory" in str(exc_info.value)

    def test_raises_on_write_failure(
        self,
        tmp_path: Path,
    ) -> None:
        """Test error when file cannot be written."""
        creds_dir = tmp_path / ".claude"
        creds_dir.mkdir(parents=True)
        creds_file = creds_dir / ".credentials.json"

        provider = ClaudeCliProvider(credentials_path=creds_file)

        # Mock write_text to raise OSError
        with patch.object(Path, "write_text", side_effect=OSError("Permission denied")):
            with pytest.raises(ClaudeCliCredentialsError) as exc_info:
                provider.ensure_credentials_file("token")
            assert "Failed to write credentials file" in str(exc_info.value)


class TestPrepareEnvironment:
    """Tests for prepare_environment method."""

    @pytest.fixture
    def provider(self) -> ClaudeCliProvider:
        """Create provider instance."""
        return ClaudeCliProvider()

    def test_clears_api_keys(self, provider: ClaudeCliProvider) -> None:
        """Test that API keys are cleared from environment."""
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "secret-key",
                "ANTHROPIC_API_KEY_OLD": "old-secret",
                "OTHER_VAR": "keep-me",
            },
        ):
            env = provider.prepare_environment()

            assert "ANTHROPIC_API_KEY" not in env
            assert "ANTHROPIC_API_KEY_OLD" not in env
            assert env.get("OTHER_VAR") == "keep-me"

    def test_handles_missing_keys(self, provider: ClaudeCliProvider) -> None:
        """Test handling when API keys don't exist."""
        # Ensure keys are not in environment
        env_copy = os.environ.copy()
        for key in ENV_KEYS_TO_CLEAR:
            env_copy.pop(key, None)

        with patch.dict(os.environ, env_copy, clear=True):
            env = provider.prepare_environment()
            # Should not raise, just skip missing keys
            for key in ENV_KEYS_TO_CLEAR:
                assert key not in env


class TestBuildArguments:
    """Tests for build_arguments method."""

    @pytest.fixture
    def provider(self) -> ClaudeCliProvider:
        """Create provider instance."""
        return ClaudeCliProvider()

    def test_new_session_with_system_prompt(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test argument building for new session with system prompt."""
        args = provider.build_arguments(
            prompt="Hello, Claude!",
            model="opus",
            session_id="session-123",
            is_resume=False,
            system_prompt="You are helpful.",
        )

        assert args[0] == "claude"
        assert "-p" in args
        assert "--output-format" in args
        assert "json" in args
        assert "--dangerously-skip-permissions" in args
        assert "--model" in args
        assert "opus" in args
        assert "--session-id" in args
        assert "session-123" in args
        assert "--append-system-prompt" in args

        # Find system prompt value
        sp_index = args.index("--append-system-prompt")
        system_prompt_value = args[sp_index + 1]
        assert "You are helpful." in system_prompt_value
        assert TOOLS_DISABLED_INSTRUCTION in system_prompt_value

        # Prompt is last
        assert args[-1] == "Hello, Claude!"

    def test_new_session_without_system_prompt(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test argument building for new session without system prompt."""
        args = provider.build_arguments(
            prompt="Hello!",
            model="sonnet",
            session_id="session-456",
            is_resume=False,
            system_prompt=None,
        )

        assert "--model" in args
        assert "sonnet" in args
        assert "--append-system-prompt" in args

        # Should still have tool disabling
        sp_index = args.index("--append-system-prompt")
        assert args[sp_index + 1] == TOOLS_DISABLED_INSTRUCTION

    def test_new_session_without_session_id(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test argument building without session ID."""
        args = provider.build_arguments(
            prompt="Hello!",
            model="opus",
            session_id=None,
            is_resume=False,
            system_prompt=None,
        )

        assert "--session-id" not in args
        assert "--model" in args

    def test_resume_session(self, provider: ClaudeCliProvider) -> None:
        """Test argument building for session resume."""
        args = provider.build_arguments(
            prompt="Continue please",
            model="opus",
            session_id="existing-session",
            is_resume=True,
            system_prompt="Ignored system prompt",
        )

        assert "--resume" in args
        assert "existing-session" in args

        # Should NOT include these when resuming
        assert "--model" not in args
        assert "--session-id" not in args
        assert "--append-system-prompt" not in args

        assert args[-1] == "Continue please"


class TestParseJsonOutput:
    """Tests for parse_json_output method."""

    @pytest.fixture
    def provider(self) -> ClaudeCliProvider:
        """Create provider instance."""
        return ClaudeCliProvider()

    def test_parse_standard_format(self, provider: ClaudeCliProvider) -> None:
        """Test parsing standard Claude CLI output format."""
        output = json.dumps(
            {
                "session_id": "sess-123",
                "message": {
                    "content": [
                        {"type": "text", "text": "Hello, "},
                        {"type": "text", "text": "world!"},
                    ]
                },
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        )

        response = provider.parse_json_output(output)

        assert response.text == "Hello, world!"
        assert response.session_id == "sess-123"
        assert response.usage == {"input_tokens": 10, "output_tokens": 5}

    def test_parse_sessionId_field(self, provider: ClaudeCliProvider) -> None:
        """Test parsing with camelCase sessionId field."""
        output = json.dumps(
            {
                "sessionId": "camel-case-id",
                "content": "Direct content",
            }
        )

        response = provider.parse_json_output(output)
        assert response.session_id == "camel-case-id"
        assert response.text == "Direct content"

    def test_parse_conversation_id_field(self, provider: ClaudeCliProvider) -> None:
        """Test parsing with conversation_id field."""
        output = json.dumps(
            {
                "conversation_id": "conv-id",
                "result": "Result text",
            }
        )

        response = provider.parse_json_output(output)
        assert response.session_id == "conv-id"
        assert response.text == "Result text"

    def test_parse_direct_text_field(self, provider: ClaudeCliProvider) -> None:
        """Test parsing with direct text field."""
        output = json.dumps(
            {
                "text": "Direct text content",
            }
        )

        response = provider.parse_json_output(output)
        assert response.text == "Direct text content"

    def test_parse_message_content_string(self, provider: ClaudeCliProvider) -> None:
        """Test parsing when message.content is a string."""
        output = json.dumps(
            {
                "message": {
                    "content": "String content"
                }
            }
        )

        response = provider.parse_json_output(output)
        assert response.text == "String content"

    def test_parse_content_array_without_type(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test parsing content array without type field."""
        output = json.dumps(
            {
                "content": [
                    {"text": "Part 1"},
                    {"text": "Part 2"},
                ]
            }
        )

        response = provider.parse_json_output(output)
        assert response.text == "Part 1Part 2"

    def test_parse_empty_usage(self, provider: ClaudeCliProvider) -> None:
        """Test parsing with empty usage object."""
        output = json.dumps(
            {
                "text": "Hello",
                "usage": {},
            }
        )

        response = provider.parse_json_output(output)
        assert response.usage is None

    def test_parse_usage_with_total_tokens(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test parsing usage with total_tokens field."""
        output = json.dumps(
            {
                "text": "Hello",
                "usage": {
                    "input_tokens": 5,
                    "output_tokens": 3,
                    "total_tokens": 8,
                },
            }
        )

        response = provider.parse_json_output(output)
        assert response.usage == {
            "input_tokens": 5,
            "output_tokens": 3,
            "total_tokens": 8,
        }

    def test_parse_filters_zero_usage(self, provider: ClaudeCliProvider) -> None:
        """Test that zero token counts are filtered from usage."""
        output = json.dumps(
            {
                "text": "Hello",
                "usage": {
                    "input_tokens": 0,
                    "output_tokens": 5,
                },
            }
        )

        response = provider.parse_json_output(output)
        assert response.usage == {"output_tokens": 5}

    def test_parse_empty_output_raises(self, provider: ClaudeCliProvider) -> None:
        """Test that empty output raises error."""
        with pytest.raises(ClaudeCliError) as exc_info:
            provider.parse_json_output("")

        assert "Empty response" in str(exc_info.value)

    def test_parse_whitespace_output_raises(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test that whitespace-only output raises error."""
        with pytest.raises(ClaudeCliError) as exc_info:
            provider.parse_json_output("   \n\t  ")

        assert "Empty response" in str(exc_info.value)

    def test_parse_invalid_json_raises(self, provider: ClaudeCliProvider) -> None:
        """Test that invalid JSON raises error."""
        with pytest.raises(ClaudeCliError) as exc_info:
            provider.parse_json_output("not valid json {{{")

        assert "Failed to parse" in str(exc_info.value)

    def test_parse_non_object_raises(self, provider: ClaudeCliProvider) -> None:
        """Test that non-object JSON raises error."""
        with pytest.raises(ClaudeCliError) as exc_info:
            provider.parse_json_output('"just a string"')

        assert "Expected JSON object" in str(exc_info.value)

    def test_parse_array_raises(self, provider: ClaudeCliProvider) -> None:
        """Test that array JSON raises error."""
        with pytest.raises(ClaudeCliError) as exc_info:
            provider.parse_json_output('[1, 2, 3]')

        assert "Expected JSON object" in str(exc_info.value)


class TestSessionManagement:
    """Tests for session management methods."""

    @pytest.fixture
    def provider(self) -> ClaudeCliProvider:
        """Create provider instance."""
        return ClaudeCliProvider()

    def test_get_session_id_returns_none_for_unknown(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test get_session_id returns None for unknown key."""
        assert provider.get_session_id("unknown-key") is None

    def test_store_and_retrieve_session(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test storing and retrieving session ID."""
        provider.store_session_id("user-123", "cli-session-abc")

        assert provider.get_session_id("user-123") == "cli-session-abc"

    def test_clear_session(self, provider: ClaudeCliProvider) -> None:
        """Test clearing a specific session."""
        provider.store_session_id("user-123", "session-abc")
        provider.store_session_id("user-456", "session-def")

        provider.clear_session("user-123")

        assert provider.get_session_id("user-123") is None
        assert provider.get_session_id("user-456") == "session-def"

    def test_clear_nonexistent_session(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test clearing nonexistent session doesn't raise."""
        provider.clear_session("nonexistent")  # Should not raise

    def test_clear_all_sessions(self, provider: ClaudeCliProvider) -> None:
        """Test clearing all sessions."""
        provider.store_session_id("user-1", "session-1")
        provider.store_session_id("user-2", "session-2")
        provider.store_session_id("user-3", "session-3")

        provider.clear_all_sessions()

        assert provider.get_session_id("user-1") is None
        assert provider.get_session_id("user-2") is None
        assert provider.get_session_id("user-3") is None


class TestComplete:
    """Tests for complete method."""

    @pytest.fixture
    def provider(self, tmp_path: Path) -> ClaudeCliProvider:
        """Create provider with temp credentials path."""
        creds_path = tmp_path / ".claude" / ".credentials.json"
        return ClaudeCliProvider(credentials_path=creds_path)

    @pytest.mark.asyncio
    async def test_complete_success_new_session(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test successful completion for new session."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(
                json.dumps(
                    {
                        "session_id": "new-session-id",
                        "message": {"content": [{"type": "text", "text": "Hello!"}]},
                    }
                ).encode(),
                b"",
            )
        )

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            response = await provider.complete(
                prompt="Hi there",
                token="test-token",
                session_key="user-123",
                system_prompt="Be helpful",
            )

            assert response.text == "Hello!"
            assert response.session_id == "new-session-id"
            assert provider.get_session_id("user-123") == "new-session-id"

    @pytest.mark.asyncio
    async def test_complete_success_resume_session(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test successful completion resuming existing session."""
        # Pre-store a session
        provider.store_session_id("user-123", "existing-session")

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(
                json.dumps(
                    {
                        "session_id": "existing-session",
                        "text": "Continuing conversation",
                    }
                ).encode(),
                b"",
            )
        )

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ) as mock_exec:
            response = await provider.complete(
                prompt="Continue",
                token="test-token",
                session_key="user-123",
            )

            assert response.text == "Continuing conversation"

            # Verify --resume was used
            call_args = mock_exec.call_args[0]
            assert "--resume" in call_args
            assert "existing-session" in call_args
            assert "--model" not in call_args

    @pytest.mark.asyncio
    async def test_complete_timeout(self, provider: ClaudeCliProvider) -> None:
        """Test handling of timeout."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            with pytest.raises(ClaudeCliTimeoutError) as exc_info:
                await provider.complete(
                    prompt="Hello",
                    token="test-token",
                    session_key="user-123",
                    timeout_seconds=5,
                )

            assert exc_info.value.timeout_seconds == 5

    @pytest.mark.asyncio
    async def test_complete_cli_error(self, provider: ClaudeCliProvider) -> None:
        """Test handling of CLI error exit code."""
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error: Invalid token")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            with pytest.raises(ClaudeCliError) as exc_info:
                await provider.complete(
                    prompt="Hello",
                    token="bad-token",
                    session_key="user-123",
                )

            assert exc_info.value.exit_code == 1
            assert "Invalid token" in exc_info.value.stderr

    @pytest.mark.asyncio
    async def test_complete_os_error(self, provider: ClaudeCliProvider) -> None:
        """Test handling of OS error when spawning process."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=OSError("Command not found"),
        ):
            with pytest.raises(ClaudeCliError) as exc_info:
                await provider.complete(
                    prompt="Hello",
                    token="test-token",
                    session_key="user-123",
                )

            assert "Failed to execute" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_custom_model(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test completion with custom model."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(json.dumps({"text": "OK"}).encode(), b"")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ) as mock_exec:
            await provider.complete(
                prompt="Hello",
                token="test-token",
                session_key="user-123",
                model="claude-sonnet-4-5",
            )

            call_args = mock_exec.call_args[0]
            # Should be normalized to "sonnet"
            model_index = list(call_args).index("--model")
            assert call_args[model_index + 1] == "sonnet"

    @pytest.mark.asyncio
    async def test_complete_env_cleared(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test that environment has API keys cleared."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(json.dumps({"text": "OK"}).encode(), b"")
        )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "should-be-cleared"}):
            with patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
            ) as mock_exec:
                await provider.complete(
                    prompt="Hello",
                    token="test-token",
                    session_key="user-123",
                )

                # Check the env kwarg
                call_kwargs = mock_exec.call_args[1]
                env = call_kwargs.get("env", {})
                assert "ANTHROPIC_API_KEY" not in env

    @pytest.mark.asyncio
    async def test_complete_credentials_written(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test that credentials file is written."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(json.dumps({"text": "OK"}).encode(), b"")
        )

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            await provider.complete(
                prompt="Hello",
                token="my-oauth-token",
                session_key="user-123",
            )

            assert provider.credentials_path.exists()
            content = json.loads(provider.credentials_path.read_text())
            assert content["claudeAiOauth"]["accessToken"] == "my-oauth-token"


class TestExtractMethods:
    """Tests for private extraction methods."""

    @pytest.fixture
    def provider(self) -> ClaudeCliProvider:
        """Create provider instance."""
        return ClaudeCliProvider()

    def test_extract_session_id_empty_string(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test that empty string session_id returns None."""
        result = provider._extract_session_id({"session_id": ""})
        assert result is None

    def test_extract_session_id_whitespace_only(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test that whitespace-only session_id returns None."""
        result = provider._extract_session_id({"session_id": "   "})
        assert result is None

    def test_extract_text_empty_data(self, provider: ClaudeCliProvider) -> None:
        """Test extracting text from empty data returns empty string."""
        result = provider._extract_text({})
        assert result == ""

    def test_extract_text_filters_non_text_content(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test that non-text content blocks are filtered."""
        data = {
            "message": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "tool_use", "name": "some_tool"},
                    {"type": "text", "text": " World"},
                ]
            }
        }
        result = provider._extract_text(data)
        assert result == "Hello World"

    def test_extract_usage_non_dict(self, provider: ClaudeCliProvider) -> None:
        """Test extract_usage with non-dict usage field."""
        result = provider._extract_usage({"usage": "not a dict"})
        assert result is None

    def test_extract_usage_negative_values(
        self,
        provider: ClaudeCliProvider,
    ) -> None:
        """Test that negative token counts are filtered."""
        result = provider._extract_usage({"usage": {"input_tokens": -5}})
        assert result is None
