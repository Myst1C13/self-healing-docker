import json

import pytest

from infra.aws.handlers.archive_incident import archive_incident
from src.aws_exporter import EventBridgeIncidentExporter, exporter_from_env


def incident():
    return {
        "incident_id": "inc_aws",
        "timestamp": "2026-08-09T01:00:00+00:00",
        "service": "auth-service",
        "incident_type": "high_cpu_anomaly",
        "recovery_status": "recovered",
        "recovery_latency_ms": 18.25,
    }


class EventsClient:
    def __init__(self, response=None):
        self.response = response or {"FailedEntryCount": 0, "Entries": [{"EventId": "evt-1"}]}
        self.entries = None

    def put_events(self, Entries):
        self.entries = Entries
        return self.response


def test_eventbridge_exporter_publishes_the_recovered_incident():
    client = EventsClient()
    receipt = EventBridgeIncidentExporter("incident-bus", client).publish(incident())
    entry = client.entries[0]
    assert entry["Source"] == "self-healing-docker"
    assert entry["DetailType"] == "IncidentRecovered"
    assert json.loads(entry["Detail"])["incident_id"] == "inc_aws"
    assert receipt == {"event_id": "evt-1", "event_bus": "incident-bus"}


def test_eventbridge_exporter_surfaces_partial_failures():
    client = EventsClient({"FailedEntryCount": 1, "Entries": [{"ErrorCode": "AccessDeniedException"}]})
    with pytest.raises(RuntimeError, match="AccessDeniedException"):
        EventBridgeIncidentExporter("incident-bus", client).publish(incident())


def test_export_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AWS_EXPORT_ENABLED", raising=False)
    assert exporter_from_env() is None


class Table:
    def put_item(self, Item):
        self.item = Item


class S3:
    def put_object(self, **kwargs):
        self.object = kwargs


def test_lambda_archives_to_dynamodb_and_s3():
    table = Table()
    s3 = S3()
    event = {"id": "evt-1", "time": "2026-08-09T01:00:01Z", "detail": incident()}
    result = archive_incident(event, table, s3, "archive-bucket")
    assert table.item["incident_id"] == "inc_aws"
    assert str(table.item["recovery_latency_ms"]) == "18.25"
    assert s3.object["Bucket"] == "archive-bucket"
    assert s3.object["Key"] == "incidents/2026-08-09/inc_aws.json"
    assert s3.object["ServerSideEncryption"] == "AES256"
    assert result["archive_key"] == s3.object["Key"]


def test_lambda_rejects_an_incomplete_event():
    with pytest.raises(ValueError, match="incident event missing"):
        archive_incident({"detail": {"incident_id": "bad"}}, Table(), S3(), "archive-bucket")
