"""
RAGAS evaluation module for RAG quality assessment.

Provides reference-free evaluation of RAG pipeline outputs using:
- Faithfulness: Is the response grounded in retrieved context?
- ResponseRelevancy: Is the response relevant to the query?
- LLMContextPrecisionWithoutReference: Are retrieved chunks relevant?

Runs asynchronously and pushes scores to Langfuse traces.
"""

from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Any

from echomind_lib.helpers.langfuse_helper import is_langfuse_enabled, score_trace

from api.middleware.metrics import (
    ragas_context_precision,
    ragas_evaluation_duration,
    ragas_evaluations_total,
    ragas_faithfulness,
    ragas_response_relevancy,
)

logger = logging.getLogger(__name__)

# Default sample rate (fraction of requests to evaluate)
_DEFAULT_SAMPLE_RATE = 0.1


@dataclass
class EvalResult:
    """Result of a RAGAS evaluation run.

    Attributes:
        trace_id: Langfuse trace ID that was evaluated.
        faithfulness: Score for response grounding in context (0-1).
        response_relevancy: Score for response relevance to query (0-1).
        context_precision: Score for context chunk relevance (0-1).
    """

    trace_id: str
    faithfulness: float | None = None
    response_relevancy: float | None = None
    context_precision: float | None = None


def _get_sample_rate() -> float:
    """
    Get the configured RAGAS sample rate.

    Returns:
        Float between 0.0 and 1.0 representing evaluation probability.
    """
    try:
        rate = float(os.getenv("API_RAGAS_SAMPLE_RATE", str(_DEFAULT_SAMPLE_RATE)))
        return max(0.0, min(1.0, rate))
    except (ValueError, TypeError):
        return _DEFAULT_SAMPLE_RATE


def _should_evaluate() -> bool:
    """
    Determine if this request should be evaluated based on sample rate.

    Returns:
        True if the request should be evaluated.
    """
    return random.random() < _get_sample_rate()


async def maybe_evaluate_async(
    trace_id: str,
    query: str,
    response: str,
    contexts: list[str],
    llm_config: dict[str, Any] | None = None,
) -> EvalResult | None:
    """
    Evaluate a chat response if sampling criteria are met.

    Entry point for online (sampled) evaluation. Checks sample rate,
    runs RAGAS metrics, and pushes scores to Langfuse. Never raises
    exceptions - all errors are logged and swallowed.

    Args:
        trace_id: Langfuse trace ID to attach scores to.
        query: The user's original query.
        response: The assistant's generated response.
        contexts: List of retrieved context strings.
        llm_config: Optional LLM configuration override for evaluation.
            Keys: endpoint, model_id, api_key.

    Returns:
        EvalResult if evaluation was performed, None if skipped.
    """
    try:
        if not trace_id or not is_langfuse_enabled():
            return None

        if not _should_evaluate():
            return None

        if not query or not response:
            return None

        return await _run_evaluation(trace_id, query, response, contexts, llm_config)

    except Exception as e:
        logger.warning(f"⚠️ RAGAS evaluation failed (non-fatal): {e}")
        return None


async def _run_evaluation(
    trace_id: str,
    query: str,
    response: str,
    contexts: list[str],
    llm_config: dict[str, Any] | None = None,
) -> EvalResult:
    """
    Run RAGAS metrics and push scores.

    Args:
        trace_id: Langfuse trace ID.
        query: User query.
        response: Assistant response.
        contexts: Retrieved context strings.
        llm_config: Optional LLM configuration.

    Returns:
        EvalResult with computed scores.
    """
    try:
        from ragas.dataset_schema import SingleTurnSample
        from ragas.metrics import (
            Faithfulness,
            LLMContextPrecisionWithoutReference,
            ResponseRelevancy,
        )
    except ImportError:
        logger.warning("⚠️ RAGAS package not installed, skipping evaluation")
        ragas_evaluations_total.labels(status="skipped").inc()
        return EvalResult(trace_id=trace_id)

    # Build sample
    sample = SingleTurnSample(
        user_input=query,
        response=response,
        retrieved_contexts=contexts if contexts else [],
    )

    result = EvalResult(trace_id=trace_id)

    # Get LLM wrapper for RAGAS
    llm_wrapper = _get_ragas_llm(llm_config)
    embeddings_wrapper = _get_ragas_embeddings(llm_config)

    # Run each metric individually for partial failure tolerance
    metrics_to_run: list[tuple[str, Any]] = [
        ("faithfulness", Faithfulness(llm=llm_wrapper)),
        ("context_precision", LLMContextPrecisionWithoutReference(llm=llm_wrapper)),
    ]

    # ResponseRelevancy requires embeddings
    if embeddings_wrapper is not None:
        metrics_to_run.append(
            ("response_relevancy", ResponseRelevancy(llm=llm_wrapper, embeddings=embeddings_wrapper))
        )

    # Map metric names to Prometheus histograms
    _prom_histograms = {
        "faithfulness": ragas_faithfulness,
        "response_relevancy": ragas_response_relevancy,
        "context_precision": ragas_context_precision,
    }

    start_time = time.monotonic()

    for metric_name, metric in metrics_to_run:
        try:
            score = await metric.single_turn_ascore(sample)
            score_float = float(score) if score is not None else None

            if score_float is not None:
                setattr(result, metric_name, score_float)
                _push_score(trace_id, metric_name, score_float)
                # Record in Prometheus histogram
                if metric_name in _prom_histograms:
                    _prom_histograms[metric_name].observe(score_float)
                logger.debug(
                    f"📊 RAGAS {metric_name}={score_float:.3f} for trace {trace_id}"
                )

        except Exception as e:
            logger.warning(
                f"⚠️ RAGAS metric {metric_name} failed for trace {trace_id}: {e}"
            )

    duration = time.monotonic() - start_time
    ragas_evaluation_duration.observe(duration)

    # Determine evaluation status
    has_any_score = any(
        getattr(result, name) is not None
        for name in ("faithfulness", "response_relevancy", "context_precision")
    )
    if has_any_score:
        ragas_evaluations_total.labels(status="success").inc()
    else:
        ragas_evaluations_total.labels(status="error").inc()

    faith = result.faithfulness or 0.0
    relevancy = f"{result.response_relevancy:.3f}" if result.response_relevancy is not None else "N/A"
    precision = result.context_precision or 0.0
    logger.info(
        f"📊 RAGAS eval complete for trace {trace_id}: faith={faith:.3f}, relevancy={relevancy}, precision={precision:.3f}"
    )

    return result


def _push_score(trace_id: str, name: str, value: float) -> None:
    """
    Push a numeric score to Langfuse.

    Args:
        trace_id: Langfuse trace ID.
        name: Score name.
        value: Score value (0.0 - 1.0).
    """
    score_trace(
        trace_id=trace_id,
        name=name,
        value=value,
        comment=f"RAGAS {name} (automated)",
    )


def _get_ragas_llm(llm_config: dict[str, Any] | None = None) -> Any:
    """
    Get a RAGAS-compatible LLM wrapper.

    Uses environment variable overrides first, then falls back to
    the provided llm_config from the assistant's configured LLM.

    Args:
        llm_config: Optional LLM config from database.

    Returns:
        RAGAS LLM wrapper instance.
    """
    from ragas.llms import LangchainLLMWrapper

    # Priority: env vars > llm_config > defaults
    endpoint = os.getenv("API_RAGAS_EVAL_LLM_ENDPOINT")
    model_id = os.getenv("API_RAGAS_EVAL_LLM_MODEL")
    api_key = os.getenv("API_RAGAS_EVAL_LLM_API_KEY")

    if llm_config and not endpoint:
        endpoint = llm_config.get("endpoint")
        model_id = model_id or llm_config.get("model_id")
        api_key = api_key or llm_config.get("api_key")

    # Default to OpenAI-compatible endpoint
    if not endpoint:
        endpoint = "https://api.openai.com/v1"

    if not model_id:
        model_id = "gpt-4o-mini"

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=model_id,
        openai_api_base=endpoint,
        openai_api_key=api_key or "no-key",
        temperature=0.0,
    )

    return LangchainLLMWrapper(llm)


def _get_ragas_embeddings(llm_config: dict[str, Any] | None = None) -> Any:
    """
    Get a RAGAS-compatible embeddings wrapper.

    Args:
        llm_config: Optional LLM config from database.

    Returns:
        RAGAS embeddings wrapper or None if unavailable.
    """
    try:
        from ragas.embeddings import LangchainEmbeddingsWrapper

        endpoint = os.getenv("API_RAGAS_EVAL_LLM_ENDPOINT")
        api_key = os.getenv("API_RAGAS_EVAL_LLM_API_KEY")

        if llm_config and not endpoint:
            endpoint = llm_config.get("endpoint")
            api_key = api_key or llm_config.get("api_key")

        if not endpoint:
            endpoint = "https://api.openai.com/v1"

        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(
            openai_api_base=endpoint,
            openai_api_key=api_key or "no-key",
        )

        return LangchainEmbeddingsWrapper(embeddings)

    except Exception as e:
        logger.warning(f"⚠️ Could not create RAGAS embeddings wrapper: {e}")
        return None
