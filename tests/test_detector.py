from src.detector import detect, detect_all


def sample(cpu=35, mem=50, latency=120, err=0.01, restarts=0):
    return {
        "cpu_percent": cpu,
        "memory_percent": mem,
        "latency_ms": latency,
        "error_rate": err,
        "restart_count": restarts,
    }


def test_healthy_window_has_no_incidents():
    window = [sample() for _ in range(10)]
    assert detect("auth-service", window) == []


def test_window_too_small_returns_empty():
    assert detect("auth-service", [sample(), sample()]) == []


def test_cpu_over_threshold_fires():
    window = [sample() for _ in range(9)] + [sample(cpu=95)]
    incidents = detect("auth-service", window)
    types = [i["incident_type"] for i in incidents]
    assert "high_cpu_anomaly" in types
    cpu = [i for i in incidents if i["incident_type"] == "high_cpu_anomaly"][0]
    assert cpu["recovery_action"] == "restart_container"


def test_zscore_spike_fires_below_threshold():
    # steady latency then a jump that's still under the 500ms cap
    window = [sample(latency=100) for _ in range(9)] + [sample(latency=300)]
    incidents = detect("api-gateway", window)
    assert any(i["incident_type"] == "latency_degradation" for i in incidents)


def test_restart_storm():
    window = [sample() for _ in range(9)] + [sample(restarts=3)]
    incidents = detect("payments-service", window)
    assert any(i["incident_type"] == "restart_storm" for i in incidents)


def test_detect_all_across_services():
    windows = {
        "auth-service": [sample() for _ in range(9)] + [sample(cpu=99)],
        "payments-service": [sample() for _ in range(10)],
    }
    incidents = detect_all(windows)
    assert len(incidents) == 1
    assert incidents[0]["service"] == "auth-service"


def test_incident_has_required_fields():
    window = [sample() for _ in range(9)] + [sample(mem=99)]
    inc = detect("auth-service", window)[0]
    for field in ["incident_id", "timestamp", "service", "reason", "recovery_status"]:
        assert field in inc
