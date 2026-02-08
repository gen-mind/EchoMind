"""
Langfuse SDK helper for EchoMind services.

Central module for initializing and managing the Langfuse Python SDK.
When Langfuse is not configured (no public key), all operations are no-ops
with zero runtime overhead.

Usage:
    from echomind_lib.helpers.langfuse_helper import (
        init_langfuse,
        shutdown_langfuse,
        create_trace,
        is_langfuse_enabled,
    )

    # At startup
    init_langfuse()

    # In request handler
    trace = create_trace(name="chat-completion", user_id="user_123")
    span = trace.span(name="retrieval")
    span.end(output={"source_count": 5})

    # At shutdown
    shutdown_langfuse()
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Module-level state
_langfuse_client: Any = None
_enabled: bool = False


class _NoOpSpan:
    """No-op span that silently ignores all calls when Langfuse is disabled."""

    def span(self, **kwargs: Any) -> "_NoOpSpan":
        """Create a child span (no-op).

        Args:
            **kwargs: Ignored span parameters.

        Returns:
            Another no-op span.
        """
        return _NoOpSpan()

    def generation(self, **kwargs: Any) -> "_NoOpGeneration":
        """Create a generation (no-op).

        Args:
            **kwargs: Ignored generation parameters.

        Returns:
            A no-op generation.
        """
        return _NoOpGeneration()

    def event(self, **kwargs: Any) -> None:
        """Record an event (no-op).

        Args:
            **kwargs: Ignored event parameters.
        """

    def score(self, **kwargs: Any) -> None:
        """Record a score (no-op).

        Args:
            **kwargs: Ignored score parameters.
        """

    def end(self, **kwargs: Any) -> None:
        """End the span (no-op).

        Args:
            **kwargs: Ignored end parameters.
        """

    def update(self, **kwargs: Any) -> "_NoOpSpan":
        """Update span metadata (no-op).

        Args:
            **kwargs: Ignored update parameters.

        Returns:
            Self for chaining.
        """
        return self

    @property
    def trace_id(self) -> str:
        """Get trace ID (no-op).

        Returns:
            Empty string.
        """
        return ""


class _NoOpGeneration:
    """No-op generation that silently ignores all calls."""

    def end(self, **kwargs: Any) -> None:
        """End the generation (no-op).

        Args:
            **kwargs: Ignored end parameters.
        """

    def update(self, **kwargs: Any) -> "_NoOpGeneration":
        """Update generation metadata (no-op).

        Args:
            **kwargs: Ignored update parameters.

        Returns:
            Self for chaining.
        """
        return self


class _NoOpTrace(_NoOpSpan):
    """No-op trace that silently ignores all calls when Langfuse is disabled."""

    @property
    def id(self) -> str:
        """Get trace ID (no-op).

        Returns:
            Empty string.
        """
        return ""


def init_langfuse() -> bool:
    """
    Initialize the Langfuse SDK from environment variables.

    Reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_BASE_URL
    from the environment. If keys are not set, Langfuse remains disabled.

    Returns:
        True if Langfuse was initialized successfully, False otherwise.
    """
    global _langfuse_client, _enabled

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    base_url = os.getenv("LANGFUSE_BASE_URL", "http://langfuse-web:3000")

    if not public_key or not secret_key:
        logger.info("📊 Langfuse disabled (no API keys configured)")
        _enabled = False
        return False

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=base_url,
            enabled=True,
        )
        _enabled = True
        logger.info(f"📊 Langfuse initialized (host: {base_url})")
        return True

    except ImportError:
        logger.warning("⚠️ Langfuse package not installed, tracing disabled")
        _enabled = False
        return False

    except Exception as e:
        logger.warning(f"⚠️ Langfuse initialization failed: {e}")
        _enabled = False
        return False


def shutdown_langfuse() -> None:
    """
    Flush pending events and shut down the Langfuse SDK.

    Safe to call even if Langfuse was never initialized.
    """
    global _langfuse_client, _enabled

    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            _langfuse_client.shutdown()
            logger.info("📊 Langfuse shut down")
        except Exception as e:
            logger.warning(f"⚠️ Langfuse shutdown error: {e}")
        finally:
            _langfuse_client = None
            _enabled = False


def is_langfuse_enabled() -> bool:
    """
    Check if Langfuse is active.

    Returns:
        True if Langfuse is initialized and enabled.
    """
    return _enabled


def get_langfuse() -> Any:
    """
    Get the Langfuse client instance.

    Returns:
        Langfuse client or None if not initialized.
    """
    return _langfuse_client


def create_trace(
    name: str,
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    **kwargs: Any,
) -> _NoOpTrace | Any:
    """
    Create a Langfuse trace.

    Returns a no-op trace when Langfuse is disabled, allowing calling code
    to use the same API without conditional checks.

    Args:
        name: Trace name (e.g., "chat-completion", "document-ingest").
        user_id: Optional user identifier.
        session_id: Optional session identifier.
        metadata: Optional metadata dictionary.
        tags: Optional list of tags.
        **kwargs: Additional trace parameters.

    Returns:
        Langfuse trace object or _NoOpTrace if disabled.
    """
    if not _enabled or _langfuse_client is None:
        return _NoOpTrace()

    try:
        trace_kwargs: dict[str, Any] = {"name": name, **kwargs}

        if user_id is not None:
            trace_kwargs["user_id"] = user_id
        if session_id is not None:
            trace_kwargs["session_id"] = session_id
        if metadata is not None:
            trace_kwargs["metadata"] = metadata
        if tags is not None:
            trace_kwargs["tags"] = tags

        return _langfuse_client.trace(**trace_kwargs)

    except Exception as e:
        logger.warning(f"⚠️ Failed to create Langfuse trace: {e}")
        return _NoOpTrace()


def score_trace(
    trace_id: str,
    name: str,
    value: float,
    comment: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Add a score to a Langfuse trace.

    No-op when Langfuse is disabled.

    Args:
        trace_id: ID of the trace to score.
        name: Score name (e.g., "faithfulness", "response_relevancy").
        value: Numeric score value (0.0 - 1.0).
        comment: Optional comment about the score.
        **kwargs: Additional score parameters.
    """
    if not _enabled or _langfuse_client is None:
        return

    try:
        score_kwargs: dict[str, Any] = {
            "trace_id": trace_id,
            "name": name,
            "value": value,
            **kwargs,
        }
        if comment is not None:
            score_kwargs["comment"] = comment

        _langfuse_client.score(**score_kwargs)

    except Exception as e:
        logger.warning(f"⚠️ Failed to score trace {trace_id}: {e}")
