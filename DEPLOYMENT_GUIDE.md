# YenkasaCode Agent - Cloud Run Deployment Guide

Date: 2026-06-06

## Deployment Target

- Project: `project-10405180-0afd-4ecc-9f8`
- Service: `yenkasa-code-agent`
- Region: `europe-west1`
- Image: `europe-west1-docker.pkg.dev/project-10405180-0afd-4ecc-9f8/yenkasa-code-agent/yenkasa-code-agent:alpha`
- Min instances: `0`
- Max instances: `5`
- Memory: `2Gi`
- CPU: `2`
- Timeout: `300s`

## Current Status

Image build: complete

Cloud Run deployment: blocked

Blocker:

- `MONGODB_URI` secret has no enabled version.
- `GOOGLE_APPLICATION_CREDENTIALS_JSON` secret has no enabled version.

`GOOGLE_APPLICATION_CREDENTIALS_JSON` may be replaced by Cloud Run workload identity if the runtime service account has the required IAM permissions.

## Build Command

```bash
gcloud builds submit \
  --tag europe-west1-docker.pkg.dev/project-10405180-0afd-4ecc-9f8/yenkasa-code-agent/yenkasa-code-agent:alpha \
  --project project-10405180-0afd-4ecc-9f8
```

Build result:

```text
b8681055-dbb6-4b92-8850-1a0bf3847a09 SUCCESS
```

## Deploy Command

Run after required secret versions are added:

```bash
gcloud run deploy yenkasa-code-agent \
  --image europe-west1-docker.pkg.dev/project-10405180-0afd-4ecc-9f8/yenkasa-code-agent/yenkasa-code-agent:alpha \
  --project project-10405180-0afd-4ecc-9f8 \
  --region europe-west1 \
  --platform managed \
  --min-instances 0 \
  --max-instances 5 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --no-allow-unauthenticated \
  --set-env-vars APP_ENV=production,APP_PORT=8080,MONGODB_DATABASE=yenkasa_code,VERTEX_EMBEDDING_MODEL=gemini-embedding-001,GOOGLE_CLOUD_PROJECT=project-10405180-0afd-4ecc-9f8,CLOUD_RUN_SERVICE=yenkasa-code-agent,CLOUD_RUN_LOCATION=europe-west1 \
  --set-secrets ADMIN_API_KEY=YENKASA_CODE_API_KEY:latest,DEVELOPER_API_KEY=YENKASA_CODE_API_KEY:latest,VIEWER_API_KEY=YENKASA_CODE_API_KEY:latest,HEALTHCHECK_API_KEY=YENKASA_CODE_API_KEY:latest,MONGODB_URI=MONGODB_URI:latest,VERTEX_PROJECT_ID=VERTEX_PROJECT_ID:latest,VERTEX_LOCATION=VERTEX_LOCATION:latest
```

## Health and Readiness

The container healthcheck calls:

```text
GET /health
```

with:

```text
X-API-Key: $HEALTHCHECK_API_KEY
```

Application readiness endpoint:

```text
GET /ready
```

Readiness checks:

- MongoDB.
- Vertex AI.
- Cloud Run.
- Cloud Logging.

## Internal Alpha Access

The service should remain private for internal alpha:

```text
--no-allow-unauthenticated
```

Callers need Cloud Run IAM invocation permission plus the app-level `X-API-Key`.
