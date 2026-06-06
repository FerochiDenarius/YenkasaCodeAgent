from __future__ import annotations

from typing import Any

from app.models.agent import AgentResponse
from app.orchestrator.execution_planner import ExecutionPlan


class ResponseSynthesizer:
    def synthesize(self, *, query: str, plan: ExecutionPlan, responses: list[AgentResponse]) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        recommendations: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        failures = [response for response in responses if not response.success]

        for response in responses:
            if response.success:
                self._collect_success(response=response, findings=findings, recommendations=recommendations, evidence=evidence)
            else:
                findings.append(
                    {
                        "severity": "HIGH",
                        "category": "Execution",
                        "issue": f"{response.agent} failed: {response.error}",
                        "recommendation": "Review the failing agent dependency and retry the workflow.",
                    }
                )

        summary = self._summary(query=query, plan=plan, responses=responses, failure_count=len(failures))
        return {
            "summary": summary,
            "findings": findings,
            "recommendations": recommendations,
            "evidence": evidence,
            "plan": {
                "intents": plan.intents,
                "agents": [step.agent for step in plan.steps],
                "parallel_safe": plan.parallel_safe,
            },
            "agent_results": [self._agent_contract(response) for response in responses],
        }

    def _collect_success(
        self,
        *,
        response: AgentResponse,
        findings: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> None:
        result = response.result
        findings.extend(result.get("findings", []))
        recommendations.extend(result.get("recommendations", []))
        if "matches" in result:
            evidence.extend({"agent": response.agent, **match} for match in result["matches"])
        if "service_status" in result or "deployment_health" in result or "error_summary" in result or "log_summary" in result:
            evidence.append({"agent": response.agent, "result": result})
        if not any(key in result for key in ("findings", "recommendations", "matches")):
            evidence.append({"agent": response.agent, "result": result})

    def _agent_contract(self, response: AgentResponse) -> dict[str, Any]:
        return {
            "agent": response.agent,
            "confidence": 1.0 if response.success else 0.0,
            "findings": response.result.get("findings", []) if response.success else [],
            "recommendations": response.result.get("recommendations", []) if response.success else [],
            "evidence": response.result.get("matches", []) if response.success else [],
            "execution_time_ms": response.result.get("execution_time_ms", 0) if response.success else 0,
            "success": response.success,
            "error": response.error,
        }

    def _summary(self, *, query: str, plan: ExecutionPlan, responses: list[AgentResponse], failure_count: int) -> str:
        agent_count = len(responses)
        if failure_count:
            return f"YIO executed {agent_count} agent(s) for '{query}' with {failure_count} failure(s)."
        return f"YIO executed {agent_count} agent(s) for '{query}' across intents: {', '.join(plan.intents)}."
