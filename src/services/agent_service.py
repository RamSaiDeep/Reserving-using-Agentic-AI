"""Service facade for agent orchestration."""

from src.agents.supervisor.supervisor_agent import SupervisorAgent


def build_supervisor() -> SupervisorAgent:
    return SupervisorAgent()
