from src.agents.base import AgentTask
from src.agents.supervisor.supervisor_agent import SupervisorAgent
from src.reserving import registry as method_registry
from src.services.reserve_service import ReserveService

CSV_TEXT = "accident_year,12,24,36\n2021,100,150,180\n2022,120,170,\n2023,130,,\n"


def test_builtin_reserving_methods_are_registered():
    assert {"CL", "MCL", "BF", "BK", "CC", "CO", "CLK"}.issubset(set(method_registry.codes()))


def test_supervisor_routes_to_data_quality_agent():
    result = SupervisorAgent().dispatch(AgentTask("summarize_triangle", {"csv_text": CSV_TEXT}))
    assert result.agent == "data_quality"
    assert result.output["summary"]["accidentYears"] == 3


def test_reserve_service_executes_chain_ladder_without_agent_coupling():
    service = ReserveService()
    summary = service.summarize_upload(CSV_TEXT)
    selected_ldfs = [item["volumeWeighted"] or 1.0 for item in summary["triangle"]["ldfs"]]

    result = service.execute_method(CSV_TEXT, "CL", {}, selected_ldfs)

    assert result["method"] == "Chain Ladder (Basic)"
    assert result["totalUlt"] >= result["totalPaid"]
