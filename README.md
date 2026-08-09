# self-healing-docker

A small container orchestration system that **detects anomalies in running
services and recovers them automatically** — no human in the loop.

Three mock microservices report live metrics. A control loop polls them,
flags anomalies with statistical + threshold rules, and takes a recovery
action (restarting the container, flagging a leak, escalating). Everything is
visible on a live dashboard, and you can inject failure on demand to watch the
system heal itself.

```
services (/metrics, /chaos)
        │  poll every 5s
        ▼
   collector ──► detector ──► recovery ──► storage
   (rolling      (z-score +   (Docker      (JSON +
    windows)     thresholds)  restart)     in-memory)
        │                                     │
        └──────────────► API + dashboard ◄────┘
```

## How it works

| Stage | File | Job |
|-------|------|-----|
| Services | `services/main.py` | 3 FastAPI mocks emitting cpu/memory/latency/error metrics; `/chaos` degrades them for 30s |
| Collector | `src/collector.py` | Polls every service, keeps a rolling window of the last 10 samples |
| Detector | `src/detector.py` | Flags anomalies when a metric crosses a critical threshold **or** its z-score spikes |
| Recovery | `src/recovery.py` | Restarts the container via the Docker SDK; softer actions flag/escalate |
| Storage | `src/storage.py` | Thread-safe incident store, mirrored to `data/incidents.json` |
| Pipeline | `src/pipeline.py` | Control loop tying it together, runs on a background thread |
| API | `src/api.py` | `/status`, `/incidents`, `/chaos/{service}`, and a live HTML dashboard |

## Detection

Two signals per metric so it catches both hard failures and subtle drift:

- **Threshold** — e.g. CPU > 85%, latency > 500ms, error rate > 10%
- **Z-score** — value more than 2.5σ from the window mean (catches spikes that
  are abnormal for that service even if under the hard cap)

## Recovery actions

| Incident | Action |
|----------|--------|
| high CPU | restart container |
| high memory | flag possible leak |
| latency degradation | mark degraded |
| error burst / restart storm | escalate |

## Run it

```bash
# 1. start the three mock services
docker-compose up --build -d

# 2. start the control plane + dashboard
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn src.api:app --reload

# 3. open the dashboard
open http://localhost:8000
```

### Trigger a failure

Click **chaos** on any service in the dashboard, or:

```bash
curl -X POST http://localhost:8000/chaos/auth-service
```

Within a few seconds the service goes red, an incident appears, and recovery
restarts the container — which clears the chaos and the service returns to
green.

## Test

```bash
pytest tests/ -q
```

## Stack

Python · FastAPI · Docker SDK · NumPy · pytest · docker-compose
