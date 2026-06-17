"""Data quality agent for triangle validation and summary tasks."""

from backend.src.agents.base import AgentResult, AgentTask
from backend.src.agents.registry import registry
from backend.src.triangles.builders import triangle_from_csv


class DataQualityAgent:
    name = "data_quality"
    supported_intents = {"summarize_triangle"}

    def can_handle(self, task: AgentTask) -> bool:
        return task.intent in self.supported_intents

    def handle(self, task: AgentTask) -> AgentResult:
        triangle = triangle_from_csv(task.payload["csv_text"])
        return AgentResult(
            agent=self.name,
            output={
                "summary": triangle.get_summary(),
                "triangle": {
                    "accidentYears": triangle.accident_years,
                    "devAges": triangle.dev_ages,
                    "matrix": triangle.matrix,
                    "ldfs": triangle.compute_ldfs(),
                },
            },
        )


registry.register(DataQualityAgent())
