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

Cloud Run deployment: complete

Service URL:

```text
https://yenkasa-code-agent-3vx2nvls4a-ew.a.run.app
```

Latest ready revision:

```text
yenkasa-code-agent-00003-kk9
```

`GOOGLE_APPLICATION_CREDENTIALS_JSON` was not used. The deployment uses Cloud Run workload identity through the runtime service account.

## Build Command

```bash
gcloud builds submit \
  --tag europe-west1-docker.pkg.dev/project-10405180-0afd-4ecc-9f8/yenkasa-code-agent/yenkasa-code-agent:alpha \
  --project project-10405180-0afd-4ecc-9f8
```

Final build result:

```text
14109790-8087-458d-8ede-6c21285b0d63 SUCCESS
```

## Deploy Command

Command used:

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
  --set-env-vars APP_ENV=production,APP_PORT=8080,MONGODB_DATABASE=yenkasa_ai_db,MONGODB_APP_DATABASE=yenkasaChat,BALESHOP_DATABASE_NAME=yenkasa_store,BALESHOP_DATABASE_LABEL=yenkasa_store,VERTEX_EMBEDDING_MODEL=gemini-embedding-001,GOOGLE_CLOUD_PROJECT=project-10405180-0afd-4ecc-9f8,CLOUD_RUN_SERVICE=yenkasa-code-agent,CLOUD_RUN_LOCATION=europe-west1 \
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
