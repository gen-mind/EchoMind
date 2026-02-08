"""
Unit tests for Prometheus metrics endpoint and metric instruments.

Verifies the /metrics endpoint returns valid Prometheus format
and that all RAGAS metric instruments are properly defined.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.metrics import (
    ragas_context_precision,
    ragas_evaluation_duration,
    ragas_evaluations_total,
    ragas_faithfulness,
    ragas_response_relevancy,
    router,
)


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with the metrics router."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestMetricsEndpoint:
    """Tests for GET /metrics."""

    def test_returns_prometheus_format(self, client: TestClient) -> None:
        """Endpoint returns text content with Prometheus MIME type."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_contains_ragas_faithfulness_metric(self, client: TestClient) -> None:
        """Response contains ragas_faithfulness_score metric."""
        response = client.get("/metrics")
        assert "ragas_faithfulness_score" in response.text

    def test_contains_ragas_response_relevancy_metric(self, client: TestClient) -> None:
        """Response contains ragas_response_relevancy_score metric."""
        response = client.get("/metrics")
        assert "ragas_response_relevancy_score" in response.text

    def test_contains_ragas_context_precision_metric(self, client: TestClient) -> None:
        """Response contains ragas_context_precision_score metric."""
        response = client.get("/metrics")
        assert "ragas_context_precision_score" in response.text

    def test_contains_ragas_evaluations_total_metric(self, client: TestClient) -> None:
        """Response contains ragas_evaluations_total metric."""
        response = client.get("/metrics")
        assert "ragas_evaluations_total" in response.text

    def test_contains_ragas_evaluation_duration_metric(self, client: TestClient) -> None:
        """Response contains ragas_evaluation_duration_seconds metric."""
        response = client.get("/metrics")
        assert "ragas_evaluation_duration_seconds" in response.text


class TestMetricInstruments:
    """Tests for metric instrument definitions."""

    def test_faithfulness_histogram_exists(self) -> None:
        """Faithfulness histogram is defined with correct name."""
        assert ragas_faithfulness._name == "ragas_faithfulness_score"

    def test_response_relevancy_histogram_exists(self) -> None:
        """Response relevancy histogram is defined with correct name."""
        assert ragas_response_relevancy._name == "ragas_response_relevancy_score"

    def test_context_precision_histogram_exists(self) -> None:
        """Context precision histogram is defined with correct name."""
        assert ragas_context_precision._name == "ragas_context_precision_score"

    def test_evaluations_counter_exists(self) -> None:
        """Evaluations counter is defined with correct name."""
        # prometheus_client Counter stores name without _total suffix internally
        assert ragas_evaluations_total._name == "ragas_evaluations"

    def test_duration_histogram_exists(self) -> None:
        """Duration histogram is defined with correct name."""
        assert ragas_evaluation_duration._name == "ragas_evaluation_duration_seconds"

    def test_faithfulness_observe(self) -> None:
        """Faithfulness histogram accepts observations."""
        ragas_faithfulness.observe(0.85)

    def test_evaluations_counter_labels(self) -> None:
        """Counter accepts status labels."""
        ragas_evaluations_total.labels(status="success").inc()
        ragas_evaluations_total.labels(status="error").inc()
        ragas_evaluations_total.labels(status="skipped").inc()
