# YenkasaCode Agent - Phase 4 Handoff

## Architecture

Phase 4 implements only `VectorSearchAgent`.

Semantic retrieval uses the existing service and repository boundaries:

```text
VectorSearchAgent
EmbeddingService and VectorSearchRepository
MongoDBService
MongoDB Atlas Vector Search
repo_chunks and memory_embeddings
```

`DatabaseAgent` and `RepositoryAgent` remain unchanged. `VectorSearchAgent` does not access MongoDB directly.

## Vector Search Flow

1. A semantic search query routes to `VectorSearchAgent`.
2. `EmbeddingService` generates a query embedding with Vertex AI Gemini Embeddings.
3. `VectorSearchRepository` runs a MongoDB Atlas `$vectorSearch` aggregation against `repo_chunks` or `memory_embeddings`.
4. The agent returns normalized matches containing file path, repository name, similarity score, and snippet.

## Embedding Provider

Provider: Vertex AI Gemini Embeddings

Default model:

```text
gemini-embedding-001
```

## Environment Variables

- `VERTEX_PROJECT_ID`
- `VERTEX_LOCATION`
- `VERTEX_EMBEDDING_MODEL`

`VERTEX_EMBEDDING_MODEL` defaults to `gemini-embedding-001`.

## Supported Queries

- Find login implementation.
- Find notification code.
- Find payment integration.
- Find JWT authentication.
- Find Cloudinary integration.
- Find post approval workflow.
- Find moderation system.
- Find community creation logic.
- Find related memories.
- Find similar memory entries.

## Limitations

- The implementation assumes existing Atlas Vector Search indexes named `repo_chunks_vector_index` and `memory_embeddings_vector_index`.
- The vector field is assumed to be `embedding`.
- Snippets are generated from `content` or `text` fields.
- Memory searches are routed when the query contains `memory` or `memories`.
- No new collections or indexes are created.
