from decimal import Decimal
import json
import os


def _dynamo_safe(value):
    return json.loads(json.dumps(value), parse_float=Decimal)


def archive_incident(event, table, s3_client, bucket_name):
    incident = event.get("detail") or {}
    required = {"incident_id", "timestamp", "service", "incident_type"}
    missing = sorted(required - incident.keys())
    if missing:
        raise ValueError("incident event missing: " + ", ".join(missing))

    item = _dynamo_safe({
        **incident,
        "eventbridge_event_id": event.get("id"),
        "eventbridge_time": event.get("time"),
    })
    table.put_item(Item=item)

    day = incident["timestamp"][:10]
    key = f"incidents/{day}/{incident['incident_id']}.json"
    body = json.dumps(incident, indent=2, sort_keys=True).encode("utf-8")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=body,
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )
    return {"incident_id": incident["incident_id"], "archive_key": key}


def handler(event, _context):
    import boto3

    table_name = os.environ["INCIDENT_TABLE_NAME"]
    bucket_name = os.environ["INCIDENT_BUCKET_NAME"]
    table = boto3.resource("dynamodb").Table(table_name)
    return archive_incident(event, table, boto3.client("s3"), bucket_name)
