# YenkasaCode Agent - Secret Manager Setup

Date: 2026-06-06

## Project

```text
project-10405180-0afd-4ecc-9f8
```

## API Status

Secret Manager API was enabled successfully.

## Secrets Created

The following Secret Manager resources were created:

- `YENKASA_CODE_API_KEY`
- `MONGODB_URI`
- `VERTEX_PROJECT_ID`
- `VERTEX_LOCATION`
- `GOOGLE_APPLICATION_CREDENTIALS_JSON`

## Secret Versions

Configured:

- `YENKASA_CODE_API_KEY`: version `1`, enabled
- `VERTEX_PROJECT_ID`: version `1`, enabled
- `VERTEX_LOCATION`: version `1`, enabled

Missing payloads:

- `MONGODB_URI`: no enabled versions
- `GOOGLE_APPLICATION_CREDENTIALS_JSON`: no enabled versions

## Add Missing Secret Versions

Add MongoDB Atlas URI:

```bash
printf '%s' '<mongodb-atlas-uri>' | gcloud secrets versions add MONGODB_URI \
  --data-file=- \
  --project project-10405180-0afd-4ecc-9f8
```

Add Google credentials JSON only if not using Cloud Run workload identity:

```bash
gcloud secrets versions add GOOGLE_APPLICATION_CREDENTIALS_JSON \
  --data-file=/secure/path/service-account.json \
  --project project-10405180-0afd-4ecc-9f8
```

Preferred production approach:

- Use the Cloud Run runtime service account and Google Application Default Credentials.
- Grant least-privilege IAM roles to the runtime service account.
- Avoid mounting long-lived Google service account JSON unless required.

## Recommended Runtime Secret Mapping

For internal alpha, the single generated API key can be mapped to all app roles:

```text
ADMIN_API_KEY=YENKASA_CODE_API_KEY:latest
DEVELOPER_API_KEY=YENKASA_CODE_API_KEY:latest
VIEWER_API_KEY=YENKASA_CODE_API_KEY:latest
HEALTHCHECK_API_KEY=YENKASA_CODE_API_KEY:latest
MONGODB_URI=MONGODB_URI:latest
VERTEX_PROJECT_ID=VERTEX_PROJECT_ID:latest
VERTEX_LOCATION=VERTEX_LOCATION:latest
```

For production, use separate admin, developer, viewer, and healthcheck keys.

## IAM Requirements

The Cloud Run runtime service account needs:

- `roles/secretmanager.secretAccessor` for the required secrets.
- `roles/aiplatform.user` for Vertex AI embeddings.
- `roles/run.viewer` for Cloud Run deployment intelligence.
- `roles/logging.viewer` for Cloud Logging observability.

MongoDB Atlas access must be restricted by credentials and network rules appropriate for Cloud Run.
