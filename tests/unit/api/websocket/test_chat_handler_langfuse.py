"""
Unit tests for Langfuse integration in ChatHandler.

Tests trace creation, span hierarchy, generation recording,
and RAGAS evaluation task firing in _process_chat().
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.logic.chat_service import RetrievedSource
from api.websocket.chat_handler import ChatHandler, MessageType


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create mock database session."""
    db = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def mock_manager() -> MagicMock:
    """Create mock connection manager."""
    manager = MagicMock()
    manager.connect = AsyncMock()
    manager.disconnect = MagicMock()
    manager.send_to_user = AsyncMock()
    manager.subscribe = MagicMock()
    return manager


@pytest.fixture
def handler(mock_db: AsyncMock, mock_manager: MagicMock) -> ChatHandler:
    """Create ChatHandler with mocked dependencies."""
    return ChatHandler(db=mock_db, manager=mock_manager)


@pytest.fixture
def mock_user() -> MagicMock:
    """Create mock TokenUser."""
    user = MagicMock()
    user.id = 42
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_session() -> MagicMock:
    """Create mock chat session with assistant and LLM."""
    session = MagicMock()
    session.id = 1

    llm = MagicMock()
    llm.model_id = "llama-3-70b"
    llm.provider = "tgi"
    llm.temperature = 0.7
    llm.max_tokens = 2048
    llm.endpoint = "http://tgi:8080"
    llm.api_key = "test-key"

    assistant = MagicMock()
    assistant.llm = llm
    session.assistant = assistant

    return session


@pytest.fixture
def mock_sources() -> list[RetrievedSource]:
    """Create mock retrieved sources."""
    return [
        RetrievedSource(
            document_id=1,
            chunk_id="chunk_1",
            score=0.95,
            title="Test Document",
            content="Test content for retrieval.",
        ),
        RetrievedSource(
            document_id=2,
            chunk_id="chunk_2",
            score=0.85,
            title="Another Doc",
            content="More test content.",
        ),
    ]


class TestChatHandlerTraceCreation:
    """Tests for Langfuse trace creation in _process_chat()."""

    @pytest.mark.asyncio
    async def test_creates_trace_on_chat_start(
        self,
        handler: ChatHandler,
        mock_user: MagicMock,
        mock_session: MagicMock,
        mock_sources: list[RetrievedSource],
        mock_manager: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Verify create_trace is called with correct parameters."""
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_span = MagicMock()
        mock_trace.span.return_value = mock_span
        mock_gen = MagicMock()
        mock_trace.generation.return_value = mock_gen

        mock_user_msg = MagicMock()
        mock_user_msg.id = 10
        mock_assistant_msg = MagicMock()
        mock_assistant_msg.id = 11

        with (
            patch(
                "api.websocket.chat_handler.create_trace",
                return_value=mock_trace,
            ) as mock_create,
            patch(
                "api.websocket.chat_handler.get_qdrant",
                return_value=MagicMock(),
            ),
            patch(
                "api.websocket.chat_handler.get_embedder_client",
                return_value=AsyncMock(),
            ),
            patch(
                "api.websocket.chat_handler.get_llm_client",
                return_value=AsyncMock(),
            ),
            patch(
                "api.websocket.chat_handler.ChatService",
            ) as mock_service_cls,
            patch(
                "api.websocket.chat_handler.maybe_evaluate_async",
                new_callable=AsyncMock,
            ),
        ):
            service = mock_service_cls.return_value
            service.get_session = AsyncMock(return_value=mock_session)
            service.retrieve_context = AsyncMock(return_value=mock_sources)
            service.get_document_titles = AsyncMock(return_value={1: "Test Document", 2: "Another Doc"})
            service.save_user_message = AsyncMock(return_value=mock_user_msg)
            service.save_assistant_message = AsyncMock(return_value=mock_assistant_msg)

            # Simulate streaming with two tokens
            async def mock_stream(**kwargs):
                yield "Hello"
                yield " world"

            service.stream_response = mock_stream

            await handler._process_chat(mock_user, session_id=1, query="test query", mode="chat")

            mock_create.assert_called_once_with(
                name="chat-completion",
                user_id="42",
                session_id="1",
                metadata={"mode": "chat"},
                tags=["chat", "chat"],
            )

    @pytest.mark.asyncio
    async def test_trace_updated_on_error(
        self,
        handler: ChatHandler,
        mock_user: MagicMock,
        mock_manager: MagicMock,
    ) -> None:
        """Verify trace.update() is called with error metadata on exception."""
        mock_trace = MagicMock()
        mock_trace.id = "trace-err"

        with (
            patch(
                "api.websocket.chat_handler.create_trace",
                return_value=mock_trace,
            ),
            patch(
                "api.websocket.chat_handler.get_qdrant",
                return_value=MagicMock(),
            ),
            patch(
                "api.websocket.chat_handler.get_embedder_client",
                return_value=AsyncMock(),
            ),
            patch(
                "api.websocket.chat_handler.get_llm_client",
                return_value=AsyncMock(),
            ),
            patch(
                "api.websocket.chat_handler.ChatService",
                side_effect=RuntimeError("Service init failed"),
            ),
        ):
            await handler._process_chat(mock_user, session_id=1, query="test", mode="chat")

            mock_trace.update.assert_called_once()
            call_kwargs = mock_trace.update.call_args[1]
            assert call_kwargs["metadata"]["error"] is True
            assert "Service init failed" in call_kwargs["metadata"]["error_message"]


class TestChatHandlerRetrievalSpan:
    """Tests for retrieval span creation and tracking."""

    @pytest.mark.asyncio
    async def test_creates_retrieval_span(
        self,
        handler: ChatHandler,
        mock_user: MagicMock,
        mock_session: MagicMock,
        mock_sources: list[RetrievedSource],
        mock_manager: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Verify retrieval span is created with correct input and output."""
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_span = MagicMock()
        mock_trace.span.return_value = mock_span
        mock_gen = MagicMock()
        mock_trace.generation.return_value = mock_gen

        mock_user_msg = MagicMock()
        mock_user_msg.id = 10
        mock_assistant_msg = MagicMock()
        mock_assistant_msg.id = 11

        with (
            patch(
                "api.websocket.chat_handler.create_trace",
                return_value=mock_trace,
            ),
            patch("api.websocket.chat_handler.get_qdrant", return_value=MagicMock()),
            patch("api.websocket.chat_handler.get_embedder_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.get_llm_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.ChatService") as mock_service_cls,
            patch("api.websocket.chat_handler.maybe_evaluate_async", new_callable=AsyncMock),
        ):
            service = mock_service_cls.return_value
            service.get_session = AsyncMock(return_value=mock_session)
            service.retrieve_context = AsyncMock(return_value=mock_sources)
            service.get_document_titles = AsyncMock(return_value={})
            service.save_user_message = AsyncMock(return_value=mock_user_msg)
            service.save_assistant_message = AsyncMock(return_value=mock_assistant_msg)

            async def mock_stream(**kwargs):
                yield "token"

            service.stream_response = mock_stream

            await handler._process_chat(mock_user, session_id=1, query="search query", mode="chat")

            # Verify span created with retrieval name and input
            mock_trace.span.assert_called_once_with(
                name="retrieval",
                input={"query": "search query", "limit": 5, "min_score": 0.4},
            )

            # Verify span ended with output
            mock_span.end.assert_called_once()
            end_kwargs = mock_span.end.call_args[1]
            assert end_kwargs["output"]["source_count"] == 2
            assert len(end_kwargs["output"]["scores"]) == 2
            assert end_kwargs["output"]["scores"][0] == 0.95


class TestChatHandlerGenerationSpan:
    """Tests for LLM generation span creation and recording."""

    @pytest.mark.asyncio
    async def test_creates_generation_span(
        self,
        handler: ChatHandler,
        mock_user: MagicMock,
        mock_session: MagicMock,
        mock_sources: list[RetrievedSource],
        mock_manager: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Verify generation span records model, tokens, and elapsed time."""
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_span = MagicMock()
        mock_trace.span.return_value = mock_span
        mock_gen = MagicMock()
        mock_trace.generation.return_value = mock_gen

        mock_user_msg = MagicMock()
        mock_user_msg.id = 10
        mock_assistant_msg = MagicMock()
        mock_assistant_msg.id = 11

        with (
            patch("api.websocket.chat_handler.create_trace", return_value=mock_trace),
            patch("api.websocket.chat_handler.get_qdrant", return_value=MagicMock()),
            patch("api.websocket.chat_handler.get_embedder_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.get_llm_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.ChatService") as mock_service_cls,
            patch("api.websocket.chat_handler.maybe_evaluate_async", new_callable=AsyncMock),
        ):
            service = mock_service_cls.return_value
            service.get_session = AsyncMock(return_value=mock_session)
            service.retrieve_context = AsyncMock(return_value=mock_sources)
            service.get_document_titles = AsyncMock(return_value={})
            service.save_user_message = AsyncMock(return_value=mock_user_msg)
            service.save_assistant_message = AsyncMock(return_value=mock_assistant_msg)

            async def mock_stream(**kwargs):
                yield "Hello"
                yield " world"
                yield "!"

            service.stream_response = mock_stream

            await handler._process_chat(mock_user, session_id=1, query="test", mode="chat")

            # Verify generation created with model info
            mock_trace.generation.assert_called_once_with(
                name="llm-completion",
                model="llama-3-70b",
                input={"query": "test", "source_count": 2},
                metadata={
                    "provider": "tgi",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                },
            )

            # Verify generation ended with output and usage
            mock_gen.end.assert_called_once()
            end_kwargs = mock_gen.end.call_args[1]
            assert end_kwargs["output"] == "Hello world!"
            assert end_kwargs["usage"] == {"total_tokens": 3}
            assert "elapsed_seconds" in end_kwargs["metadata"]

    @pytest.mark.asyncio
    async def test_search_mode_skips_generation(
        self,
        handler: ChatHandler,
        mock_user: MagicMock,
        mock_session: MagicMock,
        mock_sources: list[RetrievedSource],
        mock_manager: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Verify search mode does not create a generation span."""
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_span = MagicMock()
        mock_trace.span.return_value = mock_span

        mock_user_msg = MagicMock()
        mock_user_msg.id = 10

        with (
            patch("api.websocket.chat_handler.create_trace", return_value=mock_trace),
            patch("api.websocket.chat_handler.get_qdrant", return_value=MagicMock()),
            patch("api.websocket.chat_handler.get_embedder_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.get_llm_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.ChatService") as mock_service_cls,
        ):
            service = mock_service_cls.return_value
            service.get_session = AsyncMock(return_value=mock_session)
            service.retrieve_context = AsyncMock(return_value=mock_sources)
            service.get_document_titles = AsyncMock(return_value={})
            service.save_user_message = AsyncMock(return_value=mock_user_msg)

            await handler._process_chat(mock_user, session_id=1, query="test", mode="search")

            # Generation should not be called in search mode
            mock_trace.generation.assert_not_called()


class TestChatHandlerRagasEval:
    """Tests for RAGAS evaluation task firing."""

    @pytest.mark.asyncio
    async def test_fires_ragas_eval_task(
        self,
        handler: ChatHandler,
        mock_user: MagicMock,
        mock_session: MagicMock,
        mock_sources: list[RetrievedSource],
        mock_manager: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Verify maybe_evaluate_async is called with correct parameters."""
        mock_trace = MagicMock()
        mock_trace.id = "trace-456"
        mock_span = MagicMock()
        mock_trace.span.return_value = mock_span
        mock_gen = MagicMock()
        mock_trace.generation.return_value = mock_gen

        mock_user_msg = MagicMock()
        mock_user_msg.id = 10
        mock_assistant_msg = MagicMock()
        mock_assistant_msg.id = 11

        with (
            patch("api.websocket.chat_handler.create_trace", return_value=mock_trace),
            patch("api.websocket.chat_handler.get_qdrant", return_value=MagicMock()),
            patch("api.websocket.chat_handler.get_embedder_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.get_llm_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.ChatService") as mock_service_cls,
            patch(
                "api.websocket.chat_handler.maybe_evaluate_async",
                new_callable=AsyncMock,
            ) as mock_eval,
        ):
            service = mock_service_cls.return_value
            service.get_session = AsyncMock(return_value=mock_session)
            service.retrieve_context = AsyncMock(return_value=mock_sources)
            service.get_document_titles = AsyncMock(return_value={})
            service.save_user_message = AsyncMock(return_value=mock_user_msg)
            service.save_assistant_message = AsyncMock(return_value=mock_assistant_msg)

            async def mock_stream(**kwargs):
                yield "response text"

            service.stream_response = mock_stream

            # Patch asyncio.create_task to capture the coroutine
            created_tasks = []
            original_create_task = asyncio.create_task

            def capture_create_task(coro, **kwargs):
                task = original_create_task(coro, **kwargs)
                created_tasks.append(task)
                return task

            with patch("api.websocket.chat_handler.asyncio.create_task", side_effect=capture_create_task):
                await handler._process_chat(mock_user, session_id=1, query="test query", mode="chat")

            # Wait for the eval task to complete
            if created_tasks:
                await asyncio.gather(*created_tasks, return_exceptions=True)

            # Verify maybe_evaluate_async was called
            mock_eval.assert_called_once_with(
                trace_id="trace-456",
                query="test query",
                response="response text",
                contexts=[
                    "Test content for retrieval.",
                    "More test content.",
                ],
                llm_config={
                    "endpoint": "http://tgi:8080",
                    "model_id": "llama-3-70b",
                    "api_key": "test-key",
                },
            )

    @pytest.mark.asyncio
    async def test_no_ragas_eval_in_search_mode(
        self,
        handler: ChatHandler,
        mock_user: MagicMock,
        mock_session: MagicMock,
        mock_sources: list[RetrievedSource],
        mock_manager: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Verify RAGAS evaluation is not triggered in search mode."""
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_span = MagicMock()
        mock_trace.span.return_value = mock_span

        mock_user_msg = MagicMock()
        mock_user_msg.id = 10

        with (
            patch("api.websocket.chat_handler.create_trace", return_value=mock_trace),
            patch("api.websocket.chat_handler.get_qdrant", return_value=MagicMock()),
            patch("api.websocket.chat_handler.get_embedder_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.get_llm_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.ChatService") as mock_service_cls,
            patch(
                "api.websocket.chat_handler.maybe_evaluate_async",
                new_callable=AsyncMock,
            ) as mock_eval,
        ):
            service = mock_service_cls.return_value
            service.get_session = AsyncMock(return_value=mock_session)
            service.retrieve_context = AsyncMock(return_value=mock_sources)
            service.get_document_titles = AsyncMock(return_value={})
            service.save_user_message = AsyncMock(return_value=mock_user_msg)

            await handler._process_chat(mock_user, session_id=1, query="test", mode="search")

            mock_eval.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_config_none_when_no_assistant_llm(
        self,
        handler: ChatHandler,
        mock_user: MagicMock,
        mock_sources: list[RetrievedSource],
        mock_manager: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Verify llm_config is None when session has no assistant LLM."""
        # Session without assistant
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session.assistant = None

        mock_trace = MagicMock()
        mock_trace.id = "trace-789"
        mock_span = MagicMock()
        mock_trace.span.return_value = mock_span
        mock_gen = MagicMock()
        mock_trace.generation.return_value = mock_gen

        mock_user_msg = MagicMock()
        mock_user_msg.id = 10
        mock_assistant_msg = MagicMock()
        mock_assistant_msg.id = 11

        with (
            patch("api.websocket.chat_handler.create_trace", return_value=mock_trace),
            patch("api.websocket.chat_handler.get_qdrant", return_value=MagicMock()),
            patch("api.websocket.chat_handler.get_embedder_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.get_llm_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.ChatService") as mock_service_cls,
            patch(
                "api.websocket.chat_handler.maybe_evaluate_async",
                new_callable=AsyncMock,
            ) as mock_eval,
        ):
            service = mock_service_cls.return_value
            service.get_session = AsyncMock(return_value=mock_session)
            service.retrieve_context = AsyncMock(return_value=mock_sources)
            service.get_document_titles = AsyncMock(return_value={})
            service.save_user_message = AsyncMock(return_value=mock_user_msg)
            service.save_assistant_message = AsyncMock(return_value=mock_assistant_msg)

            async def mock_stream(**kwargs):
                yield "response"

            service.stream_response = mock_stream

            created_tasks = []
            original_create_task = asyncio.create_task

            def capture_create_task(coro, **kwargs):
                task = original_create_task(coro, **kwargs)
                created_tasks.append(task)
                return task

            with patch("api.websocket.chat_handler.asyncio.create_task", side_effect=capture_create_task):
                await handler._process_chat(mock_user, session_id=1, query="test", mode="chat")

            if created_tasks:
                await asyncio.gather(*created_tasks, return_exceptions=True)

            mock_eval.assert_called_once_with(
                trace_id="trace-789",
                query="test",
                response="response",
                contexts=[
                    "Test content for retrieval.",
                    "More test content.",
                ],
                llm_config=None,
            )


class TestChatHandlerTokenStreaming:
    """Tests for token streaming with Langfuse generation tracking."""

    @pytest.mark.asyncio
    async def test_tokens_sent_to_client(
        self,
        handler: ChatHandler,
        mock_user: MagicMock,
        mock_session: MagicMock,
        mock_sources: list[RetrievedSource],
        mock_manager: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Verify tokens are sent to client via WebSocket."""
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_span = MagicMock()
        mock_trace.span.return_value = mock_span
        mock_gen = MagicMock()
        mock_trace.generation.return_value = mock_gen

        mock_user_msg = MagicMock()
        mock_user_msg.id = 10
        mock_assistant_msg = MagicMock()
        mock_assistant_msg.id = 11

        with (
            patch("api.websocket.chat_handler.create_trace", return_value=mock_trace),
            patch("api.websocket.chat_handler.get_qdrant", return_value=MagicMock()),
            patch("api.websocket.chat_handler.get_embedder_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.get_llm_client", return_value=AsyncMock()),
            patch("api.websocket.chat_handler.ChatService") as mock_service_cls,
            patch("api.websocket.chat_handler.maybe_evaluate_async", new_callable=AsyncMock),
        ):
            service = mock_service_cls.return_value
            service.get_session = AsyncMock(return_value=mock_session)
            service.retrieve_context = AsyncMock(return_value=mock_sources)
            service.get_document_titles = AsyncMock(return_value={})
            service.save_user_message = AsyncMock(return_value=mock_user_msg)
            service.save_assistant_message = AsyncMock(return_value=mock_assistant_msg)

            tokens = ["Hello", " ", "world"]

            async def mock_stream(**kwargs):
                for t in tokens:
                    yield t

            service.stream_response = mock_stream

            await handler._process_chat(mock_user, session_id=1, query="test", mode="chat")

            # Check GENERATION_TOKEN messages were sent
            token_calls = [
                call
                for call in mock_manager.send_to_user.call_args_list
                if call[0][1].get("type") == MessageType.GENERATION_TOKEN
            ]
            assert len(token_calls) == 3

            # Check GENERATION_COMPLETE was sent
            complete_calls = [
                call
                for call in mock_manager.send_to_user.call_args_list
                if call[0][1].get("type") == MessageType.GENERATION_COMPLETE
            ]
            assert len(complete_calls) == 1
            assert complete_calls[0][0][1]["token_count"] == 3
