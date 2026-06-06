# YenkasaCode Agent - API Reference

Date: 2026-06-06

## Base URL

Cloud Run URL is not assigned yet because deployment is blocked pending secret versions.

After deployment:

```text
https://<cloud-run-url>
```

## Authentication

All API endpoints require:

```text
X-API-Key: <api-key>
```

Cloud Run is intended to be private for internal alpha, so callers also need Cloud Run IAM invocation access.

## Roles

Supported app roles:

- `viewer`
- `developer`
- `admin`

Internal alpha currently uses one generated API key mapped to all roles. Production should use separate role keys.

## Endpoints

### Health

```http
GET /health
```

Minimum role:

```text
viewer
```

Response:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "registered_agents": 9
}
```

### Readiness

```http
GET /ready
```

Minimum role:

```text
admin
```

Response:

```json
{
  "status": "ready",
  "checks": {
    "mongodb": {"ok": true, "error": null},
    "vertex_ai": {"ok": true, "error": null},
    "cloud_run": {"ok": true, "error": null},
    "cloud_logging": {"ok": true, "error": null}
  }
}
```

### List Agents

```http
GET /api/agent/agents
```

Minimum role:

```text
viewer
```

Response:

```json
[
  {
    "name": "DatabaseAgent",
    "description": "...",
    "capabilities": []
  }
]
```

### Metrics

```http
GET /api/agent/metrics
```

Minimum role:

```text
admin
```

Response includes global and per-agent counters, failures, and duration metrics.

### Query Agent

```http
POST /api/agent/query
```

Minimum role:

Depends on selected agent or inferred intent.

Request:

```json
{
  "query": "Show repository inventory.",
  "agent": "RepositoryAgent",
  "context": {}
}
```

Response:

```json
{
  "agent": "RepositoryAgent",
  "success": true,
  "result": {},
  "error": null
}
```

## Agent Routing

Admin-level queries:

- `DatabaseAgent`
- `CloudRunAgent`
- `ObservabilityAgent`
- Metrics and readiness

Developer-level queries:

- `RepositoryAgent`
- `CodeAuditAgent`
- `RefactorAgent`
- `ProductBuilderAgent`

Viewer-level queries:

- `system`
- `VectorSearchAgent`
- Health
- Agent discovery

## Request Limits

Configured defaults:

- Max request body: `65536` bytes
- Max query length: `2000`
- Max context keys: `50`

## Error Format

Validation error:

```json
{
  "detail": "Invalid request."
}
```

Agent error:

```json
{
  "agent": "DatabaseAgent",
  "success": false,
  "result": {},
  "error": "Request failed."
}
```

Sensitive values such as tokens, secrets, credentials, and MongoDB connection strings are redacted.
