# YenkasaCode Agent - Cloud Storage Setup

Date: 2026-06-06

## Bucket

```text
gs://yenkasa-code-agent-artifacts
```

## Purpose

The bucket is reserved for:

- Generated project artifacts.
- Audit exports.
- Architecture reports.
- Generated documentation.

## Configuration

Verified configuration:

- Location: `EUROPE-WEST1`
- Storage class: `STANDARD`
- Uniform bucket-level access: enabled
- Versioning: enabled
- Soft delete policy: enabled by default

## Commands Used

```bash
gcloud storage buckets create gs://yenkasa-code-agent-artifacts \
  --project project-10405180-0afd-4ecc-9f8 \
  --location=europe-west1 \
  --uniform-bucket-level-access

gcloud storage buckets update gs://yenkasa-code-agent-artifacts \
  --versioning
```

## Access Recommendation

Grant write access only to the Cloud Run runtime service account and operational maintainers.

Suggested minimum role for app writes:

```text
roles/storage.objectUser
```
