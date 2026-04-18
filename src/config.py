
SERVICES = ["auth-service", "payments-service", "api-gateway"]


SERVICE_PORTS = {
    "auth-service": 8001,
    "payments-service": 8002,
    "api-gateway": 8003
}


WINDOW_SIZE = 10


THRESHOLDS = {
    "cpu_percent":    {"critical": 85,   "z_score": 2.5},
    "memory_percent": {"critical": 90,   "z_score": 2.5},
    "latency_ms":     {"critical": 500,  "z_score": 2.5},
    "error_rate":     {"critical": 0.10, "z_score": 2.5},
    "restart_count":  {"critical": 3}
}


POLL_INTERVAL_SECONDS = 5
CHAOS_DURATION_SECONDS = 30