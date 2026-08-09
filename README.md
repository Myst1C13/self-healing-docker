<h1 align="center">Self-Healing Docker</h1>

<p align="center">
  <strong>Detect container anomalies. Recover automatically. Preserve the evidence.</strong>
</p>

<p align="center">
  <a href="https://github.com/Myst1C13/self-healing-docker/actions/workflows/verify.yml"><img src="https://github.com/Myst1C13/self-healing-docker/actions/workflows/verify.yml/badge.svg" alt="Tests"></a>
  <img src="https://img.shields.io/badge/Python-3.12-3776ab.svg" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Docker-Engine%20telemetry-2496ed.svg" alt="Docker">
  <img src="https://img.shields.io/badge/AWS-EventBridge%20%7C%20Lambda-ff9900.svg" alt="AWS">
</p>

Self-Healing Docker is a small reliability control plane for a local
microservice stack. It combines application signals with live Docker Engine
telemetry, detects threshold and statistical anomalies, applies bounded recovery
actions, and stores every incident with measured recovery latency.

An optional AWS path publishes recovered incidents to EventBridge. A Lambda
consumer archives queryable records in DynamoDB and immutable JSON in S3.

## See it in 30 seconds

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm run demo
```

The deterministic demo exercises the real detector, Docker recovery adapter,
and SQLite store with an in-process container fixture. It requires no running
Docker daemon and makes no cloud calls. For the live stack, continue below.

## Architecture

```text
┌──────────────────────── local control plane ─────────────────────────┐
│                                                                      │
│  app /metrics ─┐                                                     │
│                ├─ hybrid collector ─ rolling windows ─ detector      │
│  Docker stats ─┘                                      │              │
│                                                       ▼              │
│                                       incident cooldown / dedupe     │
│                                                       │              │
│                         FastAPI dashboard ◀─ SQLite ◀─ recovery      │
│                                                       │              │
└───────────────────────────────────────────────────────┼──────────────┘
                                                        │ optional
                                                        ▼
                                              EventBridge event bus
                                                        │
                                                        ▼
                                                     Lambda
                                                   ┌────┴────┐
                                                   ▼         ▼
                                               DynamoDB      S3
```

Local persistence happens before cloud export. An AWS failure cannot erase the
incident, and the local record captures whether export succeeded or failed.

## What it demonstrates

| Area | Implementation |
|---|---|
| Telemetry | Docker CPU delta, working-set memory, restart count, HTTP latency/error signals |
| Detection | Critical thresholds plus rolling z-scores |
| Recovery | Container restart, degradation marking, leak flagging, escalation |
| Safety | Per-service/type cooldown prevents repeated recovery storms |
| Persistence | Thread-safe SQLite with WAL, indexes, bounded queries |
| Observability | Recovery rate, mean recovery latency, incident/status APIs |
| Cloud | EventBridge → Lambda → DynamoDB + encrypted/versioned S3 |
| Delivery | pytest suite and GitHub Actions verification |

## Live Docker demo

### Requirements

- Python 3.12+
- Docker Engine / Docker Desktop
- Node.js/npm only for the convenient demo aliases

```bash
# terminal 1: demo services
docker compose up --build -d

# terminal 2: control plane
source venv/bin/activate
uvicorn src.api:app --reload

# terminal 3: optional terminal watcher
npm run demo:live
```

Open [http://localhost:8000](http://localhost:8000), then click **chaos** beside
a service. The control loop collects the degraded signals, creates an incident,
runs the mapped recovery action, and persists the measured result.

```bash
docker compose down
```

## Detection model

For CPU, memory, latency, and error rate, an incident fires when either the
latest value crosses a critical threshold or is more than 2.5 standard
deviations from its rolling mean. Restart storms use a direct count threshold.
The pipeline suppresses duplicate service/type incidents for 60 seconds.

## Telemetry modes

| `METRICS_SOURCE` | Behavior |
|---|---|
| `hybrid` | Default. Prefer Docker CPU/memory/restarts; fall back to service metrics |
| `docker` | Strict. Surface Docker telemetry failures |
| `service` | Use only the application endpoint |

Copy `.env.example` for all local options. Incidents default to
`data/incidents.db`; set `INCIDENT_DB_PATH` to override it.

## AWS incident archive

The AWS stack is real but opt-in: the default demo never creates resources or
charges. It provisions:

- a custom EventBridge bus and rule;
- a Python Lambda archive handler;
- an on-demand, encrypted DynamoDB table with point-in-time recovery;
- a private, encrypted, versioned S3 bucket;
- a least-privilege managed policy granting only `events:PutEvents`.

Deployment and teardown instructions are in [docs/AWS.md](docs/AWS.md).

```bash
export AWS_EXPORT_ENABLED=true
export AWS_REGION=us-east-1
export AWS_EVENT_BUS_NAME=self-healing-docker-dev
uvicorn src.api:app
```

## API

| Route | Purpose |
|---|---|
| `GET /health` | Control-plane health |
| `GET /status` | Latest service snapshots, restart counts, recovery stats |
| `GET /incidents` | Filterable persisted incident history |
| `POST /chaos/{service}` | Forward a demo failure injection |
| `GET /` | Live dashboard |

## Verify

```bash
npm run verify
# equivalent: python3 -m pytest tests -q
```

Tests cover detection, Docker metric math, telemetry fallback, restart recovery,
cooldowns, SQLite persistence, EventBridge publishing, and the Lambda
DynamoDB/S3 archive path.

## Repository map

```text
src/                 collector, detector, recovery, pipeline, API, storage
services/            three instrumented FastAPI demo services
infra/aws/           SAM template and Lambda archive handler
scripts/             deterministic and live terminal demos
tests/               unit and component tests
docs/AWS.md           cloud deployment, credentials, and teardown
docker-compose.yml   local microservice topology
```

## Current limitations

- Recovery policies are static mappings, not learned policies.
- Container restart is implemented; Kubernetes remediation is not.
- The AWS exporter is best-effort after a durable local write and does not yet
  include a retry queue or dead-letter queue.
- The live demo uses instrumented services and explicit chaos injection; it is
  not evidence of production-scale workload testing.

## Stack

Python · FastAPI · Docker SDK · SQLite/WAL · NumPy · pytest · Docker Compose ·
Amazon EventBridge · AWS Lambda · DynamoDB · S3 · AWS SAM
