# Live MongoDB Discovery Report

## Collection Inventory

### `yenkasa_ai_db`

Read-only discovery confirmed this is the repository intelligence database.

| Collection | Count | Indexes | Storage |
| --- | ---: | ---: | ---: |
| `ai_chats` | 349 | 3 | 483328 |
| `ai_embeddings` | 5410 | 4 | 54657024 |
| `ai_insights` | 1383 | 3 | 278528 |
| `ai_jobs` | 43 | 3 | 110592 |
| `ai_log_alerts` | 0 | 3 | 4096 |
| `ai_logs` | 0 | 5 | 4096 |
| `ai_memory` | 4375 | 4 | 528384 |
| `ai_metrics` | 293 | 2 | 94208 |
| `ai_sessions` | 48 | 3 | 45056 |
| `ai_usage` | 4578 | 8 | 1245184 |
| `ai_users` | 13 | 4 | 36864 |
| `engagement_metrics` | 168 | 2 | 61440 |
| `github_repositories` | 11 | 4 | 45056 |

The read-only stats pass was interrupted by a MongoDB operation timeout after `github_repositories`, so remaining collection counts are taken from earlier targeted discovery in the same database:

- `moderation_alerts`
- `moderation_logs`
- `repo_architecture` with count `0`
- `yme_graph`
- `yme_memories` with count `338`

### `yenkasaChat`

`yenkasaChat` is now configured as the secondary MongoDB database for DatabaseAgent inventory. It is the application database for the YenkasaChat backend, not the repository intelligence source.

## Actual Repository Storage Model

- Repository metadata: `yenkasa_ai_db.github_repositories`
- Repository file chunks and code embeddings: `yenkasa_ai_db.ai_embeddings`
- Ingestion jobs/status: `yenkasa_ai_db.ai_jobs`
- Architecture summaries: `yenkasa_ai_db.repo_architecture` currently exists but is empty

The old assumed collections do not match the live database:

- `repo_chunks` does not exist in `yenkasa_ai_db`
- `memory_embeddings` does not exist in `yenkasa_ai_db`

## Actual Embedding Storage Model

- Code embeddings: `yenkasa_ai_db.ai_embeddings`
- Memory embeddings: `yenkasa_ai_db.yme_memories`
- Legacy/general memory records: `yenkasa_ai_db.ai_memory`

Observed embedding dimension:

- `ai_embeddings.embedding`: 768 dimensions
- `yme_memories.embedding`: 768 dimensions

## Vector Index Locations

- `yenkasa_ai_db.ai_embeddings`: Atlas Vector Search index `repo_chunks_vector_index`, status previously observed as ready
- `yenkasa_ai_db.yme_memories`: Atlas Vector Search index `yme_memories_vector_index`, status previously observed as ready

## Baleshop / `yenkasa_store` SQL Discovery

Baleshop is not MongoDB. It is a Spring Boot API backed by MySQL.

Confirmed backend/server details:

- Backend path: `/Users/kofibright/Desktop/TriciaBales/baleshop`
- Server app path: `/root/triciabales`
- Spring datasource: `jdbc:mysql://localhost:3306/bale_shop`
- PM2 app name: `tricia-bales-api`
- Runtime cwd from PM2 config: `/root/triciabales`
- YenkasaChat store proxy: `/Users/kofibright/yenkasaChat/yenkasaChatBackend/RegLoginBackend/store/yenkasa-store-server.js`
- Proxy upstream: `TRICIABALES_API_BASE` or fallback `http://134.209.182.39:8080`
- MySQL version: `8.0.46-0ubuntu0.24.04.2`
- MySQL bind address: `127.0.0.1`
- MySQL database: `bale_shop`
- Tables: `app_notifications`, `bale_images`, `bales`, `order_items`, `order_refunds`, `orders`, `user_tokens`, `users`

The YenkasaChat store server does not hold SQL credentials. It forwards HTTP requests to the Baleshop Spring Boot API:

- `/api/users/*`
- `/api/triciabales/*`
- `/api/orders/*`
- `/api/refunds/*`
- `/api/paystack/*`
- `/api/notifications/*`
- `/api/deliveries/uber/*`

Network check:

- `134.209.182.39:3306` refused connections

Conclusion:

- The Baleshop MySQL database is local/private to the DigitalOcean Spring Boot server.
- Cloud Run cannot connect directly to it until a reachable SQL endpoint, tunnel, VPN, or managed database URL is provided.
- A Secret Manager placeholder `BALESHOP_DATABASE_URL` exists, but no usable production SQL URL version is attached yet.

## Recommended Agent Collection Mappings

### DatabaseAgent

- Primary MongoDB database: `yenkasa_ai_db`
- Secondary MongoDB database: `yenkasaChat`
- Repository chunks alias: `repo_chunks` -> `yenkasa_ai_db.ai_embeddings`
- Memory embeddings alias: `memory_embeddings` -> `yenkasa_ai_db.yme_memories`
- Baleshop SQL alias: `yenkasa_store` -> configured by `BALESHOP_DATABASE_URL`

### RepositoryAgent

- Repository metadata: `yenkasa_ai_db.github_repositories`
- Repository intelligence and language/chunk stats: `yenkasa_ai_db.ai_embeddings`

### VectorSearchAgent

- Semantic code search: `yenkasa_ai_db.ai_embeddings` using `repo_chunks_vector_index`
- Memory search: `yenkasa_ai_db.yme_memories` using `yme_memories_vector_index`

## Implemented Fixes

- DatabaseAgent now inventories both configured MongoDB databases: `yenkasa_ai_db` and `yenkasaChat`.
- DatabaseAgent now maps `repo_chunks` operations to live `ai_embeddings`.
- DatabaseAgent now maps `memory_embeddings` operations to live `yme_memories`.
- VectorSearchAgent now searches live `ai_embeddings` and `yme_memories` collections.
- RepositoryAgent now uses `ai_embeddings` for repository intelligence.
- DatabaseAgent now supports a read-only optional MySQL inventory source for Baleshop / `yenkasa_store`.

## Remaining Limitation

Live Baleshop SQL inventory is not available from Cloud Run yet because the MySQL service is not reachable externally and the SQL connection URL has not been added to `BALESHOP_DATABASE_URL`.
