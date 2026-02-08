"""
Unit tests for RAGAS evaluation module.

Tests sample rate logic, skip conditions, mocked RAGAS metrics,
partial failure tolerance, and score pushing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.logic.ragas_evaluator import (
    EvalResult,
    _get_sample_rate,
    _push_score,
    _should_evaluate,
    maybe_evaluate_async,
)


class TestEvalResult:
    """Tests for EvalResult dataclass."""

    def test_defaults_to_none_scores(self) -> None:
        """All scores default to None."""
        result = EvalResult(trace_id="trace_1")
        assert result.trace_id == "trace_1"
        assert result.faithfulness is None
        assert result.response_relevancy is None
        assert result.context_precision is None

    def test_with_all_scores(self) -> None:
        """All scores can be set."""
        result = EvalResult(
            trace_id="trace_1",
            faithfulness=0.9,
            response_relevancy=0.85,
            context_precision=0.7,
        )
        assert result.faithfulness == 0.9
        assert result.response_relevancy == 0.85
        assert result.context_precision == 0.7


class TestGetSampleRate:
    """Tests for _get_sample_rate()."""

    def test_default_rate(self) -> None:
        """Returns default 0.1 when env var not set."""
        with patch.dict("os.environ", {}, clear=True):
            rate = _get_sample_rate()
            assert rate == 0.1

    def test_custom_rate_from_env(self) -> None:
        """Reads rate from API_RAGAS_SAMPLE_RATE env var."""
        with patch.dict("os.environ", {"API_RAGAS_SAMPLE_RATE": "0.5"}):
            rate = _get_sample_rate()
            assert rate == 0.5

    def test_clamps_rate_above_one(self) -> None:
        """Clamps rate to 1.0 when env var exceeds 1."""
        with patch.dict("os.environ", {"API_RAGAS_SAMPLE_RATE": "2.0"}):
            rate = _get_sample_rate()
            assert rate == 1.0

    def test_clamps_rate_below_zero(self) -> None:
        """Clamps rate to 0.0 when env var is negative."""
        with patch.dict("os.environ", {"API_RAGAS_SAMPLE_RATE": "-0.5"}):
            rate = _get_sample_rate()
            assert rate == 0.0

    def test_invalid_string_returns_default(self) -> None:
        """Returns default when env var is not a valid float."""
        with patch.dict("os.environ", {"API_RAGAS_SAMPLE_RATE": "invalid"}):
            rate = _get_sample_rate()
            assert rate == 0.1

    def test_full_rate(self) -> None:
        """Rate of 1.0 means evaluate every request."""
        with patch.dict("os.environ", {"API_RAGAS_SAMPLE_RATE": "1.0"}):
            rate = _get_sample_rate()
            assert rate == 1.0

    def test_zero_rate(self) -> None:
        """Rate of 0.0 means never evaluate."""
        with patch.dict("os.environ", {"API_RAGAS_SAMPLE_RATE": "0.0"}):
            rate = _get_sample_rate()
            assert rate == 0.0


class TestShouldEvaluate:
    """Tests for _should_evaluate()."""

    def test_always_evaluates_at_rate_one(self) -> None:
        """Always returns True when sample rate is 1.0."""
        with patch.dict("os.environ", {"API_RAGAS_SAMPLE_RATE": "1.0"}):
            assert _should_evaluate() is True

    def test_never_evaluates_at_rate_zero(self) -> None:
        """Always returns False when sample rate is 0.0."""
        with patch.dict("os.environ", {"API_RAGAS_SAMPLE_RATE": "0.0"}):
            assert _should_evaluate() is False

    def test_respects_random_threshold(self) -> None:
        """Returns True when random value is below sample rate."""
        with (
            patch.dict("os.environ", {"API_RAGAS_SAMPLE_RATE": "0.5"}),
            patch("api.logic.ragas_evaluator.random.random", return_value=0.3),
        ):
            assert _should_evaluate() is True

    def test_rejects_above_threshold(self) -> None:
        """Returns False when random value is above sample rate."""
        with (
            patch.dict("os.environ", {"API_RAGAS_SAMPLE_RATE": "0.5"}),
            patch("api.logic.ragas_evaluator.random.random", return_value=0.7),
        ):
            assert _should_evaluate() is False


class TestMaybeEvaluateAsync:
    """Tests for maybe_evaluate_async()."""

    @pytest.mark.asyncio
    async def test_returns_none_when_langfuse_disabled(self) -> None:
        """Skips evaluation when Langfuse is disabled."""
        with patch(
            "api.logic.ragas_evaluator.is_langfuse_enabled",
            return_value=False,
        ):
            result = await maybe_evaluate_async(
                trace_id="trace_1",
                query="What is AI?",
                response="AI is artificial intelligence.",
                contexts=["AI stands for artificial intelligence."],
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_trace_id_empty(self) -> None:
        """Skips evaluation when trace_id is empty."""
        with patch(
            "api.logic.ragas_evaluator.is_langfuse_enabled",
            return_value=True,
        ):
            result = await maybe_evaluate_async(
                trace_id="",
                query="test",
                response="response",
                contexts=[],
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_sampling_skips(self) -> None:
        """Skips evaluation when not selected by sample rate."""
        with (
            patch(
                "api.logic.ragas_evaluator.is_langfuse_enabled",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._should_evaluate",
                return_value=False,
            ),
        ):
            result = await maybe_evaluate_async(
                trace_id="trace_1",
                query="What is AI?",
                response="AI is artificial intelligence.",
                contexts=["context"],
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_query_empty(self) -> None:
        """Skips evaluation when query is empty."""
        with (
            patch(
                "api.logic.ragas_evaluator.is_langfuse_enabled",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._should_evaluate",
                return_value=True,
            ),
        ):
            result = await maybe_evaluate_async(
                trace_id="trace_1",
                query="",
                response="response",
                contexts=[],
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_response_empty(self) -> None:
        """Skips evaluation when response is empty."""
        with (
            patch(
                "api.logic.ragas_evaluator.is_langfuse_enabled",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._should_evaluate",
                return_value=True,
            ),
        ):
            result = await maybe_evaluate_async(
                trace_id="trace_1",
                query="What is AI?",
                response="",
                contexts=[],
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_calls_run_evaluation_on_success(self) -> None:
        """Delegates to _run_evaluation when all checks pass."""
        mock_result = EvalResult(trace_id="trace_1", faithfulness=0.9)
        with (
            patch(
                "api.logic.ragas_evaluator.is_langfuse_enabled",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._should_evaluate",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._run_evaluation",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_run,
        ):
            result = await maybe_evaluate_async(
                trace_id="trace_1",
                query="What is AI?",
                response="AI is artificial intelligence.",
                contexts=["context"],
                llm_config={"endpoint": "http://llm", "model_id": "gpt-4"},
            )

            assert result is mock_result
            mock_run.assert_called_once_with(
                "trace_1",
                "What is AI?",
                "AI is artificial intelligence.",
                ["context"],
                {"endpoint": "http://llm", "model_id": "gpt-4"},
            )

    @pytest.mark.asyncio
    async def test_swallows_exceptions(self) -> None:
        """Returns None and logs warning when _run_evaluation raises."""
        with (
            patch(
                "api.logic.ragas_evaluator.is_langfuse_enabled",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._should_evaluate",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._run_evaluation",
                new_callable=AsyncMock,
                side_effect=RuntimeError("RAGAS crashed"),
            ),
        ):
            result = await maybe_evaluate_async(
                trace_id="trace_1",
                query="test",
                response="response",
                contexts=[],
            )
            assert result is None


class TestRunEvaluation:
    """Tests for _run_evaluation() with mocked RAGAS metrics."""

    @pytest.mark.asyncio
    async def test_runs_all_metrics(self) -> None:
        """Runs faithfulness, context_precision, and response_relevancy metrics."""
        mock_faithfulness = AsyncMock()
        mock_faithfulness.single_turn_ascore.return_value = 0.9

        mock_precision = AsyncMock()
        mock_precision.single_turn_ascore.return_value = 0.8

        mock_relevancy = AsyncMock()
        mock_relevancy.single_turn_ascore.return_value = 0.85

        with (
            patch(
                "api.logic.ragas_evaluator.is_langfuse_enabled",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._should_evaluate",
                return_value=True,
            ),
            patch("api.logic.ragas_evaluator._get_ragas_llm") as mock_llm,
            patch("api.logic.ragas_evaluator._get_ragas_embeddings") as mock_emb,
            patch("api.logic.ragas_evaluator.score_trace") as mock_score,
        ):
            mock_llm.return_value = MagicMock()
            mock_emb.return_value = MagicMock()

            # Patch the metric classes to return our mocks
            with patch.dict("sys.modules", {
                "ragas": MagicMock(),
                "ragas.dataset_schema": MagicMock(),
                "ragas.metrics": MagicMock(
                    Faithfulness=MagicMock(return_value=mock_faithfulness),
                    LLMContextPrecisionWithoutReference=MagicMock(return_value=mock_precision),
                    ResponseRelevancy=MagicMock(return_value=mock_relevancy),
                ),
            }):
                # Import fresh to pick up mocked modules
                from api.logic.ragas_evaluator import _run_evaluation

                result = await _run_evaluation(
                    trace_id="trace_1",
                    query="What is AI?",
                    response="AI is artificial intelligence.",
                    contexts=["AI stands for artificial intelligence."],
                )

                assert result.trace_id == "trace_1"
                assert result.faithfulness == 0.9
                assert result.context_precision == 0.8
                assert result.response_relevancy == 0.85

                # Should push 3 scores
                assert mock_score.call_count == 3

    @pytest.mark.asyncio
    async def test_partial_failure_tolerance(self) -> None:
        """Continues evaluating remaining metrics when one fails."""
        mock_faithfulness = AsyncMock()
        mock_faithfulness.single_turn_ascore.side_effect = RuntimeError("LLM timeout")

        mock_precision = AsyncMock()
        mock_precision.single_turn_ascore.return_value = 0.75

        with (
            patch(
                "api.logic.ragas_evaluator.is_langfuse_enabled",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._should_evaluate",
                return_value=True,
            ),
            patch("api.logic.ragas_evaluator._get_ragas_llm") as mock_llm,
            patch("api.logic.ragas_evaluator._get_ragas_embeddings") as mock_emb,
            patch("api.logic.ragas_evaluator.score_trace") as mock_score,
        ):
            mock_llm.return_value = MagicMock()
            mock_emb.return_value = None  # No embeddings → no response_relevancy

            with patch.dict("sys.modules", {
                "ragas": MagicMock(),
                "ragas.dataset_schema": MagicMock(),
                "ragas.metrics": MagicMock(
                    Faithfulness=MagicMock(return_value=mock_faithfulness),
                    LLMContextPrecisionWithoutReference=MagicMock(return_value=mock_precision),
                    ResponseRelevancy=MagicMock(),
                ),
            }):
                from api.logic.ragas_evaluator import _run_evaluation

                result = await _run_evaluation(
                    trace_id="trace_1",
                    query="test",
                    response="response",
                    contexts=["context"],
                )

                # Faithfulness failed, but context_precision succeeded
                assert result.faithfulness is None
                assert result.context_precision == 0.75
                assert result.response_relevancy is None

                # Only 1 score pushed (context_precision)
                assert mock_score.call_count == 1

    @pytest.mark.asyncio
    async def test_handles_ragas_import_error(self) -> None:
        """Returns empty EvalResult when ragas package not installed."""
        with (
            patch(
                "api.logic.ragas_evaluator.is_langfuse_enabled",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._should_evaluate",
                return_value=True,
            ),
        ):
            # Force ImportError on ragas imports
            import builtins

            original_import = builtins.__import__

            def mock_import(name: str, *args, **kwargs):
                if name.startswith("ragas"):
                    raise ImportError("No module named 'ragas'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                from api.logic.ragas_evaluator import _run_evaluation

                result = await _run_evaluation(
                    trace_id="trace_1",
                    query="test",
                    response="response",
                    contexts=[],
                )

                assert result.trace_id == "trace_1"
                assert result.faithfulness is None
                assert result.response_relevancy is None
                assert result.context_precision is None

    @pytest.mark.asyncio
    async def test_skips_response_relevancy_without_embeddings(self) -> None:
        """Skips response_relevancy when embeddings wrapper is None."""
        mock_faithfulness = AsyncMock()
        mock_faithfulness.single_turn_ascore.return_value = 0.9

        mock_precision = AsyncMock()
        mock_precision.single_turn_ascore.return_value = 0.8

        with (
            patch(
                "api.logic.ragas_evaluator.is_langfuse_enabled",
                return_value=True,
            ),
            patch(
                "api.logic.ragas_evaluator._should_evaluate",
                return_value=True,
            ),
            patch("api.logic.ragas_evaluator._get_ragas_llm") as mock_llm,
            patch("api.logic.ragas_evaluator._get_ragas_embeddings") as mock_emb,
            patch("api.logic.ragas_evaluator.score_trace") as mock_score,
        ):
            mock_llm.return_value = MagicMock()
            mock_emb.return_value = None  # No embeddings

            with patch.dict("sys.modules", {
                "ragas": MagicMock(),
                "ragas.dataset_schema": MagicMock(),
                "ragas.metrics": MagicMock(
                    Faithfulness=MagicMock(return_value=mock_faithfulness),
                    LLMContextPrecisionWithoutReference=MagicMock(return_value=mock_precision),
                    ResponseRelevancy=MagicMock(),
                ),
            }):
                from api.logic.ragas_evaluator import _run_evaluation

                result = await _run_evaluation(
                    trace_id="trace_1",
                    query="test",
                    response="response",
                    contexts=["ctx"],
                )

                assert result.faithfulness == 0.9
                assert result.context_precision == 0.8
                assert result.response_relevancy is None
                # Only 2 scores pushed (no response_relevancy)
                assert mock_score.call_count == 2


class TestPushScore:
    """Tests for _push_score()."""

    def test_calls_score_trace(self) -> None:
        """Delegates to langfuse_helper.score_trace()."""
        with patch("api.logic.ragas_evaluator.score_trace") as mock_score:
            _push_score("trace_1", "faithfulness", 0.95)

            mock_score.assert_called_once_with(
                trace_id="trace_1",
                name="faithfulness",
                value=0.95,
                comment="RAGAS faithfulness (automated)",
            )

    def test_formats_comment_with_metric_name(self) -> None:
        """Comment includes the metric name."""
        with patch("api.logic.ragas_evaluator.score_trace") as mock_score:
            _push_score("trace_1", "context_precision", 0.8)

            call_kwargs = mock_score.call_args[1]
            assert "context_precision" in call_kwargs["comment"]
