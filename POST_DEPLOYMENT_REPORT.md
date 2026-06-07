# YenkasaCode Agent - Post Deployment Report

Date: 2026-06-06

## Status

Cloud Run service is deployed and operational.

Service URL:

```text
https://yenkasa-code-agent-3vx2nvls4a-ew.a.run.app
```

Latest ready revision:

```text
yenkasa-code-agent-00003-kk9
```

Traffic:

```text
100%
```

## Completed Deployment Work

- Tests passed.
- Docker image built successfully in Cloud Build.
- Image pushed to Artifact Registry.
- Secret Manager API enabled.
- Required secret containers created.
- Known secret versions added.
- Artifact bucket created.
- Bucket versioning enabled.
- Uniform bucket-level access enabled.
- Cloud Run deployed privately.
- Workload identity used instead of service account JSON.
- Authenticated health and readiness checks passed.

## Endpoint Validation

Validated against Cloud Run:

- `GET /health`: `200`
- `GET /ready`: `200`
- `GET /api/agent/agents`: `200`
- `GET /api/agent/metrics`: `200`
- `POST /api/agent/query`: `200`

## Agent Validation

Validated live on Cloud Run:

- `DatabaseAgent`: success
- `RepositoryAgent`: success
- `VectorSearchAgent`: success
- `CodeAuditAgent`: success
- `RefactorAgent`: success
- `CloudRunAgent`: success
- `ObservabilityAgent`: success
- `ProductBuilderAgent`: success
- YIO: success

## Observations

- `repo_chunks` currently returned count `0`, so repository intelligence is operational but the target Atlas database appears empty for that collection.
- The service is private and requires both Cloud Run IAM invocation and app-level `X-API-Key`.
