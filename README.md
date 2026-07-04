# Service-Level Monitoring & Error Escalation System

An open-source monitoring + alerting + escalation stack built with **Prometheus**,
**Grafana OSS**, and **Alertmanager**. It monitors a sample multi-service
application at the *service* level (request rate, error rate, latency,
availability) — not just host CPU/RAM — and escalates incidents by severity
(warning → Slack, critical → Slack + Email, paged repeatedly until resolved).

## 1. Architecture

```
                ┌──────────────┐
   users ──────▶│  sample-app  │  (Flask: orders / payments / inventory)
                │  /metrics    │
                └──────┬───────┘
                       │ scrape every 5s
                       ▼
                ┌──────────────┐        evaluates alert_rules.yml
                │  Prometheus  │────────────────────┐
                └──────┬───────┘                    ▼
                       │ query                ┌──────────────┐
                       ▼                       │ Alertmanager │
                ┌──────────────┐               └──────┬───────┘
                │   Grafana    │                       │ routes by severity
                │  Dashboard   │                       ▼
                └──────────────┘            ┌─────────────────────┐
                                             │ warning → Slack      │
                                             │ critical → Slack+Email│
                                             │ (repeats until fixed) │
                                             └─────────────────────┘
```

- **sample-app**: 3 simulated services, each exposing Prometheus metrics
  (`http_requests_total`, `http_errors_total`, `http_request_duration_seconds`).
- **load-generator**: continuously sends traffic so the dashboard has live data.
- **Prometheus**: scrapes metrics every 5s, evaluates alert rules every 5s.
- **Alertmanager**: groups, deduplicates, and routes alerts by `severity` label,
  implementing the escalation policy.
- **Grafana**: visualizes request rate, error rate %, p95 latency, in-flight
  requests, and up/down status per service — plus host CPU/RAM and
  per-container CPU/RAM (via node-exporter + cAdvisor).
- **node-exporter**: exposes host-level CPU, memory, and disk metrics.
- **cAdvisor**: exposes per-container CPU and memory metrics.

## 2. Prerequisites

- Docker Engine 20.10+
- Docker Compose v2 (`docker compose version`)
- ~2GB free RAM
- (Optional, for real alerts) A Slack workspace + incoming webhook URL, and/or
  an SMTP account for email

## 3. Installation & Configuration

### Step 1 — Clone / unzip the project
```bash
cd devops-assignment
```

### Step 2 — (Optional but recommended) Configure real notifications
Edit `alertmanager/alertmanager.yml`:
- Replace `slack_api_url` with your Slack incoming webhook
  (Slack → Apps → Incoming Webhooks → Add to Slack).
- Replace `smtp_*` fields with your email provider's SMTP details.
- If you skip this, the stack still works end-to-end — alerts will just fail
  to actually deliver to Slack/Email, but you'll see them fire in the
  Alertmanager UI, which is enough to demonstrate the mechanism.

### Step 3 — Build and start everything
```bash
docker compose up -d --build
```

### Step 4 — Verify all containers are healthy
```bash
docker compose ps
```
You should see `sample-app`, `load-generator`, `prometheus`, `alertmanager`,
`grafana` all `Up`.

## 4. Accessing the Tools

| Tool          | URL                          | Login          |
|---------------|-------------------------------|----------------|
| Grafana       | http://localhost:3000         | admin / admin  |
| Prometheus    | http://localhost:9090         | -              |
| Alertmanager  | http://localhost:9093         | -              |
| Sample app    | http://localhost:5000/health  | -              |
| Node Exporter | http://localhost:9100/metrics | -              |
| cAdvisor      | http://localhost:8080         | -              |

In Grafana, the **"Service-Level Monitoring & Error Escalation"** dashboard
is auto-provisioned — no manual import needed.

## 5. Testing the Alerting & Escalation Flow

The load generator sends constant background traffic, so panels should
populate within ~10 seconds.

### Trigger a WARNING alert (elevated error rate)
```bash
curl http://localhost:5000/simulate-error/payments/10
```
This sets the `payments` service to fail 10% of requests. Within ~1 minute,
`HighErrorRate_Warning` will fire in Prometheus → Alertmanager → Slack
`#alerts-warning`.

### Trigger a CRITICAL alert (severe error rate → escalation)
```bash
curl http://localhost:5000/simulate-error/payments/80
```
This pushes the error rate to 80%. `HighErrorRate_Critical` fires and routes
to the `oncall-escalation` receiver — Slack `#alerts-critical` + email,
repeating every 5 minutes until resolved (demonstrating escalation, as
opposed to the 1-hour repeat for warnings).

### Watch it resolve
```bash
curl http://localhost:5000/simulate-error/payments/2
```
Error rate drops back to baseline (2%); Alertmanager sends a "resolved"
notification once the condition clears.

### Where to observe each stage
- **Prometheus → Alerts tab** (http://localhost:9090/alerts): see rule state
  (inactive/pending/firing).
- **Alertmanager UI** (http://localhost:9093): see active alerts, grouping,
  and routing.
- **Grafana dashboard**: see the error rate % panel spike and cross the
  orange/red threshold lines in real time.

## 6. Design Notes (for the technical discussion)

- **Service-level over host-level**: metrics are labeled by `service`
  (orders/payments/inventory), so error rate and latency are tracked per
  business capability — reflecting real user impact, not just infra
  resource usage. Host/container CPU-RAM (node-exporter + cAdvisor) is
  included as a *complementary* infra layer, not the primary signal.
- **RED method**: Rate, Errors, Duration — the standard approach for
  monitoring request-driven services.
- **Escalation policy**: severity-based routing with different
  `repeat_interval`s (warning = 1h, critical = 5m) approximates a paging
  escalation — critical issues nag until fixed, warnings don't spam.
- **Inhibition rule**: suppresses redundant warning-level noise for a
  service that already has a critical alert firing, reducing alert fatigue.
- **Extensibility**: this can be extended with Grafana OnCall (open-source)
  for formal on-call schedules and multi-step escalation chains
  (Slack → SMS → phone call) if the interview panel wants a deeper
  incident-management story.

## 7. Stopping the stack
```bash
docker compose down
```
