from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionPlanStep:
    agent: str
    query: str
    parallel_group: int = 0


@dataclass(frozen=True)
class ExecutionPlan:
    intents: list[str]
    steps: list[ExecutionPlanStep]
    parallel_safe: bool = False


class ExecutionPlanner:
    intent_agents = {
        "database": ["DatabaseAgent"],
        "repository": ["RepositoryAgent"],
        "search": ["VectorSearchAgent"],
        "audit": ["RepositoryAgent", "VectorSearchAgent", "CodeAuditAgent"],
        "refactor": ["CodeAuditAgent", "RepositoryAgent", "VectorSearchAgent", "RefactorAgent"],
        "deployment": ["CloudRunAgent"],
        "observability": ["ObservabilityAgent"],
        "product_builder": ["ProductBuilderAgent"],
    }

    def plan(self, *, query: str, intents: list[str]) -> ExecutionPlan:
        effective_intents = [intent for intent in intents if intent != "multi-agent"]
        agents: list[str] = []
        for intent in effective_intents:
            for agent in self.intent_agents.get(intent, []):
                if agent not in agents:
                    agents.append(agent)

        steps = [
            ExecutionPlanStep(agent=agent, query=query, parallel_group=self._parallel_group(agent))
            for agent in agents
        ]
        return ExecutionPlan(
            intents=intents,
            steps=steps,
            parallel_safe=len({step.parallel_group for step in steps}) > 1,
        )

    def _parallel_group(self, agent: str) -> int:
        if agent in {"RepositoryAgent", "VectorSearchAgent", "CloudRunAgent", "ObservabilityAgent", "ProductBuilderAgent"}:
            return 1
        return 0
