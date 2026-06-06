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
```
