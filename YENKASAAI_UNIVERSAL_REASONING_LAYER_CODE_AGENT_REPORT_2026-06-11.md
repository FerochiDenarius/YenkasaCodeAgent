# YenkasaAI Universal Reasoning Layer Code Agent Report

Date: 2026-06-11

## Scope

This report documents the cross-service completion work in `yenkasa-code-agent` after the YenkasaAI backend OIL reasoning baseline was deployed.

Goal:

- Make Code Agent agents act as evidence collectors.
- Add a reasoning boundary before public API responses.
- Stop RepositoryAgent inventory from being the main user-facing answer.

## Completed

### 1. Evidence Package Contract

Added:

```text
app/utils/evidence_package.py
```

Updated:

```text
app/models/agent.py
app/agents/base.py
```

Every `BaseAgent.execute()` response now includes:

```json
{
  "agent": "RepositoryAgent",
  "facts": {},
  "sources": [],
  "confidence": 0.96,
  "recommendations": [],
  "query": "...",
  "success": true,
  "error": null
}
```

The raw internal `result` remains available for internal agent-to-agent dependencies, but the public route now goes through reasoning before returning to clients. Finalized public `result` does not include `raw_evidence` by default.

### 2. Code Agent Reasoning Engine

Added:

```text
app/orchestrator/reasoning_engine.py
```

The Code Agent reasoning engine:

- Interprets agent evidence packages.
- Generates natural-language `answer` and `summary`.
- Keeps structured `facts`, `sources`, `recommendations`, and `confidence`.
- Summarizes repository and database inventory facts instead of exposing raw rows as the main result.
- Adds `reasoning` metadata to responses.

### 3. Public API Reasoning Boundary

Updated:

```text
app/core/orchestrator.py
```

`YenkasaCodeOrchestrator.route()` now finalizes every public `/api/agent/query` response through `ReasoningEngine`.

This applies to:

- Direct agent calls.
- YIO multi-agent calls.
- Unknown-agent errors.

### 4. YIO Evidence Synthesis

Updated:

```text
app/orchestrator/yio.py
app/orchestrator/response_synthesizer.py
```

YIO now carries evidence packages from planned agents into `agent_results`.

Public YIO responses now include:

- `answer`
- `summary`
- `plan`
- `findings`
- `evidence`
- `facts`
- `sources`
- `recommendations`
- `confidence`
- `agent_results`

Raw agent rows are not exposed in finalized `result` by default.

### 5. RepositoryAgent Response Quality

RepositoryAgent raw inventory is now interpreted at the public response boundary.

Before:

```json
{
  "repositories": [
    {
      "repository": "yenkasaChat",
      "chunk_count": 4123,
      "file_count": 1458
    }
  ]
}
```

After:

```text
I can see indexed repository snapshots.
Latest indexed repository: yenkasaChat on 2026-06-11T10:00:00Z.
I do not see evidence of an active scan currently running.
Repositories: yenkasaChat.
```

Largest-repository response example:

```text
The largest indexed repository is YenkasaCodeAgent with 13,438 chunks.
```

## Files Changed

Added:

- `app/orchestrator/reasoning_engine.py`
- `app/utils/evidence_package.py`
- `YENKASAAI_UNIVERSAL_REASONING_LAYER_CODE_AGENT_REPORT_2026-06-11.md`

Updated:

- `app/models/agent.py`
- `app/agents/base.py`
- `app/orchestrator/yio.py`
- `app/orchestrator/response_synthesizer.py`
- `app/core/orchestrator.py`
- `tests/test_phase1.py`

## Tests

Command:

```bash
.venv312/bin/python -m pytest
```

Result:

```text
70 passed, 3 skipped, 1 warning
```

## Deployment

Completed.

Cloud Run:

- Service: `yenkasa-code-agent`
- Revision: `yenkasa-code-agent-00011-hhj`
- Traffic: `100%`
- URL: `https://yenkasa-code-agent-496173204476.europe-west1.run.app`

Live verification query:

```text
Do you see my repo being scanned now or do you have snapshots?
```

Live result:

```text
I can see indexed repository snapshots.
Latest indexed repository: YenkasaCodeAgent on 2026-06-08T00:04:57.773729.
I do not see evidence of an active scan currently running.
Repositories: 3girlsVehicleRentals, krabehwe-receipt, PayrollSheet, PersonBMI, student-results, triciabales, yenkasa, YenkasaAi, yenkasaChat, YenkasaChatSignaling, YenkasaCodeAgent, yenkasaCommunity.
```

Verified structured facts:

- `repository_count=12`
- `total_files=4,792`
- `total_chunks=18,848`
- `latest_repository=YenkasaCodeAgent`
- `raw_result_available=false`
- no `raw_evidence` field in finalized `result`

## Remaining Notes

This completes the practical public-response architecture:

```text
User
-> Intent Router
-> Agent evidence collection
-> Evidence package
-> ReasoningEngine
-> Final response
```

Internal agent-to-agent calls still read raw `result` for compatibility. That is intentional so CodeAuditAgent and RefactorAgent continue to compose lower-level agents without a larger rewrite.

## Follow-Up Fix: Repository Question File Search

User-reported failure:

```text
are you aware am hosting my call and video call server on heroku ?check my repo
```

Bad behavior:

- YIO selected repository inventory only.
- The answer counted repositories and chunks.
- It did not search indexed source files for Heroku, call server, video call, signaling, WebSocket, Procfile, or deployment evidence.

Additional changes made:

- `app/orchestrator/intent_classifier.py`
  - Added repository/code-inspection trigger terms:
    - `check`
    - `heroku`
    - `procfile`
    - `dyno`
    - `call server`
    - `video call`
    - `video server`
    - `signaling`
    - `signalling`
    - `websocket`
    - `socket.io`
    - `socketio`
    - `server`
- `app/core/orchestrator.py`
  - Added the same terms to direct vector-search intent selection.
- `app/orchestrator/reasoning_engine.py`
  - Added YIO repository-source reasoning.
  - Repository inventory is now treated as coverage context.
  - Vector search matches are used as the user-facing answer.
  - If file-level evidence is missing, the answer says that explicitly instead of pretending repository counts answer the question.
- `tests/test_phase1.py`
  - Added regression coverage for the Heroku/video-call repo question.
  - Added regression coverage that YIO answers with file paths/snippets and does not expose `Selected agents` or raw evidence.

Updated local test result:

```text
72 passed, 3 skipped, 1 warning
```

Expected behavior after deployment:

```text
I checked the indexed repository source and found file-level evidence.
- yenkasaChat Procfile: ...
- yenkasaChat src/signaling/server.js: ...
Repository coverage used for this search: 12 repositories, 4,792 files, 18,848 chunks.
```

If no matching file-level evidence is returned:

```text
I searched the indexed repository source, but I did not find a strong file-level match for this exact question.
The snapshots are available: 12 repositories, 4,792 files, 18,848 chunks.
```

## Follow-Up Fix: PostgreSQL Repository Source Search

Issue found after live deployment:

- YIO selected both `RepositoryAgent` and `VectorSearchAgent`.
- `RepositoryAgent` read PostgreSQL repository coverage correctly.
- `VectorSearchAgent` still searched MongoDB `ai_embeddings` for repository chunks, so the active PostgreSQL repository chunks were not searched.
- A first PostgreSQL fallback used an expensive correlated text-scoring query and timed out on Cloud SQL.

Final changes made:

- `app/services/postgres_document_service.py`
  - Added `search_repo_chunks_text(...)` against the active PostgreSQL `ai_documents` store.
  - Uses query terms for Heroku, Procfile, dyno, call server, video call, WebSocket, signaling, RTC, and Agora evidence.
  - Replaced the expensive correlated scoring query with a simpler `LIKE ANY` search and path/content weighting.
- `app/repositories/vector_search_repository.py`
  - Split repository search store from memory search store.
  - Repository source search can now use PostgreSQL.
  - Memory vector search remains on MongoDB.
- `app/agents/vector_search_agent.py`
  - Skips Vertex embeddings for PostgreSQL text-backed repository searches.
  - Still uses embeddings for memory search and MongoDB vector search.
- `app/core/orchestrator.py`
  - Registers `VectorSearchRepository(self.repository_store, memory_store=self.mongodb)` so production uses PostgreSQL for repository chunks.
- `app/orchestrator/reasoning_engine.py`
  - Distinguishes call/video-call server source evidence from Heroku hosting evidence.
  - If call server files are found but no Heroku/Procfile/dyno/app config is found, the answer says so directly.
- `tests/test_phase1.py`
  - Added PostgreSQL repository-source search fallback coverage.
  - Added coverage proving memory search stays on MongoDB.
  - Added coverage for the exact Heroku/call-server distinction.

Final test result:

```text
76 passed, 3 skipped, 1 warning
```

Deployment:

```text
Cloud Run service: yenkasa-code-agent
Revision: yenkasa-code-agent-00015-d8z
Traffic: 100%
URL: https://yenkasa-code-agent-496173204476.europe-west1.run.app
```

Live verification query:

```text
are you aware am hosting my call and video call server on heroku ?check my repo
```

Live verified answer behavior:

```text
I found file-level evidence for the call/video-call server code, but I did not find file-level evidence that it is hosted on Heroku.
The strongest matches point to signaling/call handling, not deployment hosting config.
- YenkasaChatSignaling caller.server.js: ...
- YenkasaChatSignaling datacall.routes.js: ...
Repository coverage used for this search: 12 repositories, 4,792 files, 18,848 chunks.
```
