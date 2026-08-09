"""Deterministic recruiter demo: detect -> recover -> persist, without Docker."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src import detector, recovery, storage


def sample(cpu=35):
    return {
        "cpu_percent": cpu,
        "memory_percent": 48,
        "latency_ms": 110,
        "error_rate": 0.01,
        "restart_count": 0,
    }


class DemoContainer:
    def restart(self, timeout):
        print(f"  Docker adapter: restart(timeout={timeout})")


class DemoClient:
    class containers:
        @staticmethod
        def get(service):
            print(f"  Docker adapter: resolved container '{service}'")
            return DemoContainer()


def main():
    print("\nSELF-HEALING DOCKER · deterministic control-loop demo")
    print("=" * 58)
    print("Mode: offline fixture (no Docker daemon or AWS credentials required)\n")

    window = [sample() for _ in range(9)] + [sample(cpu=97)]
    print("1. COLLECT  10 rolling samples; latest CPU = 97%")
    incidents = detector.detect("auth-service", window)
    incident = next(item for item in incidents if item["incident_type"] == "high_cpu_anomaly")
    print(f"2. DETECT   {incident['incident_type']} · {incident['reason']}")

    original_get_client = recovery._get_client
    recovery._get_client = lambda: DemoClient()
    try:
        recovery.recover(incident)
    finally:
        recovery._get_client = original_get_client
    print(f"3. RECOVER  {incident['recovery_status']} in {incident['recovery_latency_ms']} ms")

    with tempfile.TemporaryDirectory(prefix="self-healing-demo-") as directory:
        original_path = storage.INCIDENT_DB_PATH
        storage.INCIDENT_DB_PATH = os.path.join(directory, "incidents.db")
        try:
            storage.save_incident(incident)
            persisted = storage.get_incidents(limit=1)[0]
            summary = storage.stats()
        finally:
            storage.INCIDENT_DB_PATH = original_path

    print("4. PERSIST  SQLite/WAL incident record")
    print("5. REPORT   " + json.dumps(summary, sort_keys=True))
    print("\nIncident:")
    print(json.dumps({
        "incident_id": persisted["incident_id"],
        "service": persisted["service"],
        "type": persisted["incident_type"],
        "status": persisted["recovery_status"],
        "recovery_latency_ms": persisted["recovery_latency_ms"],
    }, indent=2))
    print("\nDemo complete. Run npm run demo:live with the Compose stack for real Docker telemetry.\n")


if __name__ == "__main__":
    main()
