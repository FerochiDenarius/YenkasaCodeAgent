# YenkasaAI Repository Pipeline Audit

Date: 2026-06-11

## Executive Summary

`RepositoryAgent` returns:

```json
{"repositories": []}
```

because the deployed `yenkasa-code-agent` still reads repository inventory from MongoDB `yenkasa_ai_db.ai_embeddings`, and that collection currently has `0` documents.

The active YenkasaAI backend after the PostgreSQL migration stores repository data in Cloud SQL PostgreSQL table `public.ai_documents`, using Mongo-style logical collection names. PostgreSQL contains the repository data:

- `github_repositories`: 12 records
- `ai_embeddings`: 18,848 repository chunks
- distinct repository files: 4,792
- chunks with embeddings: 18,848

So the data exists, but `RepositoryAgent` is connected to the old MongoDB read path.

## Root Cause

Primary root cause:

`yenkasa-code-agent` was not migrated to read the PostgreSQL document store. Its `RepositoryAgent` is wired to MongoDB repositories only, and both inventory and chunk-count queries aggregate MongoDB collection `ai_embeddings`.

Evidence:

- Deployed `yenkasa-ai-backend` Cloud Run env has `DATABASE_BACKEND=postgres`.
- Deployed `yenkasa-code-agent` Cloud Run env has only `MONGODB_URI`, `MONGODB_DATABASE=yenkasa_ai_db`, and no PostgreSQL configuration.
- Deployed `yenkasa-code-agent` endpoint confirmed:

```json
{"agent":"RepositoryAgent","success":true,"result":{"repositories":[]},"error":null}
```

- Deployed `yenkasa-code-agent` `DatabaseAgent` confirmed MongoDB `ai_embeddings: 0`.
- Cloud SQL PostgreSQL confirmed `ai_documents` contains `collection='ai_embeddings'` with 18,848 records.

Secondary operational gaps:

- `yenkasa-ai-backend` production has `GITHUB_SCAN_ALL_REPOS=true` and `GITHUB_OWNER=FerochiDenarius`, but no `GITHUB_TOKEN`/`GITHUB_FINE_GRAINED_TOKEN` env var is configured in Cloud Run.
- There is no deployed `yenkasa-ai-worker` Cloud Run service.
- `yenkasa-ai-backend` production has `UPSTASH_REDIS_REST_URL`, but no `REDIS_URL`; code explicitly says RQ queueing remains disabled without `REDIS_URL`.
- PostgreSQL jobs show 3 stale `running` jobs from 2026-06-07, including `yenkasaChat`, `YenkasaAi`, and `YenkasaCodeAgent`.

Those operational gaps affect future sync freshness, but they are not the reason for the empty `RepositoryAgent` response. The immediate failure is the read-path mismatch.

## Documentation Evidence From YenkasaAI Backend Docs

I reviewed every Markdown document in `/Users/kofibright/Desktop/yenkasa-ai/backend/docs`:

- `analytics_system.md`
- `architecture.md`
- `auth_architecture.md`
- `code_agent_integration.md`
- `deployment.md`
- `future_memory_roadmap.md`
- `future_sso_plan.md`
- `ingestion_flow.md`
- `jwt_flow.md`
- `live-operational-context-architecture-2026-06-01.md`
- `live-operational-context-implementation-2026-06-01.md`
- `log_intelligence.md`
- `memory_pipeline.md`
- `memory_retrieval.md`
- `memory_scoring.md`
- `repo_chat.md`
- `roadmap.md`
- `tls_network_hardening_report.md`
- `vector_search.md`
- `yenkasaai-oil-stabilization-report-2026-06-01.md`
- `yme_architecture.md`
- `yme_tracking.md`

The PDF `yenkasaai-oil-stabilization-report-2026-06-01.pdf` is present as a 6-page PDF. `pdftotext` is not installed locally, and `strings` showed compressed PDF streams, so I used the same-named Markdown report as the readable source.

Key documentation clues:

1. `architecture.md` states the old design directly: MongoDB Atlas stores repository chunks, and Redis backs RQ ingestion workers.
2. `ingestion_flow.md` says repository ingestion writes a job document to MongoDB, queues it in Redis/RQ, upserts chunks into MongoDB Atlas, and updates job status in MongoDB.
3. `vector_search.md` is explicitly titled `MongoDB Atlas Vector Search` and says repository chunks live in a repo chunk collection with `repo_name`, `file_path`, `content`, and `embedding`.
4. `deployment.md` says to deploy `yenkasa-ai-worker` from `Dockerfile.worker`, and says required dependencies include MongoDB Atlas and a Redis instance reachable from Cloud Run.
5. `code_agent_integration.md` says YenkasaAI routes engineering and repository-intelligence questions to deployed `yenkasa-code-agent`, but it does not say the Code Agent was updated to use PostgreSQL.
6. No backend doc in this folder describes the repository-ingestion migration from MongoDB/Atlas to PostgreSQL `ai_documents`.
7. No backend doc in this folder describes configuring `yenkasa-code-agent` with Cloud SQL/PostgreSQL.
8. No backend doc in this folder describes a PostgreSQL replacement for Atlas vector search; current code confirms PostgreSQL mode skips Mongo `$vectorSearch` and falls back to text search.

This documentation strongly supports the historical sequence: repository scan/search originally worked through MongoDB Atlas; after the PostgreSQL migration, YenkasaAI backend storage moved to PostgreSQL, but the Code Agent retrieval path and docs were not carried forward.

## Pipeline Trace

Expected flow:

1. GitHub repository discovery
2. Clone or GitHub API snapshot extraction
3. Local repository scan
4. File filtering and language detection
5. Chunking
6. Gemini embedding generation
7. Storage
8. Retrieval by repository search/chat or `RepositoryAgent`

Actual production storage flow in YenkasaAI:

1. `GitHubSyncService.sync_all_accessible_repositories()` discovers repositories.
2. `GitHubSyncService.sync_repository_from_payload()` writes metadata to `github_repositories_collection`.
3. It calls `RepoIngestionService.ingest_repository()`.
4. `RepoIngestionService.run_job()` scans files, chunks content, generates embeddings, then calls `vector.replace_file_chunks()`.
5. Because `DATABASE_BACKEND=postgres`, `IntelligenceRuntime` uses `PostgresDocumentService`.
6. `PostgresDocumentService` writes Mongo-style documents into PostgreSQL `public.ai_documents` with logical collections:
   - `ai_embeddings`
   - `github_repositories`
   - `ai_jobs`
   - `ai_metrics`

Actual failing retrieval flow:

1. YenkasaAI routes engineering questions to deployed `yenkasa-code-agent`.
2. `yenkasa-code-agent` `RepositoryAgent` runs successfully.
3. It reads MongoDB `yenkasa_ai_db.ai_embeddings`.
4. MongoDB `ai_embeddings` is empty.
5. It returns `repositories: []`.

## Current Active Database Counts

Active production database:

- Cloud SQL instance: `project-10405180-0afd-4ecc-9f8:europe-west1:yenkasa-ai-postgres`
- PostgreSQL database: `yenkasa_ai`
- Table: `public.ai_documents`
- Total records: 53,728

Required counts:

| Item | Count | Source |
| --- | ---: | --- |
| repositories | 12 | `ai_documents where collection='github_repositories'` |
| repository_files | 4,792 | distinct `repo_name,file_path` in `collection='ai_embeddings'` |
| repository_chunks | 18,848 | `collection='ai_embeddings'` |
| repository_embeddings | 18,848 | `collection='ai_embeddings'` with non-empty `document.embedding` |
| github_sync_records | 12 | `collection='github_repositories'` |

Counts by PostgreSQL logical collection:

| Collection | Count |
| --- | ---: |
| ai_chats | 411 |
| ai_embeddings | 18,848 |
| ai_insights | 9,101 |
| ai_jobs | 135 |
| ai_memory | 5,347 |
| ai_metrics | 342 |
| ai_sessions | 55 |
| ai_usage | 12,885 |
| ai_users | 18 |
| engagement_metrics | 5,466 |
| github_repositories | 12 |
| moderation_alerts | 12 |
| moderation_logs | 157 |
| yme_graph | 462 |
| yme_memories | 477 |

Repository chunk distribution in PostgreSQL:

| Repository | Chunks | Files |
| --- | ---: | ---: |
| YenkasaCodeAgent | 13,438 | 2,804 |
| yenkasaChat | 4,123 | 1,458 |
| YenkasaAi | 856 | 335 |
| yenkasaCommunity | 213 | 101 |
| triciabales | 147 | 64 |
| 3girlsVehicleRentals | 36 | 12 |
| YenkasaChatSignaling | 23 | 6 |
| krabehwe-receipt | 8 | 8 |
| yenkasa | 1 | 1 |
| student-results | 1 | 1 |
| PersonBMI | 1 | 1 |
| PayrollSheet | 1 | 1 |

MongoDB counts from `yenkasa-code-agent` read path:

| MongoDB collection | Count |
| --- | ---: |
| `yenkasa_ai_db.ai_embeddings` | 0 |
| `yenkasa_ai_db.github_repositories` | 12 |
| `yenkasa_ai_db.ai_jobs` | 135 |
| `yenkasa_ai_db.yme_memories` | 401 |

## Job and Sync State

PostgreSQL `ai_jobs`:

- total jobs: 135
- queued/running: 3
- failed: 0

Stale running jobs:

| Repo | Status | Files total | Files processed | Chunks indexed | Updated |
| --- | --- | ---: | ---: | ---: | --- |
| YenkasaCodeAgent | running | 3,079 | 2,735 | 13,265 | 2026-06-08T00:05:01.693000 |
| yenkasaChat | running | 1,458 | 109 | 0 | 2026-06-07T18:17:28.373000 |
| YenkasaAi | running | 335 | 181 | 0 | 2026-06-07T17:58:58.484000 |

Repository metadata status:

- completed/completed: 9
- running/running: 3

The stale status appears inconsistent with actual chunk counts, because PostgreSQL has chunks for `yenkasaChat`, `YenkasaAi`, and `YenkasaCodeAgent`. This should be cleaned up separately, but it does not block retrieval if the correct PostgreSQL source is used.

## Environment Findings

YenkasaAI backend production:

- `DATABASE_BACKEND=postgres`
- Cloud SQL instance attached: `project-10405180-0afd-4ecc-9f8:europe-west1:yenkasa-ai-postgres`
- `POSTGRES_USER=yenkasa_ai`
- `POSTGRES_DATABASE=yenkasa_ai`
- `POSTGRES_HOST=/cloudsql/project-10405180-0afd-4ecc-9f8:europe-west1:yenkasa-ai-postgres`
- `MONGODB_CHUNKS_COLLECTION=ai_embeddings`
- `MONGODB_JOBS_COLLECTION=ai_jobs`
- `GITHUB_OWNER=FerochiDenarius`
- `GITHUB_SCAN_ALL_REPOS=true`
- `UPSTASH_REDIS_REST_URL` is set
- `REDIS_URL` is not set
- no `GITHUB_TOKEN`, `GITHUB_FINE_GRAINED_TOKEN`, `GITHUB_ACCESS_TOKEN`, `GITHUB_PAT`, or `GITHUB_API_KEY` was present in the Cloud Run service env

YenkasaCode Agent production:

- `MONGODB_URI` is configured
- `MONGODB_DATABASE=yenkasa_ai_db`
- `MONGODB_APP_DATABASE=yenkasaChat`
- no PostgreSQL configuration
- no GitHub token configuration
- `YENKASA_AI_BASE_URL=https://yenkasa-ai-backend-496173204476.europe-west1.run.app`

Local backend `.env`:

- still defaults to `database_backend=mongo`
- has `GITHUB_TOKEN` configured
- no `GITHUB_FINE_GRAINED_TOKEN`
- no PostgreSQL settings

## Logs Checked

YenkasaAI backend logs:

- PostgreSQL startup is successful: `PostgreSQL document store ready database=yenkasa_ai`.
- Vertex embedding calls are succeeding with HTTP 200.
- No recent GitHub sync activity was visible after the PostgreSQL deployment, consistent with missing production GitHub token.
- No deployed `yenkasa-ai-worker` service exists.
- There are PostgreSQL pool/connection errors around 2026-06-08, mostly event/YME/conversation writes. These are real operational issues but not the root cause for empty `RepositoryAgent`.

YenkasaCode Agent logs:

- `RepositoryAgent` executes successfully.
- `DatabaseAgent` executes successfully.
- A `VectorSearchAgent` error on 2026-06-08 reported embedding dimension mismatch: index 768 vs query 3072. This is separate from repository inventory returning empty.
- Older FastAPI serialization errors involving `bson.timestamp.Timestamp` appeared around 2026-06-08.

## Affected Files

YenkasaCode Agent:

- `/Users/kofibright/Desktop/yenkasa-code-agent/app/agents/repository_agent.py`
  - `RepositoryAgent.run()` returns inventory from `RepositoryIntelligenceRepository.inventory()`.
- `/Users/kofibright/Desktop/yenkasa-code-agent/app/repositories/repository_intelligence_repository.py`
  - hardcoded `collection_name = "ai_embeddings"`.
  - uses `MongoDBService.aggregate()`.
- `/Users/kofibright/Desktop/yenkasa-code-agent/app/repositories/repo_chunks_repository.py`
  - hardcoded `collection_name = "ai_embeddings"`.
  - uses MongoDB aggregate/count/stat calls.
- `/Users/kofibright/Desktop/yenkasa-code-agent/app/repositories/vector_search_repository.py`
  - hardcoded MongoDB vector search collection/index.
- `/Users/kofibright/Desktop/yenkasa-code-agent/app/core/orchestrator.py`
  - registers `RepositoryAgent`, `DatabaseAgent`, and `VectorSearchAgent` only when `self.mongodb` is available.
- `/Users/kofibright/Desktop/yenkasa-code-agent/app/config/settings.py`
  - has MongoDB settings but no PostgreSQL document-store settings.

YenkasaAI backend:

- `/Users/kofibright/Desktop/yenkasa-ai/backend/app/core/runtime.py`
  - selects `PostgresDocumentService` when `settings.database_backend == "postgres"`.
  - starts GitHub bootstrap only when `github_scan_all_repos` and `github_token` are both set.
- `/Users/kofibright/Desktop/yenkasa-ai/backend/app/services/postgres.py`
  - implements PostgreSQL document store over `public.ai_documents`.
  - maps repository logical collections using the MongoDB collection setting names.
- `/Users/kofibright/Desktop/yenkasa-ai/backend/app/modules/github/service.py`
  - writes `github_repositories` metadata and runs repo ingestion.
- `/Users/kofibright/Desktop/yenkasa-ai/backend/app/modules/repo_ingestion/service.py`
  - chunks files and writes embedded chunks via `vector.replace_file_chunks()`.
- `/Users/kofibright/Desktop/yenkasa-ai/backend/app/modules/vector_search/service.py`
  - skips MongoDB `$vectorSearch` when using PostgreSQL document store and falls back to text search.
- `/Users/kofibright/Desktop/yenkasa-ai/backend/app/services/queue.py`
  - RQ queues require `REDIS_URL`; Upstash REST does not enable repo ingestion queues.

## Recommended Fix Plan

1. Decide the ownership boundary:
   - preferred: make `yenkasa-code-agent` read repository inventory/search from YenkasaAI PostgreSQL, because PostgreSQL is now the active source of truth.
   - alternative: remove `RepositoryAgent` retrieval from Code Agent and have YenkasaAI answer repo inventory/search directly from its native `RepoSearchService`/Postgres store.

2. Add PostgreSQL repository adapters to `yenkasa-code-agent`:
   - `PostgresDocumentService` or a lean read-only equivalent.
   - repository inventory query over `public.ai_documents where collection='ai_embeddings'`.
   - top repositories by chunk count.
   - latest activity.
   - language breakdown.
   - optional text search over `document->>'content'` and `document->>'file_path'`.

3. Configure deployed `yenkasa-code-agent` with PostgreSQL env:
   - `DATABASE_BACKEND=postgres`
   - Cloud SQL instance attachment
   - `POSTGRES_USER`
   - `POSTGRES_DATABASE`
   - `POSTGRES_HOST`
   - `POSTGRES_PASSWORD` from Secret Manager
   - keep MongoDB only for legacy app database inspection if still needed.

4. Update `RepositoryAgent` wiring:
   - choose repository implementation based on configured backend.
   - do not hardcode MongoDB `ai_embeddings` as the only source.
   - add an explicit health result when configured source has zero chunks but another known source has chunks.

5. Fix production sync configuration separately:
   - add a GitHub fine-grained token secret to `yenkasa-ai-backend` using `GITHUB_FINE_GRAINED_TOKEN` or `GITHUB_TOKEN`.
   - set `REDIS_URL` and deploy `yenkasa-ai-worker`, or remove RQ-dependent endpoints and run sync through controlled Cloud Run jobs.
   - clear or reconcile stale `running` jobs after validating no ingestion worker is active.

6. Add regression checks:
   - Code Agent `RepositoryAgent` inventory should return at least `yenkasaChat`, `YenkasaAi`, and `yenkasaCommunity`.
   - Count check should assert PostgreSQL `ai_embeddings > 0`.
   - End-to-end query: `Can you see my repo yenkasaChat?` should return non-empty repository evidence.

## Final Diagnosis

Repository data was successfully migrated into PostgreSQL. `RepositoryAgent` did not follow that migration. It still reads MongoDB `ai_embeddings`, which is empty, so it returns an empty repository list even though PostgreSQL has 18,848 repository chunks and 12 repository metadata records.

## Fix Implemented Locally

Date: 2026-06-11

The Code Agent repository pipeline has now been updated so `RepositoryAgent` can read YenkasaAI repository intelligence from PostgreSQL instead of MongoDB when `DATABASE_BACKEND=postgres`.

Implemented changes:

- Added PostgreSQL repository configuration to `/Users/kofibright/Desktop/yenkasa-code-agent/app/config/settings.py`:
  - `DATABASE_BACKEND`
  - `POSTGRES_DSN`
  - `POSTGRES_HOST`
  - `POSTGRES_PORT`
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `POSTGRES_DATABASE`
  - `POSTGRES_CLOUD_SQL_CONNECTION_NAME`
  - `POSTGRES_DOCUMENT_TABLE`
  - `POSTGRES_AI_EMBEDDINGS_COLLECTION`
- Added `/Users/kofibright/Desktop/yenkasa-code-agent/app/services/postgres_document_service.py`
  - read-only PostgreSQL adapter for `public.ai_documents`.
  - implements repository inventory, top repositories by chunk count, latest indexed file, language breakdown, language file counts, repository health metadata checks, count, stats, and readiness.
  - supports Cloud SQL Unix socket path through `POSTGRES_CLOUD_SQL_CONNECTION_NAME`.
- Updated `/Users/kofibright/Desktop/yenkasa-code-agent/app/repositories/repo_chunks_repository.py`
  - keeps MongoDB behavior when given MongoDB.
  - delegates to native PostgreSQL methods when the store supports them.
- Updated `/Users/kofibright/Desktop/yenkasa-code-agent/app/repositories/repository_intelligence_repository.py`
  - keeps MongoDB aggregation behavior.
  - delegates inventory/language/latest/health operations to PostgreSQL when configured.
- Updated `/Users/kofibright/Desktop/yenkasa-code-agent/app/core/orchestrator.py`
  - accepts a separate `repository_store`.
  - wires `RepositoryAgent` to the PostgreSQL repository store when provided.
  - leaves MongoDB available for legacy database and memory inspection agents.
- Updated `/Users/kofibright/Desktop/yenkasa-code-agent/app/main.py`
  - creates `PostgresDocumentService` when `DATABASE_BACKEND=postgres`.
  - passes it into `YenkasaCodeOrchestrator`.
  - closes it cleanly on shutdown.
- Updated `/Users/kofibright/Desktop/yenkasa-code-agent/app/routers/health.py`
  - adds `repository_postgres` readiness when repository storage is PostgreSQL.
- Updated `/Users/kofibright/Desktop/yenkasa-code-agent/requirements.txt`
  - added `asyncpg==0.31.0`.
- Added regression tests in `/Users/kofibright/Desktop/yenkasa-code-agent/tests/test_phase1.py`
  - verifies `Can you see my repo yenkasaChat?` returns PostgreSQL-backed repository inventory.
  - verifies orchestrator routes `RepositoryAgent` through the PostgreSQL repository store.

Verification:

- Ran `.venv312/bin/python -m pytest tests/test_phase1.py`
- Result: `65 passed, 1 warning in 56.32s`

Deployment still required:

- Deploy updated `yenkasa-code-agent`.
- Configure Cloud Run with:
  - `DATABASE_BACKEND=postgres`
  - `POSTGRES_DATABASE=yenkasa_ai`
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD` from Secret Manager
  - either `POSTGRES_DSN` or Cloud SQL socket settings
  - `POSTGRES_CLOUD_SQL_CONNECTION_NAME=project-10405180-0afd-4ecc-9f8:europe-west1:yenkasa-ai-postgres`
  - Cloud SQL instance attachment for `project-10405180-0afd-4ecc-9f8:europe-west1:yenkasa-ai-postgres`

After deployment, `RepositoryAgent` should stop returning:

```json
{
  "repositories": []
}
```

and should read the active PostgreSQL `ai_documents` repository data for repositories including `yenkasaChat`, `YenkasaAI`, and `yenkasaCommunity`.
