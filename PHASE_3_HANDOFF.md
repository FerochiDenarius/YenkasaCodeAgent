# YenkasaCode Agent - Phase 3 Handoff

## Architecture Summary

Phase 3 implements only `RepositoryAgent`.

Repository intelligence follows the existing read-only database architecture:

```text
RepositoryAgent
RepoChunksRepository and RepositoryIntelligenceRepository
MongoDBService
repo_chunks collection
```

`RepositoryAgent` never accesses MongoDB directly. It uses the Phase 2 `RepoChunksRepository` for chunk-count ranking and `RepositoryIntelligenceRepository` for repository inventory, language analysis, recent activity, and health signals.

## Supported Repository Queries

- Which repositories are indexed?
- List indexed repositories.
- Show repository inventory.
- Which repository has the most chunks?
- Which repository is largest?
- Top repositories by chunk count.
- How many Kotlin files exist?
- How many Python files exist?
- Language breakdown.
- Most recently indexed repository.
- Most recently indexed file.
- Latest repository activity.
- Repositories with missing metadata.
- Repositories with zero chunks.
- Repositories with indexing anomalies.

## Metrics Added

The existing metrics endpoint now includes:

- `repository_queries_total`
- `repository_query_failures`
- `repository_query_duration_ms`

## Known Limitations

- Query routing is keyword-based.
- Language detection prefers an indexed `language` field and falls back to `.kt` and `.py` file extensions.
- Zero-chunk repositories cannot be fully detected from `repo_chunks` alone because absent repositories have no chunk documents.
- Health anomaly detection is intentionally conservative until the live indexed document schema is validated.

## Recommendations for Phase 4

- Validate live `repo_chunks` schema and normalize repository, file path, language, and timestamp fields.
- Add a repository catalog collection if zero-chunk repositories need first-class tracking.
- Introduce richer query parsing before adding code-audit or refactor agents.
- Keep future agents behind explicit repository/service boundaries.
