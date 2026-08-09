# AWS incident archive

The Docker control plane remains local because it needs access to the Docker
Engine socket. AWS is an optional, event-driven incident archive:

```text
local control loop
  └─ SQLite commit
      └─ EventBridge PutEvents
          └─ custom event bus + rule
              └─ Lambda archive handler
                  ├─ DynamoDB searchable incident record
                  └─ S3 immutable JSON archive
```

The local SQLite write happens before the cloud export, so an AWS outage does
not erase the incident. Export success/failure is written back to the local
incident record.

## Deploy

Requirements: AWS CLI credentials and AWS SAM CLI.

```bash
cd infra/aws
sam validate --lint
sam build
sam deploy --guided
```

Record the stack outputs, attach `LocalExporterPolicyArn` to the IAM identity
running the control plane, then configure:

```bash
export AWS_EXPORT_ENABLED=true
export AWS_REGION=us-east-1
export AWS_EVENT_BUS_NAME=self-healing-docker-dev
```

Run the control plane normally. Each locally persisted recovery publishes an
`IncidentRecovered` event. The Lambda target stores a queryable DynamoDB item
and a versioned, encrypted S3 object.

## Cost and teardown

The template uses on-demand DynamoDB, Lambda, EventBridge, and S3. Charges still
depend on traffic and retention. Remove the stack when finished:

```bash
sam delete
```

The versioned S3 bucket may need to be emptied before CloudFormation can delete
it.
