from collections import deque
import time

import requests

from src.config import METRICS_SOURCE, SERVICES, SERVICE_PORTS, WINDOW_SIZE

try:
    import docker
except ImportError:
    docker = None

_windows = {service: deque(maxlen=WINDOW_SIZE) for service in SERVICES}
_docker_client = None


def docker_cpu_percent(stats):
    cpu = stats.get("cpu_stats", {})
    previous = stats.get("precpu_stats", {})
    cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - previous.get("cpu_usage", {}).get("total_usage", 0)
    system_delta = cpu.get("system_cpu_usage", 0) - previous.get("system_cpu_usage", 0)
    cores = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage", [])) or 1
    if cpu_delta <= 0 or system_delta <= 0:
        return 0.0
    return round((cpu_delta / system_delta) * cores * 100, 2)


def docker_memory_percent(stats):
    memory = stats.get("memory_stats", {})
    usage = memory.get("usage", 0) - memory.get("stats", {}).get("inactive_file", 0)
    limit = memory.get("limit", 0)
    return round(max(0, usage) / limit * 100, 2) if limit else 0.0


def _get_docker_client():
    global _docker_client
    if _docker_client is None:
        if docker is None:
            raise RuntimeError("docker SDK not installed")
        _docker_client = docker.from_env()
    return _docker_client


def collect_snapshot(service, port, metrics_source=METRICS_SOURCE, http=requests, docker_client=None):
    started = time.perf_counter()
    response = http.get(f"http://localhost:{port}/metrics", timeout=3)
    response.raise_for_status()
    snapshot = response.json()
    snapshot["probe_latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    snapshot["metrics_source"] = "service"

    if metrics_source in {"hybrid", "docker"}:
        try:
            client = docker_client or _get_docker_client()
            container = client.containers.get(service)
            stats = container.stats(stream=False)
            container.reload()
            snapshot.update({
                "cpu_percent": docker_cpu_percent(stats),
                "memory_percent": docker_memory_percent(stats),
                "restart_count": int(container.attrs.get("RestartCount", 0)),
                "metrics_source": "docker+service",
            })
        except Exception as error:
            if metrics_source == "docker":
                raise
            snapshot["telemetry_fallback"] = str(error)
    return snapshot


def collect_once(metrics_source=METRICS_SOURCE):
    """Collect one application + container telemetry snapshot per service."""
    for service in SERVICES:
        try:
            snapshot = collect_snapshot(service, SERVICE_PORTS[service], metrics_source)
            _windows[service].append(snapshot)
        except Exception as error:
            print(f"[collector] failed to reach {service}: {error}")


def get_window(service):
    return list(_windows[service])


def get_all_windows():
    return {service: get_window(service) for service in SERVICES}


def clear_windows():
    for window in _windows.values():
        window.clear()
