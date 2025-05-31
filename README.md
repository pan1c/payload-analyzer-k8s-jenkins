# Build, Run, and Deployment Instructions

This section provides quick instructions for building, running, and deploying the service in different environments.


**How to run the service:**

**Local (no container):**
```bash
gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8081 --workers 1 --graceful-timeout 60
```

**Docker Compose:**
```bash
docker compose up --build
```

**Kubernetes deployment:**
- See manifests in `deploy/`
- Set the correct image registry in deployment and service parameters
- Apply manifests:
  ```bash
  kubectl apply -f deploy/k8s-deployment.yaml
  kubectl apply -f deploy/k8s-service.yaml
  ```

**Communicate with the service:**

- Check readiness:
  ```bash
  curl http://127.0.0.1:8081/ready
  ```
- Send a payload:
  ```bash
  curl -X POST http://127.0.0.1:8081/payload -H "Content-Type: application/json" -d '{"numbers":[1,2,3,4,5],"text":"test text"}'
  ```



### Service Description

This service is a stateless FastAPI-based microservice for real-time payload analysis, designed for production environments and zero-downtime deployments. It exposes the following endpoints:

- [`/health`](app/api/health.py): Liveness probe. Returns 200 OK if the service is alive.
- [`/ready`](app/api/health.py): Readiness probe. Returns 200 OK when the service is ready to accept requests (see readiness flag logic in [`app/main.py`](app/main.py)).
- [`/payload`](app/api/payload.py): Accepts a JSON payload:

```json
{
  "numbers": [1, 2, 3, 4, 5],
  "text": "Some sample text for analysis."
}
```

The `/payload` endpoint performs:
- Numeric analysis ([`app/services/numeric.py`](app/services/numeric.py)):
  - min, max, mean, median, standard deviation
- Text analysis ([`app/services/text.py`](app/services/text.py)):
  - word count, character count
- Returns a JSON response with all computed statistics and 200 OK. Malformed requests return 400 (see custom handler in [`app/main.py`](app/main.py)).
- [`/metrics`](app/observability/metrics.py): Exposes Prometheus-compatible operational metrics (request count, response times, error rates, etc.).

The service supports graceful shutdown:
- Handles shutdown signals (SIGTERM/SIGINT) by immediately stopping acceptance of new requests, allowing in-flight requests to finish, and only shutting down when all current transactions are complete. See [`app/main.py`](app/main.py) and Gunicorn+UvicornWorker setup for details.
- Asynchronous processing is used throughout for performance.

---

**My personal remarks:**

The server is implemented in [`app/`](app/). Python and FastAPI are used.
Standard FastAPI schema validation is used, with a custom error handler returning 400 instead of default 422.
Metrics are implemented via custom middleware and exposed at `/metrics`.
Readiness check is implemented with some custom logic - could be overkill for such small API.

Graceful shutdown is tricky: Gunicorn claims to support it ([docs](https://docs.gunicorn.org/en/stable/signals.html)), but in local testing, the master process closes connections immediately, while the worker keeps the socket open for a while, violating "Immediately ceasing to accept new requests" (see [issue 3397](https://github.com/benoitc/gunicorn/issues/3397) and [pull](https://github.com/benoitc/gunicorn/pull/3381)).

A Kubernetes-specific workaround is added: a preStop hook with `sleep 5` in the deployment manifest. This ensures the pod is removed from service endpoints before shutdown begins, allowing iptables/balancer rules to propagate and preventing new requests from reaching the pod during shutdown. See comments in [`deploy/k8s-deployment.yaml`](deploy/k8s-deployment.yaml) for details.

The requirements for "Allowing in-flight requests to complete" and "Only shutting down when all current transactions have finished" are met by default.

Only a single worker is used by default, since this is a microservice running in Kubernetes. This can be adjusted if needed.

---

### 2. Containerization
- [`Dockerfile`](Dockerfile):
  - Multi-stage build for minimal image size
  - Runs as non-root
  - Security and efficiency emphasized

---

**My personal remarks:**

The Dockerfile is in the project root, uses multi-stage builds, runs as non-root, and updates packages.

---

### 3. Deployment Configuration
- Kubernetes is used for orchestration (see [`deploy/`](deploy/)).
- [`deploy/k8s-deployment.yaml`](deploy/k8s-deployment.yaml) and [`deploy/k8s-service.yaml`](deploy/k8s-service.yaml):
  - Deploys 3 replicas behind a load balancer
  - Uses `/ready` for readiness and `/health` for liveness probes
  - Rolling updates with `maxUnavailable: 0` for zero-downtime

---

**My personal remarks:**

Kubernetes and Minikube are used. Deployment and service manifests are in [`deploy/`](deploy/).
Minikube registry used, should be changed in prod.
LoadBalancer is used, testing based on this assumption.

---

### 4. Load Testing

- **Load Testing & Metrics Collection:**
  - [`tests/load/test_load.py`](tests/load/test_load.py):
    - Sends 5000 requests (100 is too fast for meaningful results) to the load balancer IP (using Minikube tunnel)
    - For metrics, a minimal Prometheus is deployed ([`deploy/prometheus.yaml`](deploy/prometheus.yaml)), and metrics are scraped after the load test
    - If this is not possible in production, port-forwarding to each pod would be required
    - This is ok, if we lost part of the numbers in prometheus, as it still showing correct perfomance per pod

Example report:
```
[22:34:46] INFO Sending load...
[22:34:54] INFO Sent 5000 requests in 7.29s
[22:34:54] INFO Fatal errors: 0
[22:34:54] INFO Connection errors (pre-flight): 0
[22:34:54] INFO Response time: min=0.002s, max=0.025s, avg=0.004s
[22:34:54] INFO Fetching metrics from Prometheus...

--- Per-Pod /payload Metrics Report (CONCURRENCY=3) ---
Pod: 10.244.1.69:8081          | /payload Requests: 1314 | Errors: 0 | Error Rate: 0.00% | Avg /payload Latency: 0.000196s
Pod: 10.244.1.70:8081          | /payload Requests: 1142 | Errors: 0 | Error Rate: 0.00% | Avg /payload Latency: 0.000193s
Pod: 10.244.1.71:8081          | /payload Requests: 1421 | Errors: 0 | Error Rate: 0.00% | Avg /payload Latency: 0.000194s
```
This test also detects fatal errors—cases where the payload was sent but not processed.


### 5. Jenkins Integration
- [`Jenkinsfile`](Jenkinsfile):
  - Multi-stage pipeline:
    - Build: checkout, build Docker image, run unit tests
    - Containerization: security scan (Trivy), image integrity
    - Deployment: push to registry, deploy via Kubernetes manifests
    - Validation: integration tests on endpoints (`/health`, `/ready`, `/metrics`), load test
  - Parallel testing: unit, integration, static analysis run concurrently
  - Automated rollback: simulates rolling update, triggers graceful shutdown, rolls back if health checks fail
  - Artifact archiving: logs and performance reports are archived

---

  **My personal remarks:**

The Jenkinsfile is in the project root, tested on local Jenkins. Note: workaround for local macOS registry access at the start. The pipeline checks out code, builds two images (test and prod), runs security checks (prints results; TODO: deeper handling), runs basic unit tests (in parallel), pushes to local registry, deploys manifests to a separate namespace, determines service IP via Kubernetes, waits for deployment, runs integration checks, runs load test and fetches metrics from Prometheus, then simulates a rolling update and runs a load test during the update. If the test or health check fails, it rolls back (Great for demo; I suggest in production, use Argo Rollouts).

---

## Assumptions made and challenges encountered.

To be honest, there were quite a few small challenges that felt more like workarounds than real production issues. For example, returning 400 instead of 422, or deploying to Kubernetes directly from the pipeline. Setting up all the infrastructure for the task (locally, Minikube, and Jenkins) took a fair amount of time. Achieving instant graceful shutdown for the server also took a lot of effort due to the bug described above.

## Integration:
  Tested in local Jenkins and Minikube
