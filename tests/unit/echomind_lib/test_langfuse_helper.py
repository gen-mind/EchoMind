"""
Unit tests for Langfuse SDK helper.

Tests init/shutdown lifecycle, NoOp pattern, create_trace enabled/disabled,
score_trace, and error handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from echomind_lib.helpers import langfuse_helper
from echomind_lib.helpers.langfuse_helper import (
    _NoOpGeneration,
    _NoOpSpan,
    _NoOpTrace,
    create_trace,
    get_langfuse,
    init_langfuse,
    is_langfuse_enabled,
    score_trace,
    shutdown_langfuse,
)


@pytest.fixture(autouse=True)
def _reset_module_state() -> None:
    """Reset module-level state before each test."""
    langfuse_helper._langfuse_client = None
    langfuse_helper._enabled = False


class TestNoOpSpan:
    """Tests for _NoOpSpan no-op pattern."""

    def test_span_returns_noop_span(self) -> None:
        """span() returns another _NoOpSpan."""
        span = _NoOpSpan()
        child = span.span(name="child")
        assert isinstance(child, _NoOpSpan)

    def test_generation_returns_noop_generation(self) -> None:
        """generation() returns a _NoOpGeneration."""
        span = _NoOpSpan()
        gen = span.generation(name="gen")
        assert isinstance(gen, _NoOpGeneration)

    def test_event_returns_none(self) -> None:
        """event() returns None without error."""
        span = _NoOpSpan()
        result = span.event(name="test")
        assert result is None

    def test_score_returns_none(self) -> None:
        """score() returns None without error."""
        span = _NoOpSpan()
        result = span.score(name="test", value=0.5)
        assert result is None

    def test_end_returns_none(self) -> None:
        """end() returns None without error."""
        span = _NoOpSpan()
        result = span.end(output={"key": "value"})
        assert result is None

    def test_update_returns_self(self) -> None:
        """update() returns self for chaining."""
        span = _NoOpSpan()
        result = span.update(metadata={"key": "value"})
        assert result is span

    def test_trace_id_returns_empty_string(self) -> None:
        """trace_id property returns empty string."""
        span = _NoOpSpan()
        assert span.trace_id == ""


class TestNoOpGeneration:
    """Tests for _NoOpGeneration no-op pattern."""

    def test_end_returns_none(self) -> None:
        """end() returns None without error."""
        gen = _NoOpGeneration()
        result = gen.end(output="response", usage={"total_tokens": 10})
        assert result is None

    def test_update_returns_self(self) -> None:
        """update() returns self for chaining."""
        gen = _NoOpGeneration()
        result = gen.update(metadata={"key": "value"})
        assert result is gen


class TestNoOpTrace:
    """Tests for _NoOpTrace no-op pattern."""

    def test_id_returns_empty_string(self) -> None:
        """id property returns empty string."""
        trace = _NoOpTrace()
        assert trace.id == ""

    def test_inherits_span_methods(self) -> None:
        """_NoOpTrace inherits span/generation/event/score from _NoOpSpan."""
        trace = _NoOpTrace()
        assert isinstance(trace.span(name="test"), _NoOpSpan)
        assert isinstance(trace.generation(name="test"), _NoOpGeneration)
        assert trace.event(name="test") is None
        assert trace.score(name="test", value=0.5) is None

    def test_chained_calls_work(self) -> None:
        """NoOp pattern supports chained calls without error."""
        trace = _NoOpTrace()
        span = trace.span(name="retrieval", input={"query": "test"})
        span.end(output={"source_count": 5})
        gen = trace.generation(
            name="llm",
            model="gpt-4",
            input={"query": "test"},
        )
        gen.end(output="response text", usage={"total_tokens": 100})
        trace.update(metadata={"error": True})


class TestInitLangfuse:
    """Tests for init_langfuse()."""

    def test_disabled_when_no_public_key(self) -> None:
        """Returns False and stays disabled when LANGFUSE_PUBLIC_KEY is empty."""
        with patch.dict("os.environ", {}, clear=True):
            result = init_langfuse()
            assert result is False
            assert is_langfuse_enabled() is False
            assert get_langfuse() is None

    def test_disabled_when_no_secret_key(self) -> None:
        """Returns False when only public key is set."""
        with patch.dict(
            "os.environ",
            {"LANGFUSE_PUBLIC_KEY": "pk-test"},
            clear=True,
        ):
            result = init_langfuse()
            assert result is False
            assert is_langfuse_enabled() is False

    def test_enabled_when_keys_set(self) -> None:
        """Returns True and enables when both keys are set."""
        mock_client = MagicMock()
        with (
            patch.dict(
                "os.environ",
                {
                    "LANGFUSE_PUBLIC_KEY": "pk-test",
                    "LANGFUSE_SECRET_KEY": "sk-test",
                    "LANGFUSE_BASE_URL": "http://localhost:3000",
                },
                clear=True,
            ),
            patch(
                "echomind_lib.helpers.langfuse_helper.Langfuse",
                return_value=mock_client,
                create=True,
            ) as mock_cls,
        ):
            # Simulate the import inside init_langfuse
            with patch.dict(
                "sys.modules",
                {"langfuse": MagicMock(Langfuse=mock_cls)},
            ):
                result = init_langfuse()

                assert result is True
                assert is_langfuse_enabled() is True
                assert get_langfuse() is mock_client

    def test_handles_import_error(self) -> None:
        """Returns False gracefully when langfuse package not installed."""
        with patch.dict(
            "os.environ",
            {
                "LANGFUSE_PUBLIC_KEY": "pk-test",
                "LANGFUSE_SECRET_KEY": "sk-test",
            },
            clear=True,
        ):
            # Force ImportError on `from langfuse import Langfuse`
            import builtins

            original_import = builtins.__import__

            def mock_import(name: str, *args, **kwargs):
                if name == "langfuse":
                    raise ImportError("No module named 'langfuse'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = init_langfuse()
                assert result is False
                assert is_langfuse_enabled() is False

    def test_handles_initialization_error(self) -> None:
        """Returns False when Langfuse constructor raises."""
        with patch.dict(
            "os.environ",
            {
                "LANGFUSE_PUBLIC_KEY": "pk-test",
                "LANGFUSE_SECRET_KEY": "sk-test",
            },
            clear=True,
        ):
            mock_langfuse_module = MagicMock()
            mock_langfuse_module.Langfuse.side_effect = RuntimeError("Connection failed")

            import builtins

            original_import = builtins.__import__

            def mock_import(name: str, *args, **kwargs):
                if name == "langfuse":
                    return mock_langfuse_module
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = init_langfuse()
                assert result is False
                assert is_langfuse_enabled() is False


class TestShutdownLangfuse:
    """Tests for shutdown_langfuse()."""

    def test_shutdown_when_not_initialized(self) -> None:
        """Safe to call when never initialized."""
        shutdown_langfuse()
        assert is_langfuse_enabled() is False
        assert get_langfuse() is None

    def test_shutdown_flushes_and_closes(self) -> None:
        """Calls flush() and shutdown() on the client."""
        mock_client = MagicMock()
        langfuse_helper._langfuse_client = mock_client
        langfuse_helper._enabled = True

        shutdown_langfuse()

        mock_client.flush.assert_called_once()
        mock_client.shutdown.assert_called_once()
        assert is_langfuse_enabled() is False
        assert get_langfuse() is None

    def test_shutdown_handles_error_gracefully(self) -> None:
        """Cleans up state even when flush/shutdown raises."""
        mock_client = MagicMock()
        mock_client.flush.side_effect = RuntimeError("Network error")
        langfuse_helper._langfuse_client = mock_client
        langfuse_helper._enabled = True

        shutdown_langfuse()

        assert is_langfuse_enabled() is False
        assert get_langfuse() is None


class TestCreateTrace:
    """Tests for create_trace()."""

    def test_returns_noop_when_disabled(self) -> None:
        """Returns _NoOpTrace when Langfuse is disabled."""
        trace = create_trace(name="test-trace")
        assert isinstance(trace, _NoOpTrace)
        assert trace.id == ""

    def test_returns_noop_when_client_is_none(self) -> None:
        """Returns _NoOpTrace when enabled but client is None."""
        langfuse_helper._enabled = True
        langfuse_helper._langfuse_client = None

        trace = create_trace(name="test-trace")
        assert isinstance(trace, _NoOpTrace)

    def test_calls_client_trace_when_enabled(self) -> None:
        """Delegates to Langfuse client when enabled."""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_client.trace.return_value = mock_trace

        langfuse_helper._langfuse_client = mock_client
        langfuse_helper._enabled = True

        result = create_trace(
            name="chat-completion",
            user_id="user_1",
            session_id="session_1",
            metadata={"mode": "chat"},
            tags=["chat"],
        )

        assert result is mock_trace
        mock_client.trace.assert_called_once_with(
            name="chat-completion",
            user_id="user_1",
            session_id="session_1",
            metadata={"mode": "chat"},
            tags=["chat"],
        )

    def test_omits_none_optional_params(self) -> None:
        """Does not pass None values to client.trace()."""
        mock_client = MagicMock()
        mock_client.trace.return_value = MagicMock()

        langfuse_helper._langfuse_client = mock_client
        langfuse_helper._enabled = True

        create_trace(name="test")

        mock_client.trace.assert_called_once_with(name="test")

    def test_returns_noop_on_client_error(self) -> None:
        """Returns _NoOpTrace when client.trace() raises."""
        mock_client = MagicMock()
        mock_client.trace.side_effect = RuntimeError("API error")

        langfuse_helper._langfuse_client = mock_client
        langfuse_helper._enabled = True

        trace = create_trace(name="test")
        assert isinstance(trace, _NoOpTrace)


class TestScoreTrace:
    """Tests for score_trace()."""

    def test_noop_when_disabled(self) -> None:
        """Does nothing when Langfuse is disabled."""
        score_trace(trace_id="trace_1", name="faithfulness", value=0.95)
        # No error raised

    def test_noop_when_client_is_none(self) -> None:
        """Does nothing when enabled but client is None."""
        langfuse_helper._enabled = True
        langfuse_helper._langfuse_client = None

        score_trace(trace_id="trace_1", name="faithfulness", value=0.95)

    def test_calls_client_score_when_enabled(self) -> None:
        """Delegates to Langfuse client.score() when enabled."""
        mock_client = MagicMock()
        langfuse_helper._langfuse_client = mock_client
        langfuse_helper._enabled = True

        score_trace(
            trace_id="trace_1",
            name="faithfulness",
            value=0.95,
            comment="RAGAS faithfulness (automated)",
        )

        mock_client.score.assert_called_once_with(
            trace_id="trace_1",
            name="faithfulness",
            value=0.95,
            comment="RAGAS faithfulness (automated)",
        )

    def test_omits_none_comment(self) -> None:
        """Does not pass comment when it is None."""
        mock_client = MagicMock()
        langfuse_helper._langfuse_client = mock_client
        langfuse_helper._enabled = True

        score_trace(trace_id="trace_1", name="test", value=0.5)

        mock_client.score.assert_called_once_with(
            trace_id="trace_1",
            name="test",
            value=0.5,
        )

    def test_handles_error_gracefully(self) -> None:
        """Logs warning when client.score() raises, does not propagate."""
        mock_client = MagicMock()
        mock_client.score.side_effect = RuntimeError("API error")
        langfuse_helper._langfuse_client = mock_client
        langfuse_helper._enabled = True

        # Should not raise
        score_trace(trace_id="trace_1", name="test", value=0.5)
