from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api import health, payload
from app.observability.metrics import MetricsMiddleware, metrics_router
from app.observability.logging import setup_logging
from contextlib import asynccontextmanager

# READY_FLAG is used to indicate if the app is fully initialized and ready to serve traffic
READY_FLAG = False

# Lifespan handler for FastAPI: sets READY_FLAG True after startup, False on shutdown
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    global READY_FLAG
    # Startup logic (simulate async init, e.g. DB connection, config load, etc.)
    # await asyncio.sleep(0.1)  # Uncomment if you want to simulate delay
    READY_FLAG = True  # Mark app as ready
    yield
    # Shutdown logic (if needed)
    READY_FLAG = False  # Mark app as not ready

# Factory function to create the FastAPI app
def create_app() -> FastAPI:
    setup_logging()  # Set up logging for the app
    app = FastAPI(
        title="Payload Analyzer Service",
        version="1.0.0",
        lifespan=app_lifespan,  # Use custom lifespan for readiness
    )
    app.add_middleware(MetricsMiddleware)  # Add Prometheus metrics middleware
    app.include_router(metrics_router)     # Expose /metrics endpoint
    app.include_router(health.router)      # Expose /health and /ready endpoints
    app.include_router(payload.router)     # Expose /payload endpoint
    # Expose a callable to check readiness from endpoints
    app.state.ready_flag = lambda: READY_FLAG

    # Custom exception handler for validation errors: always return 400
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Return 400 Bad Request for all validation errors to comply with the assignment requirements (see TASK.md)
        # Ensure all error details are serializable
        def serialize_error(err):
            if isinstance(err, Exception):
                return str(err)
            if isinstance(err, dict):
                return {k: serialize_error(v) for k, v in err.items()}
            if isinstance(err, list):
                return [serialize_error(e) for e in err]
            return err
        return JSONResponse(
            status_code=400,
            content={"detail": serialize_error(exc.errors())},
        )

    return app

# Create the FastAPI app instance
app = create_app()