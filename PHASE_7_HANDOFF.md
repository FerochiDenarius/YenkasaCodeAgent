# YenkasaCode Agent - Phase 7 Handoff

## Supported Deployment Capabilities

Phase 7 implements only:

- `CloudRunAgent`
- `ObservabilityAgent`

`CloudRunAgent` supports:

- service status
- revision status
- traffic allocation
- deployment history
- deployment health

Supported questions include:

- Is YenkasaAI healthy?
- Which revision is live?
- Show deployment history.
- Show Cloud Run status.

## Observability Capabilities

`ObservabilityAgent` supports:

- error summaries
- log summaries
- performance metrics
- request trends
- incident detection

Supported questions include:

- Why is login failing?
- Show recent backend errors.
- Show notification failures.
- Show error trends.

## Google Cloud Requirements

Environment variables:

- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `CLOUD_RUN_SERVICE`

Default project:

```text
project-10405180-0afd-4ecc-9f8
```

Python packages:

- `google-cloud-run`
- `google-cloud-logging`

## Limitations

- Google Cloud clients are initialized lazily.
- Deployment history currently summarizes service revision state from Cloud Run service metadata.
- Observability summaries are log-based and do not yet combine Cloud Monitoring time series.
- Incident detection uses simple error-count heuristics.
- Product-building workflows are intentionally not implemented in this phase.

## Recommendations for Phase 8

- Add Cloud Monitoring latency and request-count time series.
- Add service-specific SLO thresholds for incident detection.
- Add richer revision history using deployment metadata if available.
- Keep product-building workflows separate from operational intelligence.
