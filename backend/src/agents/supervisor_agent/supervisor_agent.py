"""Supervisor-agent router for the reserving system."""

from backend.src.agents.base import AgentResult, AgentTask
from backend.src.agents.registry import registry

# Import built-in agents for registration side effects. Adding a new agent only
# requires a module that registers itself; this supervisor remains unchanged.
from backend.src.agents.data_agent import agent as _data_quality  # noqa: F401
from backend.src.agents.reserving_agent import agent as _reserving  # noqa: F401


class SupervisorAgent:
    """Routes tasks to specialist agents based on declared capabilities."""

    def dispatch(self, task: AgentTask) -> AgentResult:
        agent = registry.find_for_intent(task.intent)
        if agent is None:
            raise ValueError(f"No registered agent can handle intent: {task.intent}")
        return agent.handle(task)
