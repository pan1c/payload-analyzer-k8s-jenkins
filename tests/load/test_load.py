# This script performs load testing and collects per-pod metrics from a FastAPI service in Kubernetes.
# It sends concurrent requests to the /payload endpoint and fetches Prometheus metrics for analysis.
#
# Note:
# 1. Prometheus metrics may not exactly match the number of requests sent due to scrape intervals and pod restarts.
#    This is expected and does not affect the validity of the load test results.
# 2. It is acceptable if a pod drops a connection before the payload is sent (e.g., during rolling update or pod restart).
#    However, it is considered an error if the payload is accepted but not processed (i.e., non-200 response or connection dropped after payload sent).
#    In these cases, the script exits immediately. Only pre-flight connection errors (before payload is sent) are tolerated and logged.

import requests
import time
import threading
from collections import defaultdict
import re
import os
import sys
from requests.exceptions import ConnectTimeout, ReadTimeout, HTTPError, ConnectionError as ReqConnectionError
import logging

# Configuration via environment variables (with sensible defaults)
KUBE_HOST = os.environ.get("KUBE_HOST", "http://127.0.0.1")  # Base URL for Kubernetes cluster or local testing
SERVICE_URL = os.environ.get("SERVICE_URL", f"{KUBE_HOST}:8000")  # Service endpoint base URL
PAYLOAD_ENDPOINT = os.environ.get("PAYLOAD_ENDPOINT", f"{SERVICE_URL}/payload")  # Endpoint for payload POST
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", f"{KUBE_HOST}:9090")  # Prometheus base URL
METRICS_ENDPOINT = os.environ.get("METRICS_ENDPOINT", f"{SERVICE_URL}/metrics")  # Service metrics endpoint
N_REQUESTS = int(os.environ.get("N_REQUESTS", 5000))  # Total number of requests to send
CONCURRENCY = int(os.environ.get("CONCURRENCY", 3))  # Number of concurrent threads
CONNECT_TIMEOUT = float(os.environ.get("CONNECT_TIMEOUT", 3))  # Connection timeout for requests
READ_TIMEOUT = float(os.environ.get("READ_TIMEOUT", 30))  # Read timeout for requests
DEBUG = os.environ.get("DEBUG", "0") == "1" # Enable debug output if set to 1

# Set up logger
logger = logging.getLogger("loadtest")
log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    level=log_level,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

payload = {
    "numbers": [1, 2, 3, 4, 5],
    "text": "Some sample text for analysis."
}

results = []  # List to store response times
fatal_errors = 0  # Fatal error counter (non-200 or dropped after payload sent)
conn_errors = 0   # Pre-flight connection errors (pod unavailable)
errors_lock = threading.Lock()  # Lock for thread-safe error counting
stop_event = threading.Event()


def _is_preflight_connect_error(exc: ReqConnectionError) -> bool:
    """Detect if a connection error happened before payload was sent (pre-flight)."""
    msg = str(exc).lower()
    return (
        "failed to establish a new connection" in msg
        or "name or service not known" in msg
        or "no route to host" in msg
        or "connection refused" in msg
    )


def send_request(idx=None):
    """Send a POST request to the /payload endpoint and record response time and errors.
    Handles error semantics as follows:
    - Pre-flight connection errors (before payload sent) are logged and tolerated (conn_errors).
    - Any error after payload is sent (connection drop, timeout, non-200 response, empty or invalid response) is fatal and causes exit (fatal_errors).
    """
    global fatal_errors, conn_errors
    req_num = idx + 1 if idx is not None else '?'
    if stop_event.is_set():
        return
    try:
        if DEBUG:
            logger.debug(f"[REQ {req_num}] Sending request...")
        r = requests.post(
            PAYLOAD_ENDPOINT,
            json=payload,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        results.append(r.elapsed.total_seconds())

        # Check for non-200 or empty/invalid response
        if r.status_code != 200:
            with errors_lock:
                fatal_errors += 1
                stop_event.set()
            logger.error(f"[REQ {req_num}] [FATAL] /payload returned status {r.status_code}: {r.text}")
            sys.exit(f"[REQ {req_num}] [FATAL] /payload returned status {r.status_code}: {r.text}")
        try:
            data = r.json()
        except Exception:
            with errors_lock:
                fatal_errors += 1
                stop_event.set()
            logger.error(f"[REQ {req_num}] [FATAL] /payload returned non-JSON or empty response: {r.text}")
            sys.exit(f"[REQ {req_num}] [FATAL] /payload returned non-JSON or empty response: {r.text}")
        if not data or not isinstance(data, dict):
            with errors_lock:
                fatal_errors += 1
                stop_event.set()
            logger.error(f"[REQ {req_num}] [FATAL] /payload returned empty or invalid data: {r.text}")
            sys.exit(f"[REQ {req_num}] [FATAL] /payload returned empty or invalid data: {r.text}")
        if DEBUG:
            logger.debug(f"[REQ {req_num}] Response received: {r.status_code}")

    except ConnectTimeout as exc:
        with errors_lock:
            conn_errors += 1
        return

    except ReqConnectionError as exc:
        if _is_preflight_connect_error(exc):
            with errors_lock:
                conn_errors += 1
            return
        with errors_lock:
            fatal_errors += 1
            stop_event.set()
        logger.error(f"[REQ {req_num}] [FATAL] Connection dropped after payload sent: {exc}")
        sys.exit(f"[REQ {req_num}] [FATAL] Connection dropped after payload sent: {exc}")

    except ReadTimeout as exc:
        with errors_lock:
            fatal_errors += 1
            stop_event.set()
        logger.error(f"[REQ {req_num}] [FATAL] Read timeout waiting for response: {exc}")
        sys.exit(f"[REQ {req_num}] [FATAL] Read timeout waiting for response: {exc}")

    except Exception as exc:
        with errors_lock:
            conn_errors += 1
        return


def run_load():
    """Run the load test with the specified concurrency."""
    threads = []
    for i in range(N_REQUESTS):
        if stop_event.is_set():
            break
        t = threading.Thread(target=send_request, args=(i,))
        threads.append(t)
        t.start()
        if len(threads) >= CONCURRENCY:
            threads[0].join()
            threads.pop(0)
    for t in threads:
        t.join()


def parse_metrics(metrics_text):
    """Parse Prometheus metrics text for request counts and latencies."""
    req_count = defaultdict(int)
    req_latency = []
    for line in metrics_text.splitlines():
        if line.startswith('#'):
            continue
        m = re.match(r'.*_request_total\{.*path="([^"]+)",method="([^"]+)",status="([^"]+)".*\} ([0-9.]+)', line)
        if m:
            path, method, status, count = m.groups()
            req_count[(path, method, status)] += int(float(count))
        m2 = re.match(r'.*_request_duration_seconds_sum\{.*path="([^"]+)",method="([^"]+)".*\} ([0-9.]+)', line)
        if m2:
            path, method, total = m2.groups()
            req_latency.append(float(total))
    return req_count, req_latency


def fetch_prometheus_metrics(query, time_range=None):
    """Query Prometheus HTTP API for a given PromQL query (optionally over a time range)."""
    if time_range:
        url = f"{PROMETHEUS_URL}/api/v1/query_range"
        params = {
            "query": query,
            "start": time_range["start"],
            "end": time_range["end"],
            "step": time_range.get("step", "1s"),
        }
    else:
        url = f"{PROMETHEUS_URL}/api/v1/query"
        params = {"query": query}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


def aggregate_per_pod_metrics(data, error_data, latency_data, latency_count_data):
    """Aggregate request, error, and latency metrics per pod from Prometheus results. Debug output is only shown if DEBUG=1."""
    pod_stats = {}
    for result in data["data"]["result"]:
        metric = result["metric"]
        pod = metric.get("pod", metric.get("instance", "unknown"))
        values = result["values"]
        if values:
            first = float(values[0][1])
            last = float(values[-1][1])
            delta = last - first
            pod_stats.setdefault(pod, {"requests": 0, "errors": 0, "latency_sum": 0.0, "latency_count": 0})
            pod_stats[pod]["requests"] += delta
    for result in error_data["data"]["result"]:
        metric = result["metric"]
        pod = metric.get("pod", metric.get("instance", "unknown"))
        values = result["values"]
        if values:
            first = float(values[0][1])
            last = float(values[-1][1])
            delta = last - first
            pod_stats.setdefault(pod, {"requests": 0, "errors": 0, "latency_sum": 0.0, "latency_count": 0})
            pod_stats[pod]["errors"] += delta
    for result in latency_data["data"]["result"]:
        metric = result["metric"]
        pod = metric.get("pod", metric.get("instance", "unknown"))
        values = result["values"]
        if values:
            first = float(values[0][1])
            last = float(values[-1][1])
            delta = last - first
            pod_stats.setdefault(pod, {"requests": 0, "errors": 0, "latency_sum": 0.0, "latency_count": 0})
            pod_stats[pod]["latency_sum"] += delta
    for result in latency_count_data["data"]["result"]:
        metric = result["metric"]
        pod = metric.get("pod", metric.get("instance", "unknown"))
        values = result["values"]
        if values:
            first = float(values[0][1])
            last = float(values[-1][1])
            delta = last - first
            pod_stats.setdefault(pod, {"requests": 0, "errors": 0, "latency_sum": 0.0, "latency_count": 0})
            pod_stats[pod]["latency_count"] += delta
    if DEBUG:
        logger.debug("Aggregated per-pod stats:")
        for pod, stats in pod_stats.items():
            logger.debug(f"  {pod}: {stats}")
    return pod_stats


def get_per_pod_payload_metrics(duration):
    """Fetch per-pod /payload request, error, and latency metrics from Prometheus for the test window."""
    end = int(time.time())
    start_range = end - int(duration) - 2
    query_filter = '{path="/payload"}'
    data = fetch_prometheus_metrics(
        f'payload_analyzer_request_total{query_filter}',
        time_range={"start": start_range, "end": end, "step": "1s"}
    )
    latency_data = fetch_prometheus_metrics(
        f'payload_analyzer_request_duration_seconds_sum{query_filter}',
        time_range={"start": start_range, "end": end, "step": "1s"}
    )
    latency_count_data = fetch_prometheus_metrics(
        f'payload_analyzer_request_duration_seconds_count{query_filter}',
        time_range={"start": start_range, "end": end, "step": "1s"}
    )
    error_query_filter = query_filter[:-1] + ',status!="200"}'
    error_data = fetch_prometheus_metrics(
        f'payload_analyzer_request_total{error_query_filter}',
        time_range={"start": start_range, "end": end, "step": "1s"}
    )
    return data, error_data, latency_data, latency_count_data


def print_per_pod_metrics_report(pod_stats):
    """Print a formatted per-pod /payload metrics report, including concurrency info. Debug output is only shown if DEBUG=1."""
    print(f"\n--- Per-Pod /payload Metrics Report (CONCURRENCY={CONCURRENCY}) ---")
    for pod in sorted(pod_stats):
        stats = pod_stats[pod]
        reqs = stats["requests"]
        errs = stats["errors"]
        if DEBUG:
            logger.debug(f"Pod {pod}: latency_sum={stats['latency_sum']}, latency_count={stats['latency_count']}")
        avg_latency = (stats["latency_sum"] / stats["latency_count"]) if stats["latency_count"] else 0
        err_rate = (errs / reqs) if reqs else 0
        print(f"Pod: {pod:25} | /payload Requests: {reqs:.0f} | Errors: {errs:.0f} | Error Rate: {err_rate:.2%} | Avg /payload Latency: {avg_latency:.6f}s")
    print("-----------------------------")


def main():
    """Main entry point: checks service health, runs load, prints metrics and per-pod stats."""
    health_url = os.environ.get("HEALTH_ENDPOINT", f"{SERVICE_URL}/health")
    try:
        r = requests.get(health_url, timeout=CONNECT_TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Cannot connect to service health endpoint at {health_url}: {e}")
        exit(1)
    logger.info("Sending load...")
    start = time.time()
    run_load()
    duration = time.time() - start
    logger.info(f"Sent {N_REQUESTS} requests in {duration:.2f}s")
    logger.info(f"Fatal errors: {fatal_errors}")
    logger.info(f"Connection errors (pre-flight): {conn_errors}")
    if fatal_errors > 0:
        logger.error(f"[FATAL] Exiting due to {fatal_errors} fatal errors.")
        sys.exit(2)
    if results:
        logger.info(f"Response time: min={min(results):.3f}s, max={max(results):.3f}s, avg={sum(results)/len(results):.3f}s")
    logger.info("Fetching metrics from Prometheus...")
    try:
        data, error_data, latency_data, latency_count_data = get_per_pod_payload_metrics(duration)
        pod_stats = aggregate_per_pod_metrics(data, error_data, latency_data, latency_count_data)
        print_per_pod_metrics_report(pod_stats)
        # Only keep the three key metrics for the report: request count, error rate, avg latency
        # (This matches the requirements and keeps the report concise for documentation.)
    except Exception as e:
        logger.error(f"Could not fetch from Prometheus: {e}")


if __name__ == "__main__":
    main()
