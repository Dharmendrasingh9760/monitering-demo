"""
Sample multi-service Flask app instrumented for Prometheus.
Simulates 3 "services" (orders, payments, inventory) so we can demonstrate
SERVICE-LEVEL monitoring (request rate, error rate, latency per service),
not just host-level CPU/RAM.
"""

import random
import time
import logging

from flask import Flask, jsonify, request
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

SERVICES = ["orders", "payments", "inventory"]

# ---- Service-level metrics (the RED method: Rate, Errors, Duration) ----
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "endpoint", "method", "status"]
)

ERROR_COUNT = Counter(
    "http_errors_total",
    "Total HTTP error responses (5xx)",
    ["service", "endpoint"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency in seconds",
    ["service", "endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5]
)

IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Requests currently being processed",
    ["service"]
)

# Baseline "natural" error rate per service, adjustable at runtime for demo
ERROR_RATE = {s: 0.02 for s in SERVICES}  # 2% baseline errors


def simulate_work(service, endpoint):
    IN_PROGRESS.labels(service=service).inc()
    start = time.time()
    try:
        # simulate variable latency
        time.sleep(random.uniform(0.02, 0.3))

        if random.random() < ERROR_RATE[service]:
            ERROR_COUNT.labels(service=service, endpoint=endpoint).inc()
            REQUEST_COUNT.labels(
                service=service, endpoint=endpoint, method="GET", status="500"
            ).inc()
            duration = time.time() - start
            REQUEST_LATENCY.labels(service=service, endpoint=endpoint).observe(duration)
            log.error(f"[{service}] {endpoint} failed")
            return jsonify({"service": service, "status": "error"}), 500

        REQUEST_COUNT.labels(
            service=service, endpoint=endpoint, method="GET", status="200"
        ).inc()
        duration = time.time() - start
        REQUEST_LATENCY.labels(service=service, endpoint=endpoint).observe(duration)
        return jsonify({"service": service, "status": "ok"}), 200
    finally:
        IN_PROGRESS.labels(service=service).dec()


@app.route("/api/orders")
def orders():
    return simulate_work("orders", "/api/orders")


@app.route("/api/payments")
def payments():
    return simulate_work("payments", "/api/payments")


@app.route("/api/inventory")
def inventory():
    return simulate_work("inventory", "/api/inventory")


@app.route("/simulate-error/<service>/<int:rate_percent>")
def simulate_error(service, rate_percent):
    """Test helper: set error rate for a service to trigger alerts on demand.
    e.g. GET /simulate-error/payments/80  -> 80% of payments requests fail
    """
    if service not in SERVICES:
        return jsonify({"error": "unknown service"}), 404
    ERROR_RATE[service] = max(0, min(1, rate_percent / 100))
    log.warning(f"Error rate for {service} set to {ERROR_RATE[service]*100}%")
    return jsonify({"service": service, "new_error_rate": ERROR_RATE[service]})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
