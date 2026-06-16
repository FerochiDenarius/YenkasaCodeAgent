from __future__ import annotations

import asyncio
import time

from app.agents.registry import AgentRegistry
from app.models.agent import AgentResponse
from app.orchestrator.execution_planner import ExecutionPlanner
from app.orchestrator.intent_classifier import IntentClassifier
from app.orchestrator.response_synthesizer import ResponseSynthesizer
from app.utils.evidence_package import build_evidence_package


class YenkasaIntelligenceOrchestrator:
    name = "YIO"

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        classifier: IntentClassifier | None = None,
        planner: ExecutionPlanner | None = None,
        synthesizer: ResponseSynthesizer | None = None,
    ) -> None:
        self.registry = registry
        self.classifier = classifier or IntentClassifier()
        self.planner = planner or ExecutionPlanner()
        self.synthesizer = synthesizer or ResponseSynthesizer()

    async def execute(self, *, query: str, context: dict[str, object] | None = None) -> AgentResponse:
        started = time.perf_counter()
        context = context or {}
        intents = self.classifier.classify(query)
        plan = self.planner.plan(query=query, intents=intents)
        responses = await self._execute_plan(query=query, context=context, plan=plan)
        result = self.synthesizer.synthesize(query=query, plan=plan, responses=responses)
        result["execution_time_ms"] = int((time.perf_counter() - started) * 1000)
        success = all(response.success for response in responses)
        error = None if success else "One or more planned agents failed."
        return AgentResponse(
            agent=self.name,
            success=success,
            result=result,
            error=error,
            evidence_package=build_evidence_package(agent=self.name, result=result, success=success, error=error, query=query),
        )

    async def _execute_plan(self, *, query: str, context: dict[str, object], plan) -> list[AgentResponse]:
        if not plan.steps:
            return []
        parallel_steps = [step for step in plan.steps if step.parallel_group > 0]
        sequential_steps = [step for step in plan.steps if step.parallel_group == 0]

        responses: list[AgentResponse] = []
        if parallel_steps:
            responses.extend(await asyncio.gather(*(self._execute_step(step, context) for step in parallel_steps)))
        for step in sequential_steps:
            responses.append(await self._execute_step(step, context))
        return self._order_responses(plan_agents=[step.agent for step in plan.steps], responses=responses)

    async def _execute_step(self, step, context: dict[str, object]) -> AgentResponse:
        agent = self.registry.get(step.agent)
        if agent is None:
            return AgentResponse(agent=step.agent, success=False, result={}, error=f"Agent '{step.agent}' is not registered.")
        started = time.perf_counter()
        response = await agent.execute(query=step.query, context=context)
        if response.success:
            response.result.setdefault("execution_time_ms", int((time.perf_counter() - started) * 1000))
        return response

    def _order_responses(self, *, plan_agents: list[str], responses: list[AgentResponse]) -> list[AgentResponse]:
        by_agent = {response.agent: response for response in responses}
        return [by_agent[agent] for agent in plan_agents if agent in by_agent]
