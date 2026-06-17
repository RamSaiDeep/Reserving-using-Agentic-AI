"""Application service for reserving workflows."""

from src.agents.base import AgentTask
from src.agents.supervisor.supervisor_agent import SupervisorAgent


class ReserveService:
    def __init__(self, supervisor: SupervisorAgent | None = None) -> None:
        self.supervisor = supervisor or SupervisorAgent()

    def summarize_upload(self, csv_text: str) -> dict:
        result = self.supervisor.dispatch(AgentTask("summarize_triangle", {"csv_text": csv_text}))
        return result.output

    def execute_method(self, csv_text: str, method_code: str, params: dict, custom_ldfs: list) -> dict:
        result = self.supervisor.dispatch(
            AgentTask(
                "execute_reserving_method",
                {
                    "csv_text": csv_text,
                    "method_code": method_code,
                    "params": params,
                    "custom_ldfs": custom_ldfs,
                },
            )
        )
        return result.output
