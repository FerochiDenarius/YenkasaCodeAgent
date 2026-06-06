# YenkasaCode Agent - Integration Test Report

Date: 2026-06-06

## Status

Live integration tests were not run.

Reason:

- `MONGODB_URI` is not available locally.
- `MONGODB_URI` Secret Manager resource has no enabled version.
- `GOOGLE_APPLICATION_CREDENTIALS_JSON` Secret Manager resource has no enabled version.
- Cloud Run service is not deployed yet.

## Local Test Baseline

Command:

```bash
.venv312/bin/python -m pytest -q
```

Result:

```text
52 passed, 3 skipped, 1 warning
```

The skipped tests are live external tests.

## Required Live Test Command

Run after secrets are configured:

```bash
RUN_INTEGRATION_TESTS=1 .venv312/bin/python -m pytest -q tests/test_integration_external.py
```

## Live Systems To Validate

- MongoDB Atlas.
- MongoDB Atlas Vector Search.
- Vertex AI Gemini embeddings.
- Cloud Run APIs.
- Cloud Logging.

## Expected Pass Criteria

- MongoDB ping succeeds.
- Vector search query returns a list response from Atlas.
- Vertex AI returns a non-empty embedding vector.
- Cloud Run status API is accessible.
- Cloud Logging API is accessible.
