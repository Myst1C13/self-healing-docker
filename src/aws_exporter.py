import json
import os


class EventBridgeIncidentExporter:
    """Publish locally persisted incidents to a custom EventBridge bus."""

    def __init__(self, event_bus_name, client):
        if not event_bus_name:
            raise ValueError("event_bus_name is required")
        self.event_bus_name = event_bus_name
        self.client = client

    def publish(self, incident):
        response = self.client.put_events(
            Entries=[{
                "Source": "self-healing-docker",
                "DetailType": "IncidentRecovered",
                "Detail": json.dumps(incident, separators=(",", ":"), sort_keys=True),
                "EventBusName": self.event_bus_name,
            }]
        )
        if response.get("FailedEntryCount", 0):
            entry = (response.get("Entries") or [{}])[0]
            message = entry.get("ErrorMessage") or entry.get("ErrorCode") or "unknown EventBridge failure"
            raise RuntimeError(message)
        event_id = (response.get("Entries") or [{}])[0].get("EventId")
        return {"event_id": event_id, "event_bus": self.event_bus_name}


def exporter_from_env(client=None):
    enabled = os.getenv("AWS_EXPORT_ENABLED", "").lower() in {"1", "true", "yes"}
    if not enabled:
        return None
    event_bus = os.getenv("AWS_EVENT_BUS_NAME")
    if not event_bus:
        raise RuntimeError("AWS_EVENT_BUS_NAME is required when AWS_EXPORT_ENABLED=true")
    if client is None:
        import boto3
        client = boto3.client("events", region_name=os.getenv("AWS_REGION"))
    return EventBridgeIncidentExporter(event_bus, client)
