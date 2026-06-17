"""Base abstractions for the multi-agent reserving system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentTask:
    """A unit of work routed by the supervisor agent."""

    intent: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class AgentResult:
    """Standard response envelope returned by specialist agents."""

    agent: str
    output: dict[str, Any]
    narration: str = ""


class SpecialistAgent(Protocol):
    """Protocol implemented by independently deployable specialist agents."""

    name: str
    supported_intents: set[str]

    def can_handle(self, task: AgentTask) -> bool:
        """Return True when this agent supports the task intent."""

    def handle(self, task: AgentTask) -> AgentResult:
        """Execute the task and return a standard result."""
