from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

router = APIRouter()

@router.get("/health")
async def health() -> dict[str, str]:
    """
    Liveness probe.
    Returns 200 OK if the process is alive.
    Used by Kubernetes to determine if the container should be restarted.
    """
    # Always return 200 if process is alive.
    # Typical health checks you could add here:
    # - Check if the main event loop is running (asyncio)
    # - Check memory usage or CPU load (psutil)
    # - Check if critical background tasks are alive
    # - Check if required environment variables/configs are loaded
    # - Check if the application can reach essential dependencies (DB, cache, etc.)
    # For a stateless service, just returning 200 is usually sufficient.
    return {"status": "ok"}

@router.get("/ready")
async def ready(request: Request):
    """
    Readiness probe.
    Returns 200 OK if the service is ready to accept requests.
    Returns 503 if not ready.
    """
    ready_flag = getattr(request.app.state, "ready_flag", None)
    if ready_flag and ready_flag():
        return {"status": "ready"}
    return JSONResponse({"status": "not ready"}, status_code=HTTP_503_SERVICE_UNAVAILABLE)
