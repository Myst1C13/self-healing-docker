import json
import os
import threading

# incidents live in memory but also get written to a json file so we don't
# lose everything on restart
DATA_DIR = os.getenv("DATA_DIR", "data")
INCIDENTS_FILE = os.path.join(DATA_DIR, "incidents.json")

_lock = threading.Lock()
_incidents = []


def _load():
    if _incidents:
        return
    if os.path.exists(INCIDENTS_FILE):
        try:
            with open(INCIDENTS_FILE) as f:
                _incidents.extend(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass


def _save_to_disk():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(INCIDENTS_FILE, "w") as f:
        json.dump(_incidents, f, indent=2)


def save_incident(incident):
    with _lock:
        _load()
        _incidents.append(incident)
        _save_to_disk()
    return incident


def update_incident(incident_id, **fields):
    with _lock:
        _load()
        for inc in _incidents:
            if inc["incident_id"] == incident_id:
                inc.update(fields)
                _save_to_disk()
                return inc
    return None


def get_incidents(service=None, limit=100):
    with _lock:
        _load()
        items = _incidents
        if service:
            items = [i for i in items if i["service"] == service]
        # newest first
        return list(reversed(items))[:limit]


def stats():
    with _lock:
        _load()
        by_service = {}
        by_type = {}
        recovered = 0
        for inc in _incidents:
            by_service[inc["service"]] = by_service.get(inc["service"], 0) + 1
            by_type[inc["incident_type"]] = by_type.get(inc["incident_type"], 0) + 1
            if inc.get("recovery_status") == "recovered":
                recovered += 1
        return {
            "total_incidents": len(_incidents),
            "recovered": recovered,
            "by_service": by_service,
            "by_type": by_type,
        }


def clear():
    with _lock:
        _incidents.clear()
        if os.path.exists(INCIDENTS_FILE):
            os.remove(INCIDENTS_FILE)
