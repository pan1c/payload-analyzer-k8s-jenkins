# Payload Analyzer Microservice

FastAPI service for numeric and text data analysis with production-grade metrics and logging support.

## Key Features
- `/health`, `/ready` — status checks
- `/payload` — JSON payload analysis
- `/metrics` — Prometheus metrics: request counts, response times, error rate
- Centralized logging

## Structure
- `api/` — endpoints and schemas
- `services/` — analysis business logic
- `observability/` — metrics and logging
- `main.py` — application entry point

See the main project README for more details.
