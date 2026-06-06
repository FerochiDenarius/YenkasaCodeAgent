# YenkasaCode Agent - Production Readiness Report

Audit date: 2026-06-06

Scope: FastAPI backend, agents, YIO orchestration, MongoDB access, Vertex AI integration, Cloud Run and observability integrations, Docker configuration, dependency posture, and test coverage.

Overall status: **Not ready for production deployment**

Deployment readiness score: **42 / 100**

## 1. Security Findings

- **CRITICAL: Agent APIs are unauthenticated.** `GET /api/agent/agents`, `GET /api/agent/metrics`, and `POST /api/agent/query` are exposed without authentication or authorization checks in `app/routers/agent.py:49`, `app/routers/agent.py:54`, and `app/routers/agent.py:59`. This allows any caller to trigger database, vector search, audit, Cloud Run, log, and product-generation workflows.

- **CRITICAL: No authorization model exists for sensitive agents.** Operational agents can query deployment status and logs, and data agents can read indexed repository and memory content. There are no role checks separating read-only database access, Cloud Run visibility, observability logs, or generated-code access.

- **HIGH: Internal errors are returned to clients through agent responses.** `BaseAgent.execute` returns `error=str(exc)` in `app/agents/base.py:22`, which can expose configuration names, dependency errors, database errors, Google Cloud errors, and stack-adjacent details.

- **HIGH: Metrics and agent inventory are public.** The metrics endpoint exposes request counts, agent names, and operational capabilities without access control at `app/routers/agent.py:54`.

- **HIGH: Log and repository evidence may leak secrets or PII.** YIO synthesis returns raw agent evidence in `app/orchestrator/response_synthesizer.py`, including vector snippets and log messages. Observability returns log payloads directly in `app/services/observability_service.py:80`.

- **MEDIUM: Logging filter construction uses raw user query text.** `ObservabilityService._recent_entries` injects the user query into a Google Logging filter string at `app/services/observability_service.py:77`. This risks malformed filters and query manipulation.

- **MEDIUM: No request size, query length, or context size limits.** `AgentQueryRequest` only requires `query` length >= 1. There are no maximum payload limits, maximum context size, or per-agent input bounds.

- **MEDIUM: ProductBuilderAgent returns generated code without safety validation.** It is generate-only and does not write files, but generated code is returned directly to callers from `app/services/product_builder_service.py`.

## 2. Architecture Findings

- **YIO is useful but deterministic and keyword-driven.** Intent classification is a static keyword map in `app/orchestrator/intent_classifier.py:5`. Ambiguous or adversarial wording can select the wrong agent or too many agents.

- **The old direct routing path remains alongside YIO.** Explicit `agent` requests bypass YIO in `app/core/orchestrator.py`, which is useful operationally but means governance and policy enforcement must be implemented in both paths.

- **Agent dependencies are manually constructed in one large orchestrator.** `YenkasaCodeOrchestrator._register_foundation_agents` wires all agents and services in `app/core/orchestrator.py`. This is workable now but will become hard to test and reason about as dependencies grow.

- **Standard agent contract is only normalized at YIO.** Individual agents still return different result shapes, while YIO normalizes in `app/orchestrator/response_synthesizer.py`. API consumers using explicit agents will see inconsistent schemas.

- **Cloud Run location is coupled to Vertex location.** `CloudRunService._service_name` uses `settings.vertex_location` for Cloud Run location in `app/services/cloudrun_service.py:26`. Cloud Run should have its own `CLOUD_RUN_LOCATION`.

## 3. Scalability Findings

- **MongoDB operations can be unbounded.** `MongoDBService.aggregate` calls `to_list(length=None)` in `app/services/mongodb_service.py:51`, which can load all aggregation results into memory.

- **No MongoDB client tuning is configured.** `AsyncIOMotorClient` is created without explicit server selection timeout, socket timeout, max pool size, retry policy, or TLS expectations in `app/services/mongodb_service.py:21`.

- **No per-request timeout or cancellation policy exists.** YIO executes agents with `asyncio.gather` in `app/orchestrator/yio.py:48`, but there are no timeouts around MongoDB, Vertex, Cloud Run, logging, or generated workflows.

- **Vertex embedding call is synchronous inside an async method.** `EmbeddingService.embed_query` calls the Google GenAI client directly inside `async def` at `app/services/embedding_service.py:26`, which can block the event loop.

- **Vector search limits are caller-influenced.** Vector search uses `limit` from context upstream and computes `numCandidates=max(limit * 10, 50)` in `app/repositories/vector_search_repository.py`. There is no maximum cap.

## 4. Reliability Findings

- **Health check is shallow.** `/health` returns `status="ok"` and registered agent count only in `app/routers/health.py`. It does not verify MongoDB, Vertex credentials, Cloud Run clients, Google Logging, vector indexes, or required environment variables.

- **Startup does not validate critical configuration.** Services are lazily initialized, so missing `MONGODB_URI`, `VERTEX_PROJECT_ID`, `CLOUD_RUN_SERVICE`, or credentials fail at request time rather than deployment time.

- **Google Application Credentials setting is not applied.** `google_application_credentials` is read into settings in `app/config/settings.py:20`, but the code does not set `GOOGLE_APPLICATION_CREDENTIALS` for Google SDK clients. It works only if the real process environment is already set.

- **Cloud Run deployment history is not real history.** `deployment_history` synthesizes two entries from current service metadata in `app/services/cloudrun_service.py:49`; it does not fetch revision lists or deployment events.

- **Incident detection is heuristic.** Observability marks incidents as `len(errors) >= 5` in `app/services/observability_service.py:31`, without service-specific thresholds, time-series baselines, or alert policy integration.

- **No graceful close for Google clients.** MongoDB is closed during lifespan shutdown in `app/main.py:43`, but Cloud Run and logging clients are not explicitly closed.

## 5. Missing Production Features

- Authentication and authorization for all API routes.
- Per-agent RBAC or scoped API keys.
- Rate limiting and abuse protection.
- Request body size limits and query/context validation.
- Secrets manager integration and startup validation.
- Redaction of secrets, tokens, PII, log payloads, and code snippets.
- Deep health and readiness endpoints.
- External dependency timeouts, retries, circuit breakers, and backoff.
- Structured production logging with severity, trace IDs, and redaction.
- OpenTelemetry tracing and metrics export.
- Dependency lockfile or pinned versions.
- Container hardening: non-root user, healthcheck, image digest pinning, vulnerability scanning, and SBOM.
- Integration tests against staging MongoDB Atlas, Vertex AI, Cloud Run, and Cloud Logging.
- CI gates for tests, linting, formatting, type checking, dependency audit, and container scan.
- Production runbook and incident response documentation.

## 6. Critical Issues

1. **Unauthenticated public agent execution.**
   - Evidence: `app/routers/agent.py:49`, `app/routers/agent.py:54`, `app/routers/agent.py:59`.
   - Impact: Unauthorized callers can query operational logs, deployment status, repository snippets, memory embeddings, and generated code proposals.

2. **No authorization boundaries for sensitive capabilities.**
   - Evidence: All agents are registered into the same public query surface in `app/core/orchestrator.py`.
   - Impact: A single endpoint can reach database, observability, Cloud Run, audit, refactor, and product generation flows.

3. **No production readiness validation for required external services.**
   - Evidence: lazy initialization in `app/main.py:31` through `app/main.py:34`; shallow health check in `app/routers/health.py`.
   - Impact: Deployments can appear healthy while MongoDB, Vertex, Cloud Run, or Logging are misconfigured.

## 7. High Priority Issues

1. **Unbounded MongoDB aggregation memory usage.**
   - Evidence: `to_list(length=None)` in `app/services/mongodb_service.py:51`.

2. **No request limits or rate limits.**
   - Evidence: `AgentQueryRequest` has only minimum query length validation.

3. **Raw exception messages returned by agents.**
   - Evidence: `BaseAgent.execute` returns `str(exc)`.

4. **Raw logs and vector snippets returned in synthesized evidence.**
   - Evidence: `ObservabilityService._recent_entries` and `ResponseSynthesizer`.

5. **Unpinned dependencies.**
   - Evidence: `requirements.txt` uses lower bounds only, e.g. `fastapi>=0.115.0`.

6. **Docker container runs as root and has no healthcheck.**
   - Evidence: `Dockerfile` has no `USER`, no `HEALTHCHECK`, and installs dependencies directly into the runtime image.

7. **Google Cloud configuration is incomplete.**
   - Evidence: no dedicated Cloud Run location, no explicit credential handling, no startup validation.

## 8. Recommended Fixes

Immediate blockers:

1. Add authentication to all `/api/agent/*` routes.
2. Add authorization/RBAC by agent capability.
3. Add request size, query length, context schema, and per-agent limit validation.
4. Add rate limiting and concurrency limits.
5. Replace raw agent errors with sanitized public errors and internal structured logs.
6. Add startup config validation for required production environment variables.
7. Add `/ready` endpoint that checks MongoDB ping, configured Google Cloud project, Cloud Run service name, and optional Vertex model availability.

High-priority hardening:

1. Add MongoDB client options: server selection timeout, socket timeout, pool limits, retry settings, and TLS expectations.
2. Cap all query limits, vector search `numCandidates`, log query windows, and aggregation result lengths.
3. Redact secrets and PII from logs, vector snippets, synthesized evidence, and errors.
4. Add explicit Cloud Run location config.
5. Move Google credentials to workload identity or secret manager; do not rely on `.env` for production.
6. Pin dependencies with a lockfile and run dependency audit in CI.
7. Harden Docker: non-root user, healthcheck, multi-stage build where useful, SBOM, image vulnerability scanning.

Testing and operations:

1. Add integration tests against staging MongoDB Atlas, Vertex AI, Cloud Run, and Cloud Logging.
2. Add auth/authorization tests, negative tests, timeout tests, and malformed input tests.
3. Add OpenTelemetry tracing and request-level timing around each agent.
4. Add CI gates for tests, linting, type checking, dependency audit, and container scan.

## 9. Deployment Readiness Score

Score: **42 / 100**

Rationale:

- Core app boots and has a broad mocked test suite.
- Agent layering is generally clean, and most database access flows through repositories/services.
- `pip-audit -r requirements.txt --timeout 120` reported: **No known vulnerabilities found**.
- However, production deployment is blocked by missing authentication, missing authorization, shallow health checks, unbounded external calls, weak error redaction, no rate limiting, incomplete Google Cloud readiness, and non-hardened Docker configuration.

Recommendation: **Do not deploy to production until the Critical Issues and the first seven Recommended Fixes are completed.**
