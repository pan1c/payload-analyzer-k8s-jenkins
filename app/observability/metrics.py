"""Prometheus metrics & middleware for FastAPI microservice.

Collects per-endpoint request count and latency, exposes /metrics endpoint for Prometheus.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response, FastAPI
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
import time

from app.api import health, payload

# Prometheus metric names as constants
REQUEST_COUNT_NAME = "payload_analyzer_request_total"
REQUEST_LATENCY_NAME = "payload_analyzer_request_duration_seconds"
REQUEST_ERROR_COUNT_NAME = "payload_analyzer_request_errors_total"

# -----------------------------------------------------------------------------
# Metric objects
# -----------------------------------------------------------------------------
# Prometheus metrics objects (these are global and thread-safe)
# REQUEST_COUNT: Counter for total HTTP requests, labeled by path, method, and status code.
REQUEST_COUNT = Counter(
    name=REQUEST_COUNT_NAME,
    documentation="Total HTTP requests",
    labelnames=["path", "method", "status"],
)

# REQUEST_LATENCY: Histogram for request duration (seconds), labeled by path and method.
# In Prometheus exposition format, lines ending with _bucket represent histogram buckets.
# For example:
# payload_analyzer_request_duration_seconds_bucket{le="0.5",...} 3.0
# This means: "number of requests with duration <= 0.5 seconds".
# The histogram metric (REQUEST_LATENCY) automatically creates these _bucket lines,
# as well as _count and _sum for total count and sum of observed values.
REQUEST_LATENCY = Histogram(
    name=REQUEST_LATENCY_NAME,
    documentation="Request latency in seconds",
    labelnames=["path", "method"],
)

# REQUEST_ERROR_COUNT: Counter for error responses (status >= 400)
REQUEST_ERROR_COUNT = Counter(
    name=REQUEST_ERROR_COUNT_NAME,
    documentation="Total HTTP error responses (status >= 400)",
    labelnames=["path", "method", "status"],
)

# -----------------------------------------------------------------------------
# ASGI middleware
# -----------------------------------------------------------------------------
# Middleware to collect metrics per request.
# This middleware wraps every HTTP request and:
# - Records the start time.
# - On response, increments the request counter and observes the latency.
# - Labels are extracted from the route path (template if available), HTTP method, and status code.
class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only instrument HTTP requests (not websockets, lifespan, etc.)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        req = Request(scope, receive)
        started_at = time.perf_counter()

        async def send_wrapper(message):
            # Intercept the response start to record metrics
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Use route path template if available (e.g., "/payload"), else fallback to actual path (e.g., "/payload")
                route = scope.get("route")
                if route and hasattr(route, "path"):
                    path_template = route.path
                else:
                    path_template = scope.get("path", "")
                # Increment request counter with labels
                REQUEST_COUNT.labels(path_template, req.method, status_code).inc()
                # Increment error counter if status >= 400
                if int(status_code) >= 400:
                    REQUEST_ERROR_COUNT.labels(path_template, req.method, status_code).inc()
                # Observe request latency in seconds
                REQUEST_LATENCY.labels(path_template, req.method).observe(time.perf_counter() - started_at)
            await send(message)

        # Call the next middleware or route handler
        await self.app(scope, receive, send_wrapper)

# -----------------------------------------------------------------------------
# /metrics endpoint
# -----------------------------------------------------------------------------
# FastAPI router for /metrics endpoint.
# This endpoint exposes all Prometheus metrics in plaintext format for scraping.
metrics_router = APIRouter()

@metrics_router.get("/metrics")
async def metrics():
    # Expose Prometheus metrics in plaintext format (Prometheus scrapes this endpoint)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# -----------------------------------------------------------------------------
# Optional: create_app factory (not used in production entrypoint)
# -----------------------------------------------------------------------------
def create_app() -> FastAPI:
    """
    This factory function is useful for:
    - Running the app in development or testing (e.g., `uvicorn app.observability.metrics:create_app`)
    - Unit/integration testing with FastAPI's TestClient
    - Local experiments or running the app as a standalone FastAPI instance

    In production, your service uses a custom entrypoint (e.g., app/serve.py) and does not use this factory.
    """
    app = FastAPI(
        title="Payload Analyzer Service",
        version="1.0.0",
    )
    app.add_middleware(MetricsMiddleware)
    app.include_router(metrics_router)
    app.include_router(health.router)
    app.include_router(payload.router)
    return app
