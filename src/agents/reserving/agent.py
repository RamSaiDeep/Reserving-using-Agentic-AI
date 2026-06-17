"""Reserving agent that executes registered reserving methods."""

from src.agents.base import AgentResult, AgentTask
from src.agents.registry import registry
from src.reserving import registry as method_registry
from src.triangles.builders import triangle_from_csv


class ReservingAgent:
    name = "reserving"
    supported_intents = {"execute_reserving_method"}

    def can_handle(self, task: AgentTask) -> bool:
        return task.intent in self.supported_intents

    def handle(self, task: AgentTask) -> AgentResult:
        payload = task.payload
        triangle = triangle_from_csv(payload["csv_text"])
        for ay_str, premium in payload.get("params", {}).get("premiums", {}).items():
            triangle.premiums[int(ay_str)] = float(premium)

        method_class = method_registry.get(payload["method_code"])
        if method_class is None:
            raise ValueError(f"Unknown reserving method: {payload['method_code']}")

        model = method_class()
        model.fit(triangle, payload.get("params", {}), payload.get("custom_ldfs", []))
        diagonal = triangle.get_latest_diagonal()
        return AgentResult(
            agent=self.name,
            output={
                "method": method_class.label,
                "results": model.get_results(),
                "totalIBNR": model.get_total_ibnr(),
                "totalUlt": model.get_total_ultimate(),
                "totalPaid": sum(v for v in diagonal if v is not None),
            },
        )


registry.register(ReservingAgent())
