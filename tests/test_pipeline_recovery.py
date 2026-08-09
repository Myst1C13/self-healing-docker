from src import pipeline, recovery


def make_incident(kind="high_cpu_anomaly", action="restart_container"):
    return {
        "incident_id": "inc_test",
        "timestamp": "2026-08-08T12:00:00+00:00",
        "service": "auth-service",
        "incident_type": kind,
        "recovery_action": action,
    }


def test_incident_cooldown_suppresses_duplicate_recovery():
    pipeline.reset_cooldowns()
    first = make_incident()
    assert pipeline.should_process(first, now=100) is True
    assert pipeline.should_process(first, now=101) is False
    assert pipeline.should_process(first, now=200) is True


def test_cooldown_is_scoped_by_service_and_incident_type():
    pipeline.reset_cooldowns()
    assert pipeline.should_process(make_incident(), now=100) is True
    assert pipeline.should_process(make_incident("error_burst"), now=100) is True


def test_recovery_records_restart_and_measured_latency(monkeypatch):
    class Container:
        def restart(self, timeout):
            assert timeout == 5

    class Containers:
        @staticmethod
        def get(service):
            assert service == "auth-service"
            return Container()

    class Client:
        containers = Containers()

    monkeypatch.setattr(recovery, "_get_client", lambda: Client())
    recovery._restart_counts.clear()
    result = recovery.recover(make_incident())
    assert result["recovery_status"] == "recovered"
    assert result["recovery_latency_ms"] >= 0
    assert "recovery_started_at" in result
    assert "recovered_at" in result
    assert recovery.restart_count("auth-service") == 1


def test_non_restart_action_is_measured_without_docker():
    result = recovery.recover(make_incident("high_memory_anomaly", "flag_possible_leak"))
    assert result["recovery_status"] == "flagged"
    assert result["recovery_latency_ms"] >= 0
