# YenkasaCode Agent - Integration Test Report

Date: 2026-06-06

## Status

Live integration tests passed.

## Local Test Baseline

Command:

```bash
.venv312/bin/python -m pytest -q
```

Result:

```text
54 passed, 3 skipped, 1 warning
```

The skipped tests are live external tests.

## Required Live Test Command

Run after secrets are configured:

```bash
RUN_INTEGRATION_TESTS=1 .venv312/bin/python -m pytest -q tests/test_integration_external.py
```

Result:

```text
3 passed
```

## Live Systems To Validate

- MongoDB Atlas.
- MongoDB Atlas Vector Search.
- Vertex AI Gemini embeddings.
- Cloud Run APIs through deployed `/ready`.
- Cloud Logging through deployed `/ready`.

## Expected Pass Criteria

- MongoDB ping succeeded.
- Vector search query returned a list response from Atlas.
- Vertex AI returned a non-empty embedding vector.
- Cloud Run status API is accessible through `/ready`.
- Cloud Logging API is accessible through `/ready`.
