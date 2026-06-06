# YenkasaCode Agent - Deployment Readiness Report

Date: 2026-06-06

## Target

- Project: `project-10405180-0afd-4ecc-9f8`
- Service: `yenkasa-code-agent`
- Region: `europe-west1`
- Artifact Registry repository requested: `YenkasaCodeAgent`
- Artifact Registry repository created: `yenkasa-code-agent`

Artifact Registry requires lowercase repository IDs, so the compliant repository ID is `yenkasa-code-agent`.

## Validation Results

### Tests

Command:

```bash
.venv312/bin/python -m pytest -q
```

Result:

```text
52 passed, 3 skipped, 1 warning
```

The 3 skipped tests are live integration tests gated behind `RUN_INTEGRATION_TESTS=1`.

### Production Hardening

Status: complete

Verified controls:

- API key authentication is enabled.
- Role-based authorization is enabled.
- Rate limiting is enabled.
- Request body, query length, and context size limits are enabled.
- Sanitized errors are returned to clients.
- MongoDB, Vertex AI, Cloud Run, and Cloud Logging calls use timeouts.
- `/ready` endpoint exists.
- Docker runs as non-root and includes a healthcheck.
- Dependencies are pinned.

Reference: `PRODUCTION_HARDENING_REPORT.md`

### Docker Build

Local Docker status: unavailable on this machine.

Cloud Build was used for Docker validation.

Build ID:

```text
b8681055-dbb6-4b92-8850-1a0bf3847a09
```

Result:

```text
SUCCESS
```

Image:

```text
europe-west1-docker.pkg.dev/project-10405180-0afd-4ecc-9f8/yenkasa-code-agent/yenkasa-code-agent:alpha
```

### Requirements

Status: pinned

Pinned dependencies are defined in `requirements.txt`.

### Authentication

Status: enabled

Protected endpoints:

- `GET /health`
- `GET /ready`
- `GET /api/agent/agents`
- `GET /api/agent/metrics`
- `POST /api/agent/query`

### Readiness Endpoint

Status: implemented locally, not yet validated on Cloud Run.

Cloud Run deployment is blocked until required secret versions are added for:

- `MONGODB_URI`
- `GOOGLE_APPLICATION_CREDENTIALS_JSON`

## Readiness Decision

Code and image readiness: pass

Cloud Run deployment readiness: blocked

Reason:

Secret Manager resources exist, but `MONGODB_URI` and `GOOGLE_APPLICATION_CREDENTIALS_JSON` have no enabled secret versions. Deploying without them would not satisfy the requirement that live readiness checks pass.
