"""Agent registry used by the supervisor to avoid hard-coded dependencies."""

from __future__ import annotations

from typing import Dict, Iterable

from src.agents.base import SpecialistAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: Dict[str, SpecialistAgent] = {}

    def register(self, agent: SpecialistAgent) -> SpecialistAgent:
        self._agents[agent.name] = agent
        return agent

    def find_for_intent(self, intent: str) -> SpecialistAgent | None:
        for agent in self._agents.values():
            if intent in agent.supported_intents:
                return agent
        return None

    def all(self) -> Iterable[SpecialistAgent]:
        return tuple(self._agents.values())


registry = AgentRegistry()
