# YenkasaCode Agent - Phase 2 Handoff

## Architecture Summary

Phase 2 implements only `DatabaseAgent`.

Database access follows the required read-only layering:

```text
DatabaseAgent
Repositories
MongoDBService
MongoDB Atlas
```

`DatabaseAgent` does not access MongoDB directly. It calls `RepoChunksRepository` and `MemoryEmbeddingsRepository`; those repositories call `MongoDBService`, which owns the lazy shared Mongo client.

## Implemented Endpoints

No new HTTP endpoints were added. Phase 2 extends existing endpoints:

```http
POST /api/agent/query
GET /api/agent/agents
GET /api/agent/metrics
```

`DatabaseAgent` is registered in the existing orchestrator and can be selected explicitly with:

```json
{"agent": "DatabaseAgent", "query": "How many repo chunks exist?"}
```

It is also selected by intent routing when matching database-related keywords.

## Supported Queries

- How many repo chunks exist?
- How many memory embeddings exist?
- What is the storage size of repo_chunks?
- What is the storage size of memory_embeddings?
- What is the latest indexed file?
- What is the latest embedding timestamp?
- What are the top repositories by chunk count?

## Environment Variables

- `MONGODB_URI`
- `MONGODB_DATABASE`

The MongoDB connection is initialized lazily on the first database operation. A single Mongo client instance is reused and closed during FastAPI shutdown.

## Metrics

The existing metrics endpoint now includes:

- `database_queries_total`
- `database_query_failures`
- `database_query_duration_ms`

## Known Limitations

- Operations are read-only and intentionally limited to counts, collection stats, latest records, and aggregation.
- `collStats` requires MongoDB privileges that may not be available to every Atlas database user.
- Latest-file and latest-embedding lookups assume timestamp fields such as `indexed_at` and `created_at` exist.
- Query understanding is keyword-based, not LLM-based.

## Next Phase Recommendations

- Add schema-aware field fallbacks after validating the live Atlas document shapes.
- Add per-query result normalization for storage metrics.
- Add stricter allowlisting if future agents accept arbitrary aggregation pipelines.
- Implement the next production agent only after DatabaseAgent has live Atlas validation.
