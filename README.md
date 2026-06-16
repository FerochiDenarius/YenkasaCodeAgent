# YenkasaCode Agent

Engineering Intelligence Layer for the Yenkasa ecosystem.

This repository is being built in phases. Phase 1 contains only the foundation and orchestrator framework.

## Phase 1

- FastAPI app
- Health endpoint
- BaseAgent
- AgentRegistry
- YenkasaCodeOrchestrator
- Standard agent response model
- System agent for discovery/routing foundation

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API

```http
GET /health
POST /api/agent/query
GET /api/agent/agents
GET /api/agent/metrics
```

## Developer CLI

Use `yca` to test YenkasaCodeAgent locally from a MacBook:

```bash
./yca login
./yca
```

Inside interactive mode, type normal questions or short commands:

```text
yca> what repositories are indexed?
yca> agents
yca> search livestreamPermissions
yca> memory status
yca> audit
yca> exit
```

The CLI authenticates with YenkasaAI credentials, stores the JWT in `~/.yca/config.json`, writes local request logs to `logs/yca.jsonl`, and calls the deployed YenkasaCodeAgent API. See [YCA_CLI.md](YCA_CLI.md) for the full command reference and operational notes.

## Docker

```bash
docker build -t yenkasa-code-agent .
docker run --rm -p 8080:8080 --env-file .env.example yenkasa-code-agent
```
