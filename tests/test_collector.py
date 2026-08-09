import pytest

from src import collector


def docker_stats():
    return {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 300, "percpu_usage": [1, 1]},
            "system_cpu_usage": 2000,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 100},
            "system_cpu_usage": 1000,
        },
        "memory_stats": {
            "usage": 600,
            "limit": 1000,
            "stats": {"inactive_file": 100},
        },
    }


def test_docker_cpu_percent_uses_cpu_and_system_deltas():
    assert collector.docker_cpu_percent(docker_stats()) == 40.0


def test_docker_memory_percent_excludes_inactive_cache():
    assert collector.docker_memory_percent(docker_stats()) == 50.0


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"cpu_percent": 1, "memory_percent": 2, "latency_ms": 120, "error_rate": 0.01, "restart_count": 0}


class FakeHttp:
    @staticmethod
    def get(url, timeout):
        assert url.endswith(":8001/metrics")
        assert timeout == 3
        return FakeResponse()


class FakeContainer:
    attrs = {"RestartCount": 4}

    def stats(self, stream=False):
        assert stream is False
        return docker_stats()

    def reload(self):
        return None


class FakeContainers:
    @staticmethod
    def get(name):
        assert name == "auth-service"
        return FakeContainer()


class FakeDocker:
    containers = FakeContainers()


def test_hybrid_snapshot_uses_real_container_resources():
    snapshot = collector.collect_snapshot("auth-service", 8001, "hybrid", FakeHttp(), FakeDocker())
    assert snapshot["metrics_source"] == "docker+service"
    assert snapshot["cpu_percent"] == 40.0
    assert snapshot["memory_percent"] == 50.0
    assert snapshot["restart_count"] == 4
    assert snapshot["probe_latency_ms"] >= 0


def test_strict_docker_mode_surfaces_telemetry_failure():
    class BrokenDocker:
        class containers:
            @staticmethod
            def get(_name):
                raise RuntimeError("daemon unavailable")

    with pytest.raises(RuntimeError, match="daemon unavailable"):
        collector.collect_snapshot("auth-service", 8001, "docker", FakeHttp(), BrokenDocker())
