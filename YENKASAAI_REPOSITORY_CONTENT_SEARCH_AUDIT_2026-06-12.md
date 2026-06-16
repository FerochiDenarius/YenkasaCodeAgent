# YenkasaAI Repository Content Search Audit

Date: 2026-06-12

## Summary

Repository inventory and PostgreSQL repository counts were already working, but `RepositoryAgent` still answered most repository questions from inventory only. File-level questions such as:

- Which file handles Cloudinary uploads in yenkasaChat?
- Search for Agora usage.
- Are you aware I am hosting my call and video call server on Heroku? Check my repo.

could return repository counts instead of searching indexed chunks.

## Root Cause

The PostgreSQL repository store already exposes chunk text search through `search_repo_chunks_text()` against `collection='ai_embeddings'`.

`VectorSearchAgent` could use that search path, but `RepositoryAgent` did not. Its decision tree only handled:

- inventory
- largest repositories
- language breakdown
- latest activity
- repository health

So when YenkasaAI selected `RepositoryAgent`, the agent returned inventory evidence instead of searching file paths or chunk contents.

## Files Changed

- `app/agents/repository_agent.py`
  - Added repository content-search, file-lookup, and code-explanation capabilities.
  - Detects file/content/hosting questions.
  - Calls repository chunk text search before inventory fallback.

- `app/repositories/repo_chunks_repository.py`
  - Added `search_text()`.
  - Uses PostgreSQL `search_repo_chunks_text()` when available.
  - Falls back to Mongo-style text matching over repository, file path, and chunk fields.

- `app/orchestrator/reasoning_engine.py`
  - Converts RepositoryAgent `matches` into natural-language file-level answers.
  - Handles no-match repository content searches without dumping inventory.
  - Expanded ranking terms for Cloudinary, uploads, GCS, Agora, livestream, moderation, Heroku, Procfile, Socket.IO, and signaling.

- `tests/test_phase1.py`
  - Added regression coverage for direct RepositoryAgent content search.
  - Added regression coverage for finalized RepositoryAgent answers through the orchestrator route.

## Database Collection Involved

- PostgreSQL document table backing `ai_documents`
- Logical collection: `ai_embeddings`
- Search fields:
  - `repo_name`
  - `repository`
  - `file_path`
  - `path`
  - `content`
  - `text`
  - `chunk`
  - `snippet`

## Before

Question:

> Are you aware I am hosting my call and video call server on Heroku? Check my repo.

Behavior:

RepositoryAgent returned inventory/count evidence such as repository count, file count, chunk count, and latest indexed repository.

## After

RepositoryAgent now searches indexed repository chunks and returns file-level evidence.

Expected response shape:

```text
I searched the indexed repository content and found 1 file-level match(es).
- yenkasaChat Procfile: web: node server.js
```

If there are no matches:

```text
I searched the indexed repository content, but I did not find a strong file-level match for this question.
```

## Test Results

Targeted tests:

```text
.venv312/bin/python -m pytest tests/test_phase1.py -q
75 passed, 1 warning
```

Full Code Agent tests:

```text
.venv312/bin/python -m pytest -q
78 passed, 3 skipped, 1 warning
```

## What Is Complete

- RepositoryAgent can now search repository chunks for content/file questions.
- RepositoryAgent can use PostgreSQL `ai_embeddings` text search directly.
- RepositoryAgent no longer has to rely on VectorSearchAgent for basic file lookup.
- Final answers are natural-language summaries with source files instead of inventory JSON.
- Regression tests pass.

## What Still Needs Live Verification

- Live production query against the deployed Code Agent service after deployment:
  - `Which file handles Cloudinary uploads in yenkasaChat?`
  - `Search for Agora usage.`
  - `Explain livestreamPermissions.js.`
  - `Are you aware I am hosting my call and video call server on Heroku? Check my repo.`

- Confirm production PostgreSQL search returns the expected real files from `yenkasaChat`, not only test fixtures.

## Recommended Next Step

Deploy the Code Agent service, then run live API checks through YenkasaAI so the integration path proves:

User question -> YenkasaAI -> Code Agent RepositoryAgent -> PostgreSQL ai_embeddings -> file-level answer.
