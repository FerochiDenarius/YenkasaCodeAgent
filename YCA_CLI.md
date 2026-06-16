# YenkasaCodeAgent Developer CLI

`yca` is an internal CLI for testing YenkasaCodeAgent from a MacBook.

## Setup

From this repository:

```bash
./.venv312/bin/pip install -r requirements.txt
./yca login
./yca
```

If the launcher is on your `PATH`, use `yca` directly:

```bash
yca login
yca
```

The CLI authenticates against YenkasaAI and stores the returned JWT locally in:

```text
~/.yca/config.json
```

Request and failure logs are written locally to:

```text
logs/yca.jsonl
```

Secrets and bearer tokens are redacted from the local log file.

## Authentication Flow

`yca login` posts your YenkasaAI email/password to:

```text
POST /api/auth/login
```

Agent calls then send the YenkasaAI access token to YenkasaCodeAgent using:

```text
X-Yenkasa-AI-Authorization: Bearer <jwt>
```

The server validates that token against:

```text
GET /api/auth/me
```

The existing `X-API-Key` path still works for service-to-service calls and health checks. The CLI does not require a separate Code Agent API key.

## Cloud Run IAM

The production YenkasaCodeAgent service may still require Cloud Run IAM invocation. When the target URL contains `.run.app`, `yca` automatically runs:

```bash
gcloud auth print-identity-token
```

and sends the result as:

```text
X-Serverless-Authorization: Bearer <identity-token>
```

This keeps Cloud Run IAM separate from YenkasaAI application authentication.

Disable this only for local testing:

```bash
./yca --cloud-run-iam off --code-agent-url http://127.0.0.1:8080 agents
```

## Commands

Running `./yca` without a command starts interactive mode. After login, type normal questions or run short commands without the `./yca` prefix:

```text
yca> what repositories are indexed?
yca> agents
yca> search livestreamPermissions
yca> audit
yca> exit
```

You can still run one-shot commands from the shell:

```bash
./yca agents
./yca agent RepoAgent status
./yca repos
./yca repo stats
./yca repo scan
./yca search "livestreamPermissions"
./yca open path/to/file.js
./yca audit
./yca memory status
./yca memory query "livestream permissions"
./yca indexing status
./yca indexing run
./yca analytics status
./yca orchestration test
./yca doctor
```

Inside interactive mode, Ctrl-D exits `yca` and returns to your shell. At a normal shell prompt, Ctrl-D exits the terminal session. Use Ctrl-C to cancel a running CLI command.

## Command Behavior

`yca agents`

- Calls `/health` and `/api/agent/agents`.
- Displays agent name, status, version, heartbeat timestamp, and response latency.
- Requires YenkasaAI user role that maps to Code Agent `viewer` or above.

`yca agent <AgentName> status`

- Calls one registered agent directly through `/api/agent/query`.
- The target agent's server-side role policy still applies.

`yca repos`

- Calls `RepositoryAgent` with `Show repository inventory`.

`yca repo stats`

- Calls `DatabaseAgent` for repository/indexing counts and latest indexed file metadata.
- Requires a YenkasaAI role that maps to Code Agent `admin`.

`yca search "<query>"`

- Calls `VectorSearchAgent` directly.
- Requires `viewer` or above.

`yca audit`

- Calls `CodeAuditAgent`.
- Requires `developer` or above.

`yca memory status`

- Calls `DatabaseAgent`.
- Requires `admin`.

`yca memory query "<query>"`

- Calls `VectorSearchAgent`.
- Requires `viewer` or above.

`yca doctor`

- Runs authentication, repo access, indexing, memory, search, audit, and orchestration checks and writes a diagnostic report to `logs/yca.jsonl`.
- Requires an admin-capable YenkasaAI account for every check to pass.

## Role Mapping

YenkasaCodeAgent maps YenkasaAI user roles as follows:

```text
admin, super_admin, senior_developer -> admin
developer, maintainer                -> developer
other authenticated users             -> viewer
```

Commands that route to `DatabaseAgent`, `CloudRunAgent`, or `ObservabilityAgent` require `admin`. Commands that route to `RepositoryAgent`, `CodeAuditAgent`, `RefactorAgent`, or `ProductBuilderAgent` require `developer`. Vector search and discovery commands work for `viewer`.

## Configuration

Defaults point at production:

```text
YCA_YENKASA_AI_URL=https://yenkasa-ai-backend-496173204476.europe-west1.run.app
YCA_CODE_AGENT_URL=https://yenkasa-code-agent-3vx2nvls4a-ew.a.run.app
```

Override per command:

```bash
./yca --code-agent-url http://127.0.0.1:8080 agents
```

## Agent Aliases

The CLI accepts short names from the developer spec and maps them to current registered agents:

```text
RepoAgent        -> RepositoryAgent
MemoryAgent      -> VectorSearchAgent
SearchAgent      -> VectorSearchAgent
AuditAgent       -> CodeAuditAgent
AnalyticsAgent   -> DatabaseAgent
CodeReviewAgent  -> CodeAuditAgent
IndexingAgent    -> RepositoryAgent
```

## Current Backend Notes

- The server accepts both `X-API-Key` and YenkasaAI JWT auth.
- The CLI uses `X-Yenkasa-AI-Authorization` so Cloud Run IAM can use `X-Serverless-Authorization` without clobbering app auth.
- `VectorSearchAgent` now requests 768-dimensional Vertex embeddings to match the Atlas vector index.
- Validation with a regular audit account confirmed `yca agents`, `yca search`, and `yca memory query` work. Admin-only commands correctly return `403` for non-admin users.
- Repository inventory still depends on the configured repository data source. If migrated repository metadata lives in PostgreSQL `github_repositories` rather than Mongo `ai_embeddings`, the backend repository service must be pointed at that source for non-empty repository inventory.
