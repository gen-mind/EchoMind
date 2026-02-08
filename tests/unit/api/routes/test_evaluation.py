"""
Unit tests for RAGAS batch evaluation endpoint.

Tests the batch evaluation route including Langfuse-disabled handling,
session filtering, user-assistant pair extraction, document context
gathering, and error tolerance.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.routes.evaluation import (
    BatchEvalRequest,
    BatchEvalResponse,
    run_batch_evaluation,
)


def _make_session(
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    message_count: int = 5,
) -> MagicMock:
    """Create a mock ChatSession ORM object.

    Args:
        session_id: Session UUID.
        user_id: User UUID.
        message_count: Number of messages in session.

    Returns:
        MagicMock configured as a ChatSession.
    """
    session = MagicMock()
    session.id = session_id or uuid.uuid4()
    session.user_id = user_id or uuid.uuid4()
    session.message_count = message_count
    return session


def _make_message(role: str, content: str, msg_id: uuid.UUID | None = None) -> MagicMock:
    """Create a mock ChatMessage ORM object.

    Args:
        role: Message role ("user" or "assistant").
        content: Message content text.
        msg_id: Optional message UUID.

    Returns:
        MagicMock configured as a ChatMessage.
    """
    msg = MagicMock()
    msg.id = msg_id or uuid.uuid4()
    msg.role = role
    msg.content = content
    return msg


def _make_doc_link(document_id: uuid.UUID) -> MagicMock:
    """Create a mock ChatMessageDocument ORM object.

    Args:
        document_id: Document UUID.

    Returns:
        MagicMock configured as a ChatMessageDocument.
    """
    link = MagicMock()
    link.document_id = document_id
    return link


def _make_document(doc_id: uuid.UUID, title: str) -> MagicMock:
    """Create a mock Document ORM object.

    Args:
        doc_id: Document UUID.
        title: Document title.

    Returns:
        MagicMock configured as a Document.
    """
    doc = MagicMock()
    doc.id = doc_id
    doc.title = title
    return doc


def _make_admin_user() -> MagicMock:
    """Create a mock admin TokenUser.

    Returns:
        MagicMock configured as an admin user.
    """
    user = MagicMock()
    user.id = uuid.uuid4()
    user.roles = ["admin"]
    return user


class TestBatchEvalRequest:
    """Tests for BatchEvalRequest model validation."""

    def test_default_values(self) -> None:
        """Defaults to limit=50, min_messages=2."""
        req = BatchEvalRequest()
        assert req.limit == 50
        assert req.min_messages == 2

    def test_custom_values(self) -> None:
        """Accepts custom limit and min_messages."""
        req = BatchEvalRequest(limit=100, min_messages=4)
        assert req.limit == 100
        assert req.min_messages == 4

    def test_limit_min_validation(self) -> None:
        """Rejects limit below 1."""
        with pytest.raises(Exception):
            BatchEvalRequest(limit=0)

    def test_limit_max_validation(self) -> None:
        """Rejects limit above 500."""
        with pytest.raises(Exception):
            BatchEvalRequest(limit=501)

    def test_min_messages_validation(self) -> None:
        """Rejects min_messages below 2."""
        with pytest.raises(Exception):
            BatchEvalRequest(min_messages=1)


class TestBatchEvalResponse:
    """Tests for BatchEvalResponse model."""

    def test_default_values(self) -> None:
        """All counters default to 0."""
        resp = BatchEvalResponse()
        assert resp.evaluated == 0
        assert resp.skipped == 0
        assert resp.errors == 0

    def test_custom_values(self) -> None:
        """Accepts custom counter values."""
        resp = BatchEvalResponse(evaluated=10, skipped=5, errors=2)
        assert resp.evaluated == 10
        assert resp.skipped == 5
        assert resp.errors == 2


class TestRunBatchEvaluation:
    """Tests for run_batch_evaluation endpoint."""

    @pytest.mark.asyncio
    async def test_returns_skipped_when_langfuse_disabled(self) -> None:
        """Returns all sessions as skipped when Langfuse is disabled."""
        with patch(
            "api.routes.evaluation.is_langfuse_enabled",
            return_value=False,
        ):
            result = await run_batch_evaluation(
                request=BatchEvalRequest(limit=25),
                user=_make_admin_user(),
                db=AsyncMock(),
            )

            assert result.skipped == 25
            assert result.evaluated == 0
            assert result.errors == 0

    @pytest.mark.asyncio
    async def test_evaluates_sessions_with_valid_pairs(self) -> None:
        """Evaluates sessions that have user-assistant message pairs."""
        session = _make_session()
        user_msg = _make_message("user", "What is AI?")
        assistant_msg = _make_message("assistant", "AI is artificial intelligence.")
        doc_id = uuid.uuid4()
        doc_link = _make_doc_link(doc_id)
        doc = _make_document(doc_id, "AI Overview")

        mock_trace = MagicMock()
        mock_trace.id = "trace_123"

        mock_eval_result = MagicMock()  # Truthy → counts as evaluated

        # Build db mock that returns different results for each execute call
        db = AsyncMock()
        sessions_result = MagicMock()
        sessions_result.scalars.return_value.all.return_value = [session]

        # Messages returned in DESC order (newest first), code calls .reverse()
        messages_result = MagicMock()
        messages_result.scalars.return_value.all.return_value = [assistant_msg, user_msg]

        doc_links_result = MagicMock()
        doc_links_result.scalars.return_value.all.return_value = [doc_link]

        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc

        db.execute = AsyncMock(
            side_effect=[sessions_result, messages_result, doc_links_result, doc_result]
        )

        with (
            patch("api.routes.evaluation.is_langfuse_enabled", return_value=True),
            patch("api.routes.evaluation.create_trace", return_value=mock_trace),
            patch(
                "api.routes.evaluation.maybe_evaluate_async",
                new_callable=AsyncMock,
                return_value=mock_eval_result,
            ) as mock_eval,
        ):
            result = await run_batch_evaluation(
                request=BatchEvalRequest(limit=10),
                user=_make_admin_user(),
                db=db,
            )

            assert result.evaluated == 1
            assert result.skipped == 0
            assert result.errors == 0

            # Verify eval was called with correct args
            mock_eval.assert_called_once_with(
                trace_id="trace_123",
                query="What is AI?",
                response="AI is artificial intelligence.",
                contexts=["AI Overview"],
            )

    @pytest.mark.asyncio
    async def test_skips_session_without_user_message(self) -> None:
        """Skips sessions that only have assistant messages."""
        session = _make_session()
        assistant_msg = _make_message("assistant", "Hello!")

        db = AsyncMock()
        sessions_result = MagicMock()
        sessions_result.scalars.return_value.all.return_value = [session]

        messages_result = MagicMock()
        messages_result.scalars.return_value.all.return_value = [assistant_msg]

        db.execute = AsyncMock(side_effect=[sessions_result, messages_result])

        with patch("api.routes.evaluation.is_langfuse_enabled", return_value=True):
            result = await run_batch_evaluation(
                request=BatchEvalRequest(limit=10),
                user=_make_admin_user(),
                db=db,
            )

            assert result.skipped == 1
            assert result.evaluated == 0

    @pytest.mark.asyncio
    async def test_skips_session_without_assistant_response(self) -> None:
        """Skips sessions that only have user messages."""
        session = _make_session()
        user_msg = _make_message("user", "Hello?")

        db = AsyncMock()
        sessions_result = MagicMock()
        sessions_result.scalars.return_value.all.return_value = [session]

        messages_result = MagicMock()
        messages_result.scalars.return_value.all.return_value = [user_msg]

        db.execute = AsyncMock(side_effect=[sessions_result, messages_result])

        with patch("api.routes.evaluation.is_langfuse_enabled", return_value=True):
            result = await run_batch_evaluation(
                request=BatchEvalRequest(limit=10),
                user=_make_admin_user(),
                db=db,
            )

            assert result.skipped == 1
            assert result.evaluated == 0

    @pytest.mark.asyncio
    async def test_counts_error_on_session_exception(self) -> None:
        """Increments errors counter when session processing raises."""
        session = _make_session()

        db = AsyncMock()
        sessions_result = MagicMock()
        sessions_result.scalars.return_value.all.return_value = [session]

        # Simulate DB error when fetching messages
        db.execute = AsyncMock(
            side_effect=[sessions_result, RuntimeError("DB connection lost")]
        )

        with patch("api.routes.evaluation.is_langfuse_enabled", return_value=True):
            result = await run_batch_evaluation(
                request=BatchEvalRequest(limit=10),
                user=_make_admin_user(),
                db=db,
            )

            assert result.errors == 1
            assert result.evaluated == 0
            assert result.skipped == 0

    @pytest.mark.asyncio
    async def test_skips_session_when_eval_returns_none(self) -> None:
        """Counts session as skipped when maybe_evaluate_async returns None."""
        session = _make_session()
        user_msg = _make_message("user", "What is AI?")
        assistant_msg = _make_message("assistant", "AI is artificial intelligence.")

        mock_trace = MagicMock()
        mock_trace.id = "trace_456"

        db = AsyncMock()
        sessions_result = MagicMock()
        sessions_result.scalars.return_value.all.return_value = [session]

        # Messages in DESC order (newest first), code calls .reverse()
        messages_result = MagicMock()
        messages_result.scalars.return_value.all.return_value = [assistant_msg, user_msg]

        doc_links_result = MagicMock()
        doc_links_result.scalars.return_value.all.return_value = []  # No docs

        db.execute = AsyncMock(
            side_effect=[sessions_result, messages_result, doc_links_result]
        )

        with (
            patch("api.routes.evaluation.is_langfuse_enabled", return_value=True),
            patch("api.routes.evaluation.create_trace", return_value=mock_trace),
            patch(
                "api.routes.evaluation.maybe_evaluate_async",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await run_batch_evaluation(
                request=BatchEvalRequest(limit=10),
                user=_make_admin_user(),
                db=db,
            )

            assert result.skipped == 1
            assert result.evaluated == 0

    @pytest.mark.asyncio
    async def test_handles_no_sessions_found(self) -> None:
        """Returns all zeros when no sessions match criteria."""
        db = AsyncMock()
        sessions_result = MagicMock()
        sessions_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(return_value=sessions_result)

        with patch("api.routes.evaluation.is_langfuse_enabled", return_value=True):
            result = await run_batch_evaluation(
                request=BatchEvalRequest(limit=10),
                user=_make_admin_user(),
                db=db,
            )

            assert result.evaluated == 0
            assert result.skipped == 0
            assert result.errors == 0

    @pytest.mark.asyncio
    async def test_skips_documents_without_title(self) -> None:
        """Skips documents that have no title when building contexts."""
        session = _make_session()
        user_msg = _make_message("user", "Tell me about AI")
        assistant_msg = _make_message("assistant", "AI is cool")
        doc_id = uuid.uuid4()
        doc_link = _make_doc_link(doc_id)

        # Document with no title
        doc_no_title = MagicMock()
        doc_no_title.id = doc_id
        doc_no_title.title = None

        mock_trace = MagicMock()
        mock_trace.id = "trace_789"

        mock_eval_result = MagicMock()

        db = AsyncMock()
        sessions_result = MagicMock()
        sessions_result.scalars.return_value.all.return_value = [session]

        # Messages in DESC order (newest first), code calls .reverse()
        messages_result = MagicMock()
        messages_result.scalars.return_value.all.return_value = [assistant_msg, user_msg]

        doc_links_result = MagicMock()
        doc_links_result.scalars.return_value.all.return_value = [doc_link]

        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc_no_title

        db.execute = AsyncMock(
            side_effect=[sessions_result, messages_result, doc_links_result, doc_result]
        )

        with (
            patch("api.routes.evaluation.is_langfuse_enabled", return_value=True),
            patch("api.routes.evaluation.create_trace", return_value=mock_trace),
            patch(
                "api.routes.evaluation.maybe_evaluate_async",
                new_callable=AsyncMock,
                return_value=mock_eval_result,
            ) as mock_eval,
        ):
            result = await run_batch_evaluation(
                request=BatchEvalRequest(limit=10),
                user=_make_admin_user(),
                db=db,
            )

            assert result.evaluated == 1
            # Context should be empty (doc had no title)
            mock_eval.assert_called_once_with(
                trace_id="trace_789",
                query="Tell me about AI",
                response="AI is cool",
                contexts=[],
            )

    @pytest.mark.asyncio
    async def test_multiple_sessions_mixed_results(self) -> None:
        """Handles mix of evaluated, skipped, and errored sessions."""
        session1 = _make_session()  # Will evaluate
        session2 = _make_session()  # Will skip (no assistant)
        session3 = _make_session()  # Will error

        user_msg1 = _make_message("user", "Q1")
        assistant_msg1 = _make_message("assistant", "A1")
        user_msg2 = _make_message("user", "Q2")

        mock_trace = MagicMock()
        mock_trace.id = "trace_multi"
        mock_eval_result = MagicMock()

        db = AsyncMock()
        sessions_result = MagicMock()
        sessions_result.scalars.return_value.all.return_value = [session1, session2, session3]

        # Session 1: valid pair, no docs (DESC order — newest first)
        msgs1_result = MagicMock()
        msgs1_result.scalars.return_value.all.return_value = [assistant_msg1, user_msg1]
        docs1_result = MagicMock()
        docs1_result.scalars.return_value.all.return_value = []

        # Session 2: only user message
        msgs2_result = MagicMock()
        msgs2_result.scalars.return_value.all.return_value = [user_msg2]

        # Session 3: DB error
        db.execute = AsyncMock(
            side_effect=[
                sessions_result,
                msgs1_result,     # session1 messages
                docs1_result,     # session1 docs
                msgs2_result,     # session2 messages
                RuntimeError("DB crashed"),  # session3 messages
            ]
        )

        with (
            patch("api.routes.evaluation.is_langfuse_enabled", return_value=True),
            patch("api.routes.evaluation.create_trace", return_value=mock_trace),
            patch(
                "api.routes.evaluation.maybe_evaluate_async",
                new_callable=AsyncMock,
                return_value=mock_eval_result,
            ),
        ):
            result = await run_batch_evaluation(
                request=BatchEvalRequest(limit=10),
                user=_make_admin_user(),
                db=db,
            )

            assert result.evaluated == 1
            assert result.skipped == 1
            assert result.errors == 1

    @pytest.mark.asyncio
    async def test_creates_trace_with_correct_metadata(self) -> None:
        """Creates Langfuse trace with correct user_id, session_id, and tags."""
        session_id = uuid.uuid4()
        user_id = uuid.uuid4()
        session = _make_session(session_id=session_id, user_id=user_id)

        user_msg = _make_message("user", "Q")
        assistant_msg = _make_message("assistant", "A")

        mock_trace = MagicMock()
        mock_trace.id = "trace_meta"

        db = AsyncMock()
        sessions_result = MagicMock()
        sessions_result.scalars.return_value.all.return_value = [session]

        # Messages in DESC order (newest first), code calls .reverse()
        messages_result = MagicMock()
        messages_result.scalars.return_value.all.return_value = [assistant_msg, user_msg]

        doc_links_result = MagicMock()
        doc_links_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(
            side_effect=[sessions_result, messages_result, doc_links_result]
        )

        with (
            patch("api.routes.evaluation.is_langfuse_enabled", return_value=True),
            patch("api.routes.evaluation.create_trace", return_value=mock_trace) as mock_create,
            patch(
                "api.routes.evaluation.maybe_evaluate_async",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
        ):
            await run_batch_evaluation(
                request=BatchEvalRequest(limit=10),
                user=_make_admin_user(),
                db=db,
            )

            mock_create.assert_called_once_with(
                name="batch-evaluation",
                user_id=str(user_id),
                session_id=str(session_id),
                tags=["batch-eval"],
            )
