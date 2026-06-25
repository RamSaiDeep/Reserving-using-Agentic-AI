import sys
import os
import json
import pytest
import pandas as pd

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import agent_workflow
from agents.diagnostics_agent import DiagnosticsAgent
from agents.reserving_agent import ReservingAgent
from agents.comparison_agent import ComparisonAgent
from agents.recommendation_agent import RecommendationAgent
from agents.reporting_agent import ReportingAgent
from agents.supervisor import SupervisorAgent

def mock_run_agent(api_key, base_url, model_name, sys_inst, prompt, tools=None):
    # Depending on system instruction content, return different mock JSON responses
    sys_inst_lower = sys_inst.lower()
    if "recommender" in sys_inst_lower or "recommendation" in sys_inst_lower:
        return json.dumps({
            "recommended_method": "CL_PAID",
            "confidence": "High",
            "reasoning": [
                "Stable historical development patterns",
                "High data quality with low volatility",
                "Mature years favor development-based method"
            ],
            "assumptions_used": "Volume weighted development averages.",
            "cautions": ["None identified under current conditions."],
            "alternative_methods": ["BF_PAID", "BK_PAID"]
        })
    elif "reporting agent" in sys_inst_lower:
        return "# Mock Actuarial Report\n\n## Executive Summary\nRecommended method is CL_PAID."
    elif "comparison" in sys_inst_lower:
        return "Mock comparison explanation: Method values differ slightly due to BF dependency on ELR versus Chain Ladder purely relying on development factors."
    elif "diagnostics agent" in sys_inst_lower:
        return json.dumps({
            "data_quality_assessment": "Mock quality check: Excellent data, no missing values.",
            "reporting_pattern_diagnostics": "Mock reporting pattern check: Smooth incremental progression.",
            "ldf_stability_assessment": "Mock stability check: High stability in recent periods.",
            "outlier_detection": "Mock outlier detection: No distinct anomalies found.",
            "maturity_assessment": "Mock maturity check: Data represents a mature book of business."
        })
    elif "validation" in sys_inst_lower:
        return json.dumps({
            "validation_summary": "Mock validation check: All mathematical models executed successfully and satisfied actuarial constraints.",
            "assumptions_configured": "Mock assumptions configured: Used volume-weighted averages with tail factor = 1.0.",
            "notes": "No warnings or issues identified."
        })
    return "Mock general response"


def test_diagnostics_agent():
    # Load test data
    with open("../data/df_masked.csv", "r") as f:
        csv_text = f.read()

    session_id = agent_workflow.create_session(csv_text, 5)
    agent_workflow.ingest_csv(session_id)
    agent_workflow.build_loss_triangle(session_id)

    session = agent_workflow.SESSION_STORE[session_id]
    triangle = session['triangle']
    df = session['df']

    # Patch run_agent on agent_workflow
    agent_workflow.run_agent = mock_run_agent

    agent = DiagnosticsAgent(api_key="mock", base_url="mock", model_name="mock")
    res = agent.analyze(triangle, df)

    assert "metrics" in res
    assert "llm_analysis" in res
    assert res["llm_analysis"]["data_quality_assessment"] == "Mock quality check: Excellent data, no missing values."
    print("DiagnosticsAgent tested successfully.")


def test_comparison_agent():
    agent_workflow.run_agent = mock_run_agent
    agent = ComparisonAgent(api_key="mock", base_url="mock", model_name="mock")

    methods_results = [
        {"code": "CL_PAID", "name": "Chain Ladder (Paid)", "status": "success", "ultimate": 1000.0, "ibnr": 200.0, "reserve": 200.0, "paid": 800.0},
        {"code": "BF_PAID", "name": "Bornhuetter-Ferguson (Paid)", "status": "success", "ultimate": 950.0, "ibnr": 150.0, "reserve": 150.0, "paid": 800.0}
    ]

    res = agent.compare(methods_results)
    assert "comparison_table" in res
    assert "differences" in res
    assert "explanation" in res
    assert res["median_ultimate"] == 975.0
    assert "Method values differ slightly" in res["explanation"]
    print("ComparisonAgent tested successfully.")


def test_recommendation_agent():
    agent_workflow.run_agent = mock_run_agent
    agent = RecommendationAgent(api_key="mock", base_url="mock", model_name="mock")

    diagnostics = {"llm_analysis": {"maturity_assessment": "Mature"}, "metrics": {"overall": {}}}
    reserving_outputs = {"selected_method": "CL_PAID", "best_estimate": 1000.0}
    comparison_results = {"comparison_table": [], "differences": {}, "explanation": "test"}

    res = agent.recommend(diagnostics, reserving_outputs, comparison_results)
    assert res["recommended_method"] == "CL_PAID"
    assert res["confidence"] == "High"
    assert len(res["reasoning"]) == 3
    print("RecommendationAgent tested successfully.")


def test_reporting_agent():
    agent_workflow.run_agent = mock_run_agent
    agent = ReportingAgent(api_key="mock", base_url="mock", model_name="mock")

    res = agent.generate_report({}, {}, {}, {"recommended_method": "CL_PAID"})
    assert "report_markdown" in res
    assert "CL_PAID" in res["report_markdown"]
    print("ReportingAgent tested successfully.")


def test_supervisor_orchestration():
    # Patch run_agent on agent_workflow
    agent_workflow.run_agent = mock_run_agent

    # Load test data
    with open("../data/df_masked.csv", "r") as f:
        csv_text = f.read()

    session_id = agent_workflow.create_session(csv_text, 5, api_key="mock", model_name="mock")
    
    # Run pipeline Part 1
    stream_part1 = list(agent_workflow.execute_sequential_pipeline_part1(session_id))
    assert len(stream_part1) > 0
    
    # Run recommendation & report compiling
    session = agent_workflow.SESSION_STORE[session_id]
    results_summary = [
        {"code": "CL_PAID", "name": "Chain Ladder (Paid)", "status": "success", "ultimate": 8051238.0, "ibnr": 1601676.0, "reserve": 1601676.0, "paid": 6449562.0},
        {"code": "BF_PAID", "name": "Bornhuetter-Ferguson (Paid)", "status": "success", "ultimate": 8104037.0, "ibnr": 1654475.0, "reserve": 1654475.0, "paid": 6449562.0}
    ]
    
    rec_out = agent_workflow.run_reserve_recommendation_agent(session_id, results_summary)
    assert rec_out["recommended_method"] == "CL_PAID"
    assert rec_out["confidence"] == "High"
    assert "report_markdown" in session
    assert "diagnostics_analysis" in session
    assert "comparison" in session
    assert "recommendation" in session
    
    # Verify Chat Agent
    reply = agent_workflow.run_parallel_chat(session_id, "Explain the diagnostics summary", [])
    assert reply is not None
    print("SupervisorAgent orchestration tested successfully.")

if __name__ == "__main__":
    pytest.main([__file__])
