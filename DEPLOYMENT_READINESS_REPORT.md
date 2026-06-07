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
54 passed, 3 skipped, 1 warning
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

Final build ID:

```text
14109790-8087-458d-8ede-6c21285b0d63
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

Status: validated on Cloud Run.

Cloud Run readiness result:

```text
GET /ready -> 200
```

Readiness checks passed:

- MongoDB
- Vertex AI
- Cloud Run
- Cloud Logging

## Readiness Decision

Code and image readiness: pass

Cloud Run deployment readiness: pass

Deployment:

- Service: `yenkasa-code-agent`
- URL: `https://yenkasa-code-agent-3vx2nvls4a-ew.a.run.app`
- Revision: `yenkasa-code-agent-00003-kk9`
- Traffic: `100%`
