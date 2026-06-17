# Multi-Agent Architecture

The application follows a supervisor-agent pattern:

- `backend.src.agents.supervisor_agent.supervisor_agent.SupervisorAgent` receives a task and routes it by intent.
- Specialist agents declare `supported_intents` and register with `backend.src.agents.registry.registry`.
- Reserving methods are independent domain classes registered in `backend.src.reserving.registry.registry`.
- API routes call services, services call the supervisor, and reserving calculations remain outside orchestration code.

To add a new agent, implement the `SpecialistAgent` protocol and register an instance. Existing agents do not need to be edited.

To add a new reserving method, implement a `MethodBase` subclass and call `register_method`. Agent routing remains unchanged.
