import threading

# docker might not be importable in test env, don't blow up if it isn't
try:
    import docker
except ImportError:
    docker = None

_lock = threading.Lock()
_restart_counts = {}
_client = None


def _get_client():
    global _client
    if _client is None:
        if docker is None:
            raise RuntimeError("docker SDK not installed")
        _client = docker.from_env()
    return _client


def restart_count(service):
    return _restart_counts.get(service, 0)


def _restart_container(service):
    # container_name in docker-compose matches the service name
    try:
        c = _get_client().containers.get(service)
        c.restart(timeout=5)
        with _lock:
            _restart_counts[service] = _restart_counts.get(service, 0) + 1
        return "recovered", "restarted container " + service
    except Exception as e:
        return "failed", "restart failed: " + str(e)


def recover(incident):
    action = incident.get("recovery_action")
    service = incident["service"]

    if action == "restart_container":
        status, detail = _restart_container(service)
    elif action == "flag_possible_leak":
        status, detail = "flagged", "possible memory leak, flagged for review"
    elif action == "mark_service_degraded":
        status, detail = "degraded", "service marked degraded"
    elif action == "escalate_critical":
        status, detail = "escalated", "escalated to on-call"
    else:
        status, detail = "no_action", "no handler for action " + str(action)

    incident["recovery_status"] = status
    incident["recovery_detail"] = detail
    print("[recovery]", service, incident["incident_type"], "->", status)
    return incident
