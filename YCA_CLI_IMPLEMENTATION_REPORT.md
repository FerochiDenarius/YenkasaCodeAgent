# YenkasaCodeAgent CLI Implementation Report

Date: 2026-06-08

## Objective

Build a local developer CLI for testing YenkasaCodeAgent agents individually and through orchestration from a MacBook.

## Files Added

- `app/cli.py`
  - Implements the `yca` command surface.
  - Handles YenkasaAI login.
  - Stores JWT/session metadata under `~/.yca/config.json`.
  - Calls YenkasaCodeAgent endpoints.
  - Writes local JSONL logs under `logs/yca.jsonl`.

- `yca`
  - Shell launcher.
  - Uses `.venv312/bin/python` when available.
  - Falls back to `.venv/bin/python`, then `python3`.

- `YCA_CLI.md`
  - Full CLI usage documentation.

- `YCA_CLI_IMPLEMENTATION_REPORT.md`
  - Implementation and validation notes.

- `.gitignore`
  - Ignores Python cache files, pytest cache, local CLI logs, and office lock/temp files.

## Files Changed

- `app/security/auth.py`
  - Keeps existing `X-API-Key` authentication.
  - Adds YenkasaAI JWT authentication.
  - Accepts app JWTs from `X-Yenkasa-AI-Authorization`.
  - Still accepts standard `Authorization: Bearer` for local/backward compatibility.
  - Validates JWTs by calling YenkasaAI `GET /api/auth/me`.
  - Maps YenkasaAI roles into Code Agent roles:
    - `admin`, `super_admin`, `senior_developer` -> `admin`
    - `developer`, `maintainer` -> `developer`
    - everything else -> `viewer`

- `app/config/settings.py`
  - Adds `VERTEX_EMBEDDING_DIMENSIONS`, default `768`.
  - Adds `YENKASA_AI_BASE_URL`.
  - Adds `YENKASA_AI_AUTH_TIMEOUT_SECONDS`.

- `app/services/embedding_service.py`
  - Requests Vertex embeddings with `output_dimensionality=768`.
  - Validates returned vector length before querying Atlas.

- `tests/test_phase1.py`
  - Adds test coverage for `X-Yenkasa-AI-Authorization` endpoint authorization.

- `README.md`
  - Adds developer CLI quick-start.

## Command Coverage

Implemented commands:

```bash
yca login
yca agents
yca agent <AgentName> status
yca repos
yca repo scan
yca repo stats
yca search "<query>"
yca open <path>
yca audit
yca memory status
yca memory query "<query>"
yca indexing status
yca indexing run
yca analytics status
yca orchestration test
yca doctor
```

## Authentication Design

The CLI uses YenkasaAI credentials only.

Flow:

1. `yca login`
2. CLI calls YenkasaAI `POST /api/auth/login`
3. CLI stores the returned access token in `~/.yca/config.json`
4. Agent calls include:

```text
X-Yenkasa-AI-Authorization: Bearer <jwt>
```

YenkasaCodeAgent validates the token against:

```text
GET /api/auth/me
```

The existing `X-API-Key` path remains available for internal automation.

## Cloud Run IAM Design

If the target Code Agent URL contains `.run.app`, the CLI attempts to get a Google identity token using:

```bash
gcloud auth print-identity-token
```

It sends that token as:

```text
X-Serverless-Authorization: Bearer <identity-token>
```

This prevents conflict with the YenkasaAI application JWT.

## Agent Alias Mapping

The CLI accepts developer-facing aliases:

```text
RepoAgent        -> RepositoryAgent
MemoryAgent      -> VectorSearchAgent
SearchAgent      -> VectorSearchAgent
AuditAgent       -> CodeAuditAgent
AnalyticsAgent   -> DatabaseAgent
CodeReviewAgent  -> CodeAuditAgent
IndexingAgent    -> RepositoryAgent
```

## Validation

Local validation:

```bash
./.venv312/bin/python -m compileall app
./.venv312/bin/python -m pytest tests/test_phase1.py -q
```

Result:

```text
63 passed, 1 warning
```

Production deployment:

```text
yenkasa-code-agent-00007-bns
```

Production CLI smoke test:

```bash
./yca login
./yca agents
./yca search "livestreamPermissions"
./yca memory query "livestream permissions"
```

Observed:

- `yca login`: succeeded and stored token.
- `yca agents`: listed 9 agents.
- `yca search`: reached `VectorSearchAgent`.
- `yca memory query`: reached `VectorSearchAgent` and returned memory matches.
- Previous vector dimension error was gone.
- `yca memory status` returned `403` for the regular audit account because it routes to admin-only `DatabaseAgent`. This is expected. Use a YenkasaAI `senior_developer`, `admin`, or `super_admin` account for full `doctor` coverage.

## Remaining Data-Source Note

`RepositoryAgent` currently reads repository inventory from Mongo `ai_embeddings`. The user clarified that repository metadata may now live under PostgreSQL-backed `github_repositories`.

If repository inventory still returns empty after this CLI work, the backend repository data source needs a separate fix:

- inspect the PostgreSQL `ai_documents` collections,
- confirm where migrated repository metadata lives,
- point `RepositoryAgent` and repository stats commands at that source,
- or create a sync/indexing path that writes repository chunks back into the vector-search collection.

The CLI is ready to expose and validate that once the backend repository source is corrected.
