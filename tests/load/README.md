# Load Test: Quick Start

This document shows how to run the load test for the Payload Analyzer service.

## Jenkins/Docker Example

```
docker run --rm --add-host=host.docker.internal:host-gateway \
  -e N_REQUESTS=5000 \
  -e SERVICE_URL=http://host.docker.internal:8000 \
  -e PROMETHEUS_URL=http://host.docker.internal:9090 \
  -e HEALTH_ENDPOINT=http://host.docker.internal:8000/health \
  -v /path/to/jenkins/workspace/tests/load:/load \
  payload-analyzer-dev python3 /load/test_load.py | tee load_test_report.txt
```

## Minimal Local Run (no Prometheus)

```
PYTHONPATH=. SERVICE_URL=http://127.0.0.1:8081 python3 tests/load/test_load.py
```

## Output Example

```
[11:07:33] INFO Sending load...
[11:07:41] INFO Sent 5000 requests in 7.56s
[11:07:41] INFO Fatal errors: 0
[11:07:41] INFO Connection errors (pre-flight): 0
[11:07:41] INFO Response time: min=0.002s, max=0.016s, avg=0.004s
[11:07:41] INFO Fetching metrics from Prometheus...

--- Per-Pod /payload Metrics Report (CONCURRENCY=3) ---
Pod: 10.244.1.77:8081          | /payload Requests: 1355 | Errors: 0 | Error Rate: 0.00% | Avg /payload Latency: 0.000199s
Pod: 10.244.1.78:8081          | /payload Requests: 1295 | Errors: 0 | Error Rate: 0.00% | Avg /payload Latency: 0.000207s
Pod: 10.244.1.79:8081          | /payload Requests: 1470 | Errors: 0 | Error Rate: 0.00% | Avg /payload Latency: 0.000201s
```
