"""
Prometheus metrics for RAGAS evaluation.

Exposes a /metrics endpoint and provides metric instruments
for tracking RAGAS evaluation scores, counts, and durations.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Score buckets cover the full 0.0-1.0 range in 0.1 increments
RAGAS_BUCKETS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

ragas_faithfulness = Histogram(
    "ragas_faithfulness_score",
    "RAGAS faithfulness score",
    buckets=RAGAS_BUCKETS,
)
ragas_response_relevancy = Histogram(
    "ragas_response_relevancy_score",
    "RAGAS response relevancy score",
    buckets=RAGAS_BUCKETS,
)
ragas_context_precision = Histogram(
    "ragas_context_precision_score",
    "RAGAS context precision score",
    buckets=RAGAS_BUCKETS,
)
ragas_evaluations_total = Counter(
    "ragas_evaluations_total",
    "Total RAGAS evaluations",
    ["status"],
)
ragas_evaluation_duration = Histogram(
    "ragas_evaluation_duration_seconds",
    "RAGAS evaluation duration in seconds",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120),
)

router = APIRouter()


@router.get("/metrics")
async def metrics() -> Response:
    """
    Expose Prometheus metrics.

    Returns:
        Response with Prometheus text format metrics.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
