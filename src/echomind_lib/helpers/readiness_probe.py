"""
Kubernetes readiness and liveness probe utilities.

Provides health check endpoints for container orchestration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from http.server import HTTPServer
from typing import Any, Callable, Coroutine


class HealthStatus(str, Enum):
    """Health check status values."""
    
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    
    name: str
    status: HealthStatus
    message: str | None = None
    latency_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Aggregated health report for all checks."""
    
    status: HealthStatus
    checks: list[HealthCheckResult]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_ms": c.latency_ms,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class ReadinessProbe:
    """
    Kubernetes readiness/liveness probe manager.
    
    Usage:
        probe = ReadinessProbe()
        
        # Register health checks
        probe.register("database", check_database)
        probe.register("redis", check_redis)
        
        # Run all checks
        report = await probe.check_health()
        
        # Use in FastAPI
        @app.get("/health")
        async def health():
            return await probe.check_health()
    """
    
    def __init__(self, timeout: float = 5.0):
        """
        Initialize readiness probe.
        
        Args:
            timeout: Timeout for each health check in seconds
        """
        self._timeout = timeout
        self._checks: dict[str, Callable[[], Coroutine[Any, Any, HealthCheckResult]]] = {}
    
    def register(
        self,
        name: str,
        check: Callable[[], Coroutine[Any, Any, HealthCheckResult]],
    ) -> None:
        """
        Register a health check.
        
        Args:
            name: Unique name for the check
            check: Async function that returns HealthCheckResult
        """
        self._checks[name] = check
    
    def unregister(self, name: str) -> None:
        """Unregister a health check."""
        self._checks.pop(name, None)
    
    async def check_health(self) -> HealthReport:
        """
        Run all registered health checks.
        
        Returns:
            HealthReport with aggregated results
        """
        results: list[HealthCheckResult] = []
        
        for name, check in self._checks.items():
            try:
                start = asyncio.get_event_loop().time()
                result = await asyncio.wait_for(check(), timeout=self._timeout)
                latency = (asyncio.get_event_loop().time() - start) * 1000
                result.latency_ms = latency
                results.append(result)
            except asyncio.TimeoutError:
                results.append(HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check timed out after {self._timeout}s",
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                ))
        
        # Determine overall status
        if all(r.status == HealthStatus.HEALTHY for r in results):
            overall = HealthStatus.HEALTHY
        elif any(r.status == HealthStatus.UNHEALTHY for r in results):
            overall = HealthStatus.UNHEALTHY
        else:
            overall = HealthStatus.DEGRADED
        
        return HealthReport(status=overall, checks=results)
    
    async def is_ready(self) -> bool:
        """Check if service is ready (all checks healthy)."""
        report = await self.check_health()
        return report.status == HealthStatus.HEALTHY
    
    async def is_alive(self) -> bool:
        """Check if service is alive (basic liveness)."""
        return True


async def create_db_health_check(
    check_func: Callable[[], Coroutine[Any, Any, bool]],
    name: str = "database",
) -> Callable[[], Coroutine[Any, Any, HealthCheckResult]]:
    """
    Create a database health check function.
    
    Args:
        check_func: Async function that returns True if healthy
        name: Check name
    
    Returns:
        Health check function
    """
    async def check() -> HealthCheckResult:
        try:
            healthy = await check_func()
            return HealthCheckResult(
                name=name,
                status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
                message="Connected" if healthy else "Connection failed",
            )
        except Exception as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
    
    return check


_readiness_probe: ReadinessProbe | None = None


def get_readiness_probe() -> ReadinessProbe:
    """Get the global readiness probe instance."""
    global _readiness_probe
    if _readiness_probe is None:
        _readiness_probe = ReadinessProbe()
    return _readiness_probe


class HealthServer:
    """
    HTTP health check server for standalone services (gRPC, NATS consumers).

    Provides /healthz and /readyz endpoints for Kubernetes probes.

    Usage:
        server = HealthServer(port=8080)
        threading.Thread(target=server.start, daemon=True).start()

    Attributes:
        is_ready: Set to True when service is ready to receive traffic.
    """

    def __init__(self, port: int = 8080):
        """
        Initialize health server.

        Args:
            port: HTTP port to listen on.
        """
        self._port = port
        self.is_ready = False
        self._server: HTTPServer | None = None

    def set_ready(self, ready: bool = True) -> None:
        """
        Set service readiness state.

        Args:
            ready: Whether service is ready for traffic.
        """
        self.is_ready = ready

    def start(self) -> None:
        """
        Start the HTTP health server (blocking).

        Call this in a daemon thread.
        """
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import json

        health_server = self

        class HealthHandler(BaseHTTPRequestHandler):
            """Handler for health check endpoints."""

            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                """Handle GET requests for health endpoints."""
                if self.path == "/healthz" or self.path == "/":
                    self._respond(200, {"status": "healthy"})
                elif self.path == "/readyz":
                    if health_server.is_ready:
                        self._respond(200, {"status": "ready"})
                    else:
                        self._respond(503, {"status": "not_ready"})
                else:
                    self._respond(404, {"error": "not_found"})

            def _respond(self, status: int, body: dict[str, str]) -> None:
                """Send JSON response."""
                content = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, format: str, *args: Any) -> None:
                """Suppress default access logging."""
                pass

        self._server = HTTPServer(("0.0.0.0", self._port), HealthHandler)
        self._server.serve_forever()

    def stop(self) -> None:
        """Stop the health server."""
        if self._server:
            self._server.shutdown()
