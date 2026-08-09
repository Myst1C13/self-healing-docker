import json
import os
import sqlite3
import threading

DATA_DIR = os.getenv("DATA_DIR", "data")
INCIDENT_DB_PATH = os.getenv("INCIDENT_DB_PATH", os.path.join(DATA_DIR, "incidents.db"))
_lock = threading.Lock()


def _connect():
    parent = os.path.dirname(INCIDENT_DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    connection = sqlite3.connect(INCIDENT_DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("pragma journal_mode = wal")
    connection.execute("""
        create table if not exists incidents (
            incident_id text primary key,
            timestamp text not null,
            service text not null,
            incident_type text not null,
            recovery_status text not null,
            recovery_latency_ms real,
            payload text not null
        )
    """)
    connection.execute("create index if not exists incidents_service_time on incidents(service, timestamp desc)")
    return connection


def _write(connection, incident):
    connection.execute(
        """insert or replace into incidents
           (incident_id, timestamp, service, incident_type, recovery_status, recovery_latency_ms, payload)
           values (?, ?, ?, ?, ?, ?, ?)""",
        (
            incident["incident_id"],
            incident["timestamp"],
            incident["service"],
            incident["incident_type"],
            incident.get("recovery_status", "triggered"),
            incident.get("recovery_latency_ms"),
            json.dumps(incident),
        ),
    )


def save_incident(incident):
    with _lock, _connect() as connection:
        _write(connection, incident)
    return incident


def update_incident(incident_id, **fields):
    with _lock, _connect() as connection:
        row = connection.execute("select payload from incidents where incident_id = ?", (incident_id,)).fetchone()
        if not row:
            return None
        incident = json.loads(row["payload"])
        incident.update(fields)
        _write(connection, incident)
        return incident


def get_incidents(service=None, limit=100):
    safe_limit = max(1, min(int(limit), 500))
    query = "select payload from incidents"
    params = []
    if service:
        query += " where service = ?"
        params.append(service)
    query += " order by timestamp desc limit ?"
    params.append(safe_limit)
    with _lock, _connect() as connection:
        return [json.loads(row["payload"]) for row in connection.execute(query, params)]


def stats():
    with _lock, _connect() as connection:
        rows = connection.execute("select service, incident_type, recovery_status, recovery_latency_ms from incidents").fetchall()
    by_service = {}
    by_type = {}
    latencies = []
    recovered = 0
    for row in rows:
        by_service[row["service"]] = by_service.get(row["service"], 0) + 1
        by_type[row["incident_type"]] = by_type.get(row["incident_type"], 0) + 1
        if row["recovery_status"] == "recovered":
            recovered += 1
        if row["recovery_latency_ms"] is not None:
            latencies.append(row["recovery_latency_ms"])
    return {
        "total_incidents": len(rows),
        "recovered": recovered,
        "recovery_rate_percent": round(recovered / len(rows) * 100, 1) if rows else 0,
        "mean_recovery_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "by_service": by_service,
        "by_type": by_type,
    }


def clear():
    with _lock, _connect() as connection:
        connection.execute("delete from incidents")
