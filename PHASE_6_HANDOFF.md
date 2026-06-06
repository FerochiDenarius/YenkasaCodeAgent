# YenkasaCode Agent - Phase 6 Handoff

## Supported Refactor Capabilities

Phase 6 implements only `RefactorAgent`.

`RefactorAgent` is planning-only. It never modifies files, commits code, or generates automatic migrations. It produces:

- recommendations
- migration plans
- patch proposals
- technical debt reports

It uses `RefactorService`, which leverages existing `CodeAuditAgent` findings, `RepositoryAgent` statistics, and `VectorSearchAgent` retrieval results.

## Recommendation Categories

- Technical Debt
- Service Extraction
- Duplication
- Dependency
- Architecture

## Risk Scoring Model

Priority levels:

- `CRITICAL`
- `HIGH`
- `MEDIUM`
- `LOW`

Risk levels:

- `HIGH`
- `MEDIUM`
- `LOW`

Current mapping:

- `CRITICAL` priority maps to `HIGH` risk.
- `HIGH` and `MEDIUM` priority map to `MEDIUM` risk.
- `LOW` priority maps to `LOW` risk.

Service extraction and dependency recommendations default to `MEDIUM` risk because they commonly touch boundaries and tests. Duplication consolidation defaults to `LOW` risk when call-site behavior can be verified before implementation.

## Limitations

- Recommendations are heuristic and depend on audit findings, repository inventory, and semantic retrieval quality.
- No source code is modified.
- No migrations are generated.
- Dependency analysis does not yet build a full import graph.
- Duplication analysis uses semantic indicators rather than deterministic clone detection.

## Recommendations for Phase 7

- Add a dry-run proposal format that references exact files and validation steps.
- Add deterministic dependency graph analysis.
- Add clone-detection tooling for duplicate code blocks.
- Keep deployment and runtime operations separate from refactor planning.
