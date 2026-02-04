"""
Claude CLI Provider for EchoMind.

Uses Claude Code CLI with Max subscription OAuth token for flat-rate pricing.
This provider executes the Claude CLI as a subprocess and parses JSON output.

Key characteristics:
- Non-streaming: Returns complete response (not token-by-token)
- Session-aware: Maintains conversation context via CLI session IDs
- OAuth-based: Uses Max subscription token instead of API key

Verified against: Moltbot CLI Runner implementation
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default credential file path (Claude CLI standard location)
DEFAULT_CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"

# Model aliases accepted by Claude CLI (verified from Moltbot cli-backends.ts)
MODEL_ALIASES: dict[str, str] = {
    "opus": "opus",
    "opus-4.5": "opus",
    "opus-4": "opus",
    "claude-opus-4-5": "opus",
    "claude-opus-4": "opus",
    "sonnet": "sonnet",
    "sonnet-4.5": "sonnet",
    "sonnet-4.1": "sonnet",
    "sonnet-4.0": "sonnet",
    "claude-sonnet-4-5": "sonnet",
    "claude-sonnet-4-1": "sonnet",
    "claude-sonnet-4-0": "sonnet",
    "haiku": "haiku",
    "haiku-3.5": "haiku",
    "claude-haiku-3-5": "haiku",
}

# Environment variables to clear (forces OAuth usage)
ENV_KEYS_TO_CLEAR = ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY_OLD")

# Default timeout for CLI execution
DEFAULT_TIMEOUT_SECONDS = 300

# Tool disabling instruction (always appended to system prompt)
TOOLS_DISABLED_INSTRUCTION = "Tools are disabled in this session. Do not call tools."


class ClaudeCliError(Exception):
    """
    Base exception for Claude CLI errors.

    Attributes:
        message: Human-readable error message.
        exit_code: CLI process exit code, if available.
        stderr: CLI stderr output, if available.
    """

    def __init__(
        self,
        message: str,
        exit_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        """
        Initialize Claude CLI error.

        Args:
            message: Human-readable error message.
            exit_code: CLI process exit code.
            stderr: CLI stderr output.
        """
        self.message = message
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(message)


class ClaudeCliTimeoutError(ClaudeCliError):
    """Raised when CLI execution exceeds timeout."""

    def __init__(self, timeout_seconds: int) -> None:
        """
        Initialize timeout error.

        Args:
            timeout_seconds: The timeout value that was exceeded.
        """
        super().__init__(
            message=f"Claude CLI execution timed out after {timeout_seconds}s",
        )
        self.timeout_seconds = timeout_seconds


class ClaudeCliCredentialsError(ClaudeCliError):
    """Raised when credential file operations fail."""

    pass


@dataclass(frozen=True)
class ClaudeCliResponse:
    """
    Response from Claude CLI execution.

    Attributes:
        text: The generated text content.
        session_id: CLI session ID for conversation continuity.
        usage: Token usage statistics, if available.
    """

    text: str
    session_id: str | None = None
    usage: dict[str, int] | None = None


@dataclass(frozen=True)
class ClaudeCliConfig:
    """
    Configuration for Claude CLI execution.

    Attributes:
        model: Model alias (opus, sonnet, haiku).
        timeout_seconds: Maximum execution time.
        credentials_path: Path to credentials file.
    """

    model: str = "opus"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    credentials_path: Path = DEFAULT_CREDENTIALS_PATH


class ClaudeCliProvider:
    """
    Provider for Claude CLI execution.

    This class handles:
    - Credential file management (write once, reuse)
    - Environment preparation (clear API keys for OAuth)
    - CLI argument construction (new session vs resume)
    - Subprocess execution with timeout
    - JSON output parsing
    - Session tracking per user

    Thread Safety:
        Session tracking uses a dict which is not thread-safe.
        For concurrent use, consider external session storage.

    Example:
        >>> provider = ClaudeCliProvider()
        >>> response = await provider.complete(
        ...     prompt="Hello, Claude!",
        ...     token="sk-ant-oat01-...",
        ...     session_key="user-123",
        ... )
        >>> print(response.text)
    """

    def __init__(
        self,
        config: ClaudeCliConfig | None = None,
        credentials_path: Path | None = None,
    ) -> None:
        """
        Initialize Claude CLI provider.

        Args:
            config: Provider configuration. Uses defaults if not provided.
            credentials_path: Override credentials file path. Takes precedence
                over config.credentials_path if both are provided.
        """
        self._config = config or ClaudeCliConfig()
        self._credentials_path = credentials_path or self._config.credentials_path
        self._sessions: dict[str, str] = {}
        self._credentials_written = False

    @property
    def credentials_path(self) -> Path:
        """Get the credentials file path."""
        return self._credentials_path

    def normalize_model(self, model: str) -> str:
        """
        Normalize model identifier to CLI alias.

        Args:
            model: Model identifier from configuration.

        Returns:
            Normalized model alias (opus, sonnet, or haiku).

        Example:
            >>> provider.normalize_model("claude-opus-4-5")
            'opus'
            >>> provider.normalize_model("sonnet-4.1")
            'sonnet'
        """
        trimmed = model.strip().lower()
        return MODEL_ALIASES.get(trimmed, trimmed)

    def ensure_credentials_file(self, token: str) -> None:
        """
        Ensure credentials file exists with the provided token.

        This method implements a write-once pattern:
        - First call: Creates credentials file with token
        - Subsequent calls: Verifies file exists, rewrites only if token differs

        Args:
            token: OAuth access token from database.

        Raises:
            ClaudeCliCredentialsError: If unable to create or write credentials file.
        """
        credentials_dir = self._credentials_path.parent

        # Create directory if it doesn't exist
        try:
            credentials_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ClaudeCliCredentialsError(
                f"Failed to create credentials directory {credentials_dir}: {e}"
            ) from e

        # Check if file exists with matching token
        if self._credentials_path.exists():
            try:
                existing = json.loads(self._credentials_path.read_text())
                existing_token = existing.get("claudeAiOauth", {}).get("accessToken")
                if existing_token == token:
                    logger.debug(
                        "✅ Credentials file exists with matching token at %s",
                        self._credentials_path,
                    )
                    self._credentials_written = True
                    return
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(
                    "😱 Failed to read existing credentials file, will rewrite: %s",
                    e,
                )

        # Write new credentials file
        # Token is valid for 1 year, set expiry to ~11 months from now
        import time

        expires_at = int((time.time() + 330 * 24 * 3600) * 1000)
        credentials = {
            "claudeAiOauth": {
                "accessToken": token,
                "refreshToken": None,
                "expiresAt": expires_at,
            }
        }

        try:
            self._credentials_path.write_text(json.dumps(credentials, indent=2))
            self._credentials_path.chmod(0o600)  # Secure permissions
            self._credentials_written = True
            logger.info("✅ Wrote credentials file to %s", self._credentials_path)
        except OSError as e:
            raise ClaudeCliCredentialsError(
                f"Failed to write credentials file {self._credentials_path}: {e}"
            ) from e

    def prepare_environment(self) -> dict[str, str]:
        """
        Prepare environment variables for CLI subprocess.

        Clears ANTHROPIC_API_KEY and related variables to force OAuth usage.
        The Claude CLI checks for API keys first; clearing them ensures
        it falls back to the OAuth token in credentials file.

        Returns:
            Environment variables dict with API keys removed.
        """
        env = os.environ.copy()
        for key in ENV_KEYS_TO_CLEAR:
            env.pop(key, None)
        return env

    def build_arguments(
        self,
        prompt: str,
        model: str,
        session_id: str | None,
        is_resume: bool,
        system_prompt: str | None,
    ) -> list[str]:
        """
        Build CLI arguments based on session state.

        Two modes of operation (verified from Moltbot cli-backends.ts):
        1. New session: Includes --model, --session-id, --append-system-prompt
        2. Resume: Only --resume flag with session ID (no model/system prompt)

        Args:
            prompt: User prompt text.
            model: Normalized model alias.
            session_id: Session ID for continuity.
            is_resume: True if resuming an existing session.
            system_prompt: System prompt (only used on first message).

        Returns:
            List of CLI arguments including the command.
        """
        args = [
            "claude",
            "-p",  # Print mode (non-interactive)
            "--output-format", "json",  # JSON output for parsing
            "--dangerously-skip-permissions",  # Skip tool permissions
        ]

        if is_resume and session_id:
            # Resume mode: only --resume and prompt
            args.extend(["--resume", session_id])
        else:
            # New session mode: include model, session-id, system prompt
            args.extend(["--model", model])

            if session_id:
                args.extend(["--session-id", session_id])

            if system_prompt:
                # Append tool disabling instruction
                full_system = f"{system_prompt}\n\n{TOOLS_DISABLED_INSTRUCTION}"
                args.extend(["--append-system-prompt", full_system])
            else:
                # Even without system prompt, disable tools
                args.extend(["--append-system-prompt", TOOLS_DISABLED_INSTRUCTION])

        # Prompt is always the last argument
        args.append(prompt)
        return args

    def parse_json_output(self, stdout: str) -> ClaudeCliResponse:
        """
        Parse Claude CLI JSON output.

        Expected JSON structure (from Claude CLI):
        {
            "session_id": "...",
            "message": {
                "content": [{"type": "text", "text": "..."}]
            },
            "usage": {"input_tokens": N, "output_tokens": M}
        }

        Args:
            stdout: Raw stdout from CLI process.

        Returns:
            Parsed response with text and session ID.

        Raises:
            ClaudeCliError: If JSON parsing fails or structure is unexpected.
        """
        trimmed = stdout.strip()
        if not trimmed:
            raise ClaudeCliError("Empty response from Claude CLI")

        try:
            data = json.loads(trimmed)
        except json.JSONDecodeError as e:
            raise ClaudeCliError(
                f"Failed to parse CLI output as JSON: {e}",
            ) from e

        if not isinstance(data, dict):
            raise ClaudeCliError(
                f"Expected JSON object, got {type(data).__name__}",
            )

        # Extract session ID (multiple field names supported)
        session_id = self._extract_session_id(data)

        # Extract text content (handle nested structures)
        text = self._extract_text(data)

        # Extract usage if present
        usage = self._extract_usage(data)

        return ClaudeCliResponse(
            text=text,
            session_id=session_id,
            usage=usage,
        )

    def _extract_session_id(self, data: dict[str, Any]) -> str | None:
        """
        Extract session ID from response data.

        Args:
            data: Parsed JSON response.

        Returns:
            Session ID string or None if not found.
        """
        for field in ("session_id", "sessionId", "conversation_id", "conversationId"):
            value = data.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _extract_text(self, data: dict[str, Any]) -> str:
        """
        Extract text content from nested response structure.

        Handles multiple response formats:
        - message.content (array of content blocks)
        - content (direct string or array)
        - result (direct string)

        Args:
            data: Parsed JSON response.

        Returns:
            Extracted text content.
        """
        # Try message.content (standard Claude format)
        if "message" in data and isinstance(data["message"], dict):
            msg = data["message"]
            if "content" in msg:
                content = msg["content"]
                if isinstance(content, list):
                    return "".join(
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict) and item.get("type") == "text"
                    )
                if isinstance(content, str):
                    return content

        # Try direct content field
        if "content" in data:
            content = data["content"]
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict)
                )

        # Try result field
        if "result" in data and isinstance(data["result"], str):
            return data["result"]

        # Try direct text field
        if "text" in data and isinstance(data["text"], str):
            return data["text"]

        return ""

    def _extract_usage(self, data: dict[str, Any]) -> dict[str, int] | None:
        """
        Extract token usage from response data.

        Args:
            data: Parsed JSON response.

        Returns:
            Usage dict with input_tokens and output_tokens, or None.
        """
        if "usage" not in data or not isinstance(data["usage"], dict):
            return None

        usage = data["usage"]
        result: dict[str, int] = {}

        for key in ("input_tokens", "output_tokens", "total_tokens"):
            if key in usage and isinstance(usage[key], int) and usage[key] > 0:
                result[key] = usage[key]

        return result if result else None

    def get_session_id(self, session_key: str) -> str | None:
        """
        Get stored CLI session ID for a session key.

        Args:
            session_key: Application session identifier (e.g., user ID or chat ID).

        Returns:
            CLI session ID if exists, None otherwise.
        """
        return self._sessions.get(session_key)

    def store_session_id(self, session_key: str, cli_session_id: str) -> None:
        """
        Store CLI session ID for a session key.

        Args:
            session_key: Application session identifier.
            cli_session_id: CLI session ID from response.
        """
        self._sessions[session_key] = cli_session_id

    def clear_session(self, session_key: str) -> None:
        """
        Clear stored session for a session key.

        Args:
            session_key: Application session identifier.
        """
        self._sessions.pop(session_key, None)
        logger.info("🗑️ Cleared CLI session for key: %s", session_key)

    def clear_all_sessions(self) -> None:
        """Clear all stored sessions."""
        count = len(self._sessions)
        self._sessions.clear()
        logger.info("🗑️ Cleared %d CLI sessions", count)

    async def complete(
        self,
        prompt: str,
        token: str,
        session_key: str,
        system_prompt: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> ClaudeCliResponse:
        """
        Generate completion using Claude CLI.

        Workflow:
        1. Ensure credentials file exists with token
        2. Check for existing CLI session (determines new vs resume)
        3. Build appropriate CLI arguments
        4. Execute subprocess with timeout
        5. Parse JSON response
        6. Store session ID for future requests

        Args:
            prompt: User prompt text.
            token: OAuth access token from database.
            session_key: Application session identifier for tracking CLI sessions.
            system_prompt: Optional system prompt (only used on first message).
            model: Model alias (defaults to config value).
            timeout_seconds: Execution timeout (defaults to config value).

        Returns:
            Response with generated text and session ID.

        Raises:
            ClaudeCliCredentialsError: If credential file operations fail.
            ClaudeCliTimeoutError: If execution exceeds timeout.
            ClaudeCliError: If CLI execution fails or output parsing fails.
        """
        # Ensure credentials file exists
        self.ensure_credentials_file(token)

        # Resolve configuration
        resolved_model = self.normalize_model(model or self._config.model)
        resolved_timeout = timeout_seconds or self._config.timeout_seconds

        # Determine session state
        existing_session = self.get_session_id(session_key)
        is_resume = existing_session is not None

        # Build CLI arguments
        args = self.build_arguments(
            prompt=prompt,
            model=resolved_model,
            session_id=existing_session,
            is_resume=is_resume,
            system_prompt=system_prompt if not is_resume else None,
        )

        logger.info(
            "🚀 Executing Claude CLI: model=%s, resume=%s, prompt_len=%d, session_key=%s",
            resolved_model,
            is_resume,
            len(prompt),
            session_key,
        )

        # Execute CLI subprocess
        env = self.prepare_environment()

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=resolved_timeout,
            )

        except asyncio.TimeoutError:
            logger.error(
                "❌ Claude CLI timed out after %ds for session_key=%s",
                resolved_timeout,
                session_key,
            )
            raise ClaudeCliTimeoutError(resolved_timeout)
        except OSError as e:
            logger.error("❌ Failed to execute Claude CLI: %s", e)
            raise ClaudeCliError(f"Failed to execute Claude CLI: {e}") from e

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # Check for CLI errors
        if process.returncode != 0:
            error_msg = stderr.strip() or stdout.strip() or "Unknown error"
            logger.error(
                "❌ Claude CLI failed with exit code %d: %s",
                process.returncode,
                error_msg[:500],
            )
            raise ClaudeCliError(
                message=f"Claude CLI failed: {error_msg[:200]}",
                exit_code=process.returncode,
                stderr=stderr,
            )

        # Parse response
        response = self.parse_json_output(stdout)

        # Store session ID for future requests
        if response.session_id:
            self.store_session_id(session_key, response.session_id)
            logger.debug(
                "📝 Stored CLI session %s for key %s",
                response.session_id,
                session_key,
            )

        logger.info(
            "✅ Claude CLI completed: session_id=%s, response_len=%d",
            response.session_id,
            len(response.text),
        )

        return response
