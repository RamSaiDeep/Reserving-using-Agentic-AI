"""Service facade for agent orchestration."""

from backend.src.agents.supervisor_agent.supervisor_agent import SupervisorAgent


def build_supervisor() -> SupervisorAgent:
    return SupervisorAgent()
