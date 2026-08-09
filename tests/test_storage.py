from src import storage


def incident(identifier="inc_1", service="auth-service"):
    return {
        "incident_id": identifier,
        "timestamp": "2026-08-08T12:00:00+00:00",
        "service": service,
        "incident_type": "high_cpu_anomaly",
        "signals": {"cpu_percent": 99},
        "recovery_status": "recovered",
        "recovery_latency_ms": 12.5,
    }


def test_sqlite_store_persists_and_filters_incidents(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "INCIDENT_DB_PATH", str(tmp_path / "incidents.db"))
    storage.save_incident(incident())
    storage.save_incident(incident("inc_2", "payments-service"))
    assert [item["incident_id"] for item in storage.get_incidents(service="auth-service")] == ["inc_1"]


def test_sqlite_store_updates_payload_and_indexed_status(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "INCIDENT_DB_PATH", str(tmp_path / "incidents.db"))
    storage.save_incident(incident())
    updated = storage.update_incident("inc_1", recovery_status="failed", recovery_detail="daemon unavailable")
    assert updated["recovery_status"] == "failed"
    assert storage.get_incidents()[0]["recovery_detail"] == "daemon unavailable"


def test_stats_report_recovery_rate_and_latency(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "INCIDENT_DB_PATH", str(tmp_path / "incidents.db"))
    storage.save_incident(incident())
    failed = incident("inc_2")
    failed["recovery_status"] = "failed"
    failed["recovery_latency_ms"] = 7.5
    storage.save_incident(failed)
    result = storage.stats()
    assert result["total_incidents"] == 2
    assert result["recovery_rate_percent"] == 50.0
    assert result["mean_recovery_latency_ms"] == 10.0
