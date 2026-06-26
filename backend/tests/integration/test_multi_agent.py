import sys
import os
import json
import pytest
import pandas as pd

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import agent_workflow
from agents.diagnostics_agent import DiagnosticsAgent
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

@pytest.mark.integration
def test_diagnostics_agent(sample_csv_text):
    session_id = agent_workflow.create_session(sample_csv_text, 5)
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

@pytest.mark.integration
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

@pytest.mark.integration
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

@pytest.mark.integration
def test_reporting_agent():
    agent_workflow.run_agent = mock_run_agent
    agent = ReportingAgent(api_key="mock", base_url="mock", model_name="mock")

    res = agent.generate_report({}, {}, {}, {"recommended_method": "CL_PAID"})
    assert "report_markdown" in res
    assert "CL_PAID" in res["report_markdown"]

@pytest.mark.integration
def test_supervisor_orchestration(sample_csv_text):
    # Patch run_agent on agent_workflow
    agent_workflow.run_agent = mock_run_agent

    session_id = agent_workflow.create_session(sample_csv_text, 5, api_key="mock", model_name="mock")
    
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

def test_deterministic_parser():
    from agents.parser import parse_request
    # Test greeting intent
    parsed = parse_request("Hello, can you help me?")
    assert parsed["intent"] == "GREETING"
    
    # Test out of scope
    parsed = parse_request("Tell me a funny joke")
    assert parsed["intent"] == "OUT_OF_SCOPE"
    
    # Test calculation query and methods
    parsed = parse_request("Calculate Bornhuetter-Ferguson and Mack on incurred basis")
    assert parsed["intent"] == "CALCULATION_QUERY"
    assert "BF" in parsed["methods"]
    assert "MCL" in parsed["methods"]
    assert parsed["basis"] == "incurred"

def test_execution_planner():
    from agents.planner import create_execution_plan
    # Planner should require dataset, results, and recommendation for recommendation query
    parsed = {
        "intent": "RECOMMENDATION_QUERY",
        "methods": [],
        "basis": None,
        "comparison": False,
        "recommendation": True,
        "parameters": {}
    }
    plan = create_execution_plan(parsed)
    assert plan["need_dataset"] is True
    assert plan["need_results"] is True
    assert plan["need_recommendation"] is True

    # Planner should not need results or recommendation for greeting
    parsed_greeting = {
        "intent": "GREETING",
        "methods": [],
        "basis": None,
        "comparison": False,
        "recommendation": False,
        "parameters": {}
    }
    plan_greeting = create_execution_plan(parsed_greeting)
    assert plan_greeting["need_dataset"] is False
    assert plan_greeting["need_results"] is False
    assert plan_greeting["need_recommendation"] is False

def test_stage_manager_dependencies():
    from agents.stage_manager import StageManager
    manager = StageManager()
    
    # Check that recommendation stage depends on results
    rec_stage = manager.stages["recommendation"]
    assert "results" in rec_stage.deps
    
    # Check that results stage depends on preprocessing
    results_stage = manager.stages["results"]
    assert "preprocessing" in results_stage.deps
    
    # Check that preprocessing stage depends on dataset
    prep_stage = manager.stages["preprocessing"]
    assert "dataset" in prep_stage.deps

def test_dataset_metadata_queries_and_method_specific_execution(sample_csv_text):
    from agents.parser import parse_request
    from agents.planner import create_execution_plan
    from agents.stage_manager import StageManager
    
    # 1. Verify Dataset Metadata Query parsing
    queries = [
        "How many rows does the dataset have?",
        "What columns are present?",
        "What variables are available?",
        "What is the shape of the dataset?",
        "How many accident years are there?",
        "Are there missing values?",
        "What entities are present?",
        "What development periods exist?"
    ]
    for q in queries:
        parsed = parse_request(q)
        assert parsed["intent"] == "DATASET_QUERY", f"Failed for query: {q}"
        plan = create_execution_plan(parsed)
        assert plan["need_dataset"] is True
        
    # 2. Verify deterministic replies for metadata queries
    session_id = agent_workflow.create_session(sample_csv_text, 5, api_key="mock", model_name="mock")
    # Pre-populate session
    agent_workflow.ingest_csv(session_id)
    agent_workflow.perform_data_quality_checks(session_id)
    agent_workflow.build_loss_triangle(session_id)
    session = agent_workflow.SESSION_STORE[session_id]
    
    from agents.supervisor import SupervisorAgent
    sv = SupervisorAgent()
    
    rep_rows = sv.answer_dataset_query(session, "How many rows does the dataset have?")
    assert "rows" in rep_rows and "columns" in rep_rows
    
    rep_cols = sv.answer_dataset_query(session, "What columns are present?")
    assert "development" in rep_cols or "paid" in rep_cols or "accident" in rep_cols
    
    rep_missing = sv.answer_dataset_query(session, "Are there missing values?")
    assert "missing values" in rep_missing or "no missing values" in rep_missing.lower()
    
    # 3. Verify method-specific execution
    # Case A: Chain Ladder explicitly requested
    p_cl = parse_request("Run the Chain Ladder method")
    assert p_cl["methods"] == ["CL"]
    plan_cl = create_execution_plan(p_cl)
    assert plan_cl["methods_required"] == ["CL"]
    # Verify execution only runs CL
    session_cl = agent_workflow.create_session(sample_csv_text, 5, api_key="mock", model_name="mock")
    agent_workflow.ingest_csv(session_cl)
    agent_workflow.perform_data_quality_checks(session_cl)
    agent_workflow.build_loss_triangle(session_cl)
    agent_workflow.calculate_ldfs(session_cl)
    s_cl = agent_workflow.SESSION_STORE[session_cl]
    sm = StageManager()
    sm.ensure_stage("results", plan_cl, session_cl, s_cl, [])
    assert "CL" in s_cl["results_by_method"]
    assert len(s_cl["results_by_method"]) == 1
    
    # Case B: Mack explicitly requested
    p_mack = parse_request("Run Mack")
    assert p_mack["methods"] == ["MCL"]
    plan_mack = create_execution_plan(p_mack)
    session_mack = agent_workflow.create_session(sample_csv_text, 5, api_key="mock", model_name="mock")
    agent_workflow.ingest_csv(session_mack)
    agent_workflow.perform_data_quality_checks(session_mack)
    agent_workflow.build_loss_triangle(session_mack)
    agent_workflow.calculate_ldfs(session_mack)
    s_mack = agent_workflow.SESSION_STORE[session_mack]
    sm.ensure_stage("results", plan_mack, session_mack, s_mack, [])
    assert "MCL" in s_mack["results_by_method"]
    assert len(s_mack["results_by_method"]) == 1
    
    # Case C: Compare Mack and BF
    p_comp = parse_request("Compare Mack and BF")
    assert "MCL" in p_comp["methods"]
    assert "BF" in p_comp["methods"]
    plan_comp = create_execution_plan(p_comp)
    session_comp = agent_workflow.create_session(sample_csv_text, 5, api_key="mock", model_name="mock")
    agent_workflow.ingest_csv(session_comp)
    agent_workflow.perform_data_quality_checks(session_comp)
    agent_workflow.build_loss_triangle(session_comp)
    agent_workflow.calculate_ldfs(session_comp)
    s_comp = agent_workflow.SESSION_STORE[session_comp]
    sm.ensure_stage("results", plan_comp, session_comp, s_comp, [])
    assert "MCL" in s_comp["results_by_method"]
    assert "BF" in s_comp["results_by_method"]
    assert len(s_comp["results_by_method"]) == 2

    # Case D: Conversational Continuity / Follow-up queries with history
    # User asks "Compare it with BF" after having run/discussed CL
    history = [
        {"role": "user", "text": "Run CL on Incurred"},
        {"role": "assistant", "text": "I have run CL on Incurred. The Ultimate is ..."}
    ]
    p_followup = parse_request("Compare it with BF", history=history)
    assert "BF" in p_followup["methods"]
    assert "CL" in p_followup["methods"]
    assert p_followup["basis"] == "incurred"

    # User asks "What about Mack?" after having run CL on paid
    history_paid = [
        {"role": "user", "text": "Run CL on paid"},
        {"role": "assistant", "text": "I have run CL on paid."}
    ]
    p_mack_followup = parse_request("What about Mack?", history=history_paid)
    assert p_mack_followup["methods"] == ["MCL"]
    assert p_mack_followup["basis"] == "paid"

    # User asks "Run it on incurred" without specifying the method
    p_incurred_followup = parse_request("Run it on incurred", history=history_paid)
    assert p_incurred_followup["methods"] == ["CL"]
    assert p_incurred_followup["basis"] == "incurred"

    # Verify new natural phrasing dataset queries map to DATASET_QUERY
    natural_queries = [
        "how many records in the dataset?",
        "what lines of business are there?",
        "are there empty fields?",
        "show me development ages"
    ]
    for q in natural_queries:
        parsed = parse_request(q)
        assert parsed["intent"] == "DATASET_QUERY", f"Failed for natural phrasing: {q}"

def test_chat_agent_architecture_and_behaviour():
    from agents.prompt_builders import ChatIntent, ChatRequest, ChatClassifier, ContextBuilder, ChatPromptBuilder
    from agents.parser import parse_request
    import json
    
    # 1. Verify ChatIntent Classification
    # CONCEPTUAL
    r = ChatClassifier.classify("What is IBNR?", parse_request("What is IBNR?"))
    assert r.intent == ChatIntent.CONCEPTUAL
    
    # COLUMN_INFO
    r = ChatClassifier.classify("What columns are in the dataset?", parse_request("What columns are in the dataset?"))
    assert r.intent == ChatIntent.COLUMN_INFO
    
    # DATA_EXPLORATION
    r = ChatClassifier.classify("Summarize the dataset rows and size", parse_request("Summarize the dataset rows and size"))
    assert r.intent == ChatIntent.DATA_EXPLORATION
    
    # CALCULATION
    r = ChatClassifier.classify("Calculate the Chain Ladder reserve for 1997", parse_request("Calculate the Chain Ladder reserve for 1997"))
    assert r.intent == ChatIntent.CALCULATION
    assert "CL" in r.methods
    assert r.entities.get("accident_year") == 1997
    
    # METHOD_EXPLANATION
    r = ChatClassifier.classify("Explain the Chain Ladder formula and assumptions", parse_request("Explain the Chain Ladder formula and assumptions"))
    assert r.intent == ChatIntent.METHOD_EXPLANATION
    
    # DIAGNOSTIC
    r = ChatClassifier.classify("Show diagnostics and outliers", parse_request("Show diagnostics and outliers"))
    assert r.intent == ChatIntent.DIAGNOSTIC
    
    # RECOMMENDATION
    r = ChatClassifier.classify("Which method do you recommend?", parse_request("Which method do you recommend?"))
    assert r.intent == ChatIntent.RECOMMENDATION
    
    # COMPARISON
    r = ChatClassifier.classify("Compare CL vs BF", parse_request("Compare CL vs BF"))
    assert r.intent == ChatIntent.COMPARISON
    assert "CL" in r.methods
    assert "BF" in r.methods
    
    # REPORT
    r = ChatClassifier.classify("Give me a summary report of the analysis", parse_request("Give me a summary report of the analysis"))
    assert r.intent == ChatIntent.REPORT
    
    # UNKNOWN
    r = ChatClassifier.classify("write a python code to scrape weather", parse_request("write a python code to scrape weather"))
    assert r.intent == ChatIntent.UNKNOWN
    
    # 2. Verify Priority-Based Context Assembly
    session_data = {
        "n_years": 5,
        "results": {
            "selected_method": "CL",
            "best_estimate": 1000.0,
            "totalIBNR": 200.0,
            "methods": [
                {"code": "CL", "name": "Chain Ladder", "status": "success", "ultimate": 1000.0, "ibnr": 200.0, "loss_ratio": 0.6, "reserve": 200.0},
                {"code": "BF", "name": "Bornhuetter-Ferguson", "status": "success", "ultimate": 1100.0, "ibnr": 300.0, "loss_ratio": 0.7, "reserve": 300.0}
            ]
        },
        "diagnostics_analysis": {
            "metrics": {
                "overall": {"n_accident_years": 5, "n_dev_periods": 5, "total_paid": 5000.0},
                "ldf_stability": {"average_cov": 0.05, "cl_suitable_indicator": "Stable"}
            },
            "llm_analysis": {"data_quality_assessment": "Good Quality Data"}
        },
        "ldfs": [1.5, 1.2, 1.1, 1.05],
        "cdfs": [2.0, 1.3, 1.1, 1.05]
    }
    
    # CONCEPTUAL context should be minimal
    req_concept = ChatRequest(intent=ChatIntent.CONCEPTUAL)
    ctx = ContextBuilder.build(session_data, req_concept)
    assert "methods_summary" not in ctx
    assert "diagnostics" not in ctx
    assert ctx.get("n_years") == 5
    
    # CALCULATION context (with specific method CL) should only have CL
    req_calc = ChatRequest(intent=ChatIntent.CALCULATION, methods=["CL"])
    ctx = ContextBuilder.build(session_data, req_calc)
    assert "methods_summary" in ctx
    assert len(ctx["methods_summary"]) == 1
    assert ctx["methods_summary"][0]["code"] == "CL"
    assert "overall_results" in ctx
    
    # Suffix-appended and Case Outstanding codes matching test
    suffix_session_data = {
        "n_years": 5,
        "results": {
            "selected_method": "CL_PAID",
            "best_estimate": 9570000.0,
            "methods": [
                {"code": "CL_PAID", "name": "Chain Ladder (Paid)", "status": "success", "ultimate": 8250000.0, "ibnr": 199000.0, "reserve": 199000.0},
                {"code": "CC_PAID", "name": "Cape Cod (Stanard-Buhlmann) (Paid)", "status": "success", "ultimate": 9570000.0, "ibnr": 1520000.0, "reserve": 1520000.0},
                {"code": "CO", "name": "Case Outstanding", "status": "success", "ultimate": 8050000.0, "ibnr": 0.0, "reserve": 0.0}
            ]
        }
    }
    
    # Matching multiple codes
    req_multi = ChatRequest(intent=ChatIntent.CALCULATION, methods=["CC", "CO"])
    ctx_multi = ContextBuilder.build(suffix_session_data, req_multi)
    assert "methods_summary" in ctx_multi
    summary_codes = [m["code"] for m in ctx_multi["methods_summary"]]
    assert "CC_PAID" in summary_codes
    assert "CO" in summary_codes
    assert "CL_PAID" not in summary_codes
    
    # Context size pruning: if a low-priority field (e.g. curves) is extremely large, it gets pruned
    large_curves = [1.0] * 2000 # extremely large list to exceed 3000 char JSON limit
    session_large = dict(session_data)
    session_large["ldfs"] = large_curves
    
    req_diag = ChatRequest(intent=ChatIntent.DIAGNOSTIC, message="LDF curve")
    ctx_pruned = ContextBuilder.build(session_large, req_diag)
    # Check that ldfs_curve is NOT in ctx_pruned because it exceeded length and got pruned first (Priority 4)
    assert "ldfs_curve" not in ctx_pruned
    # But n_years and diagnostics (Priority 1 and 3) should remain
    assert ctx_pruned.get("n_years") == 5
    assert "diagnostics" in ctx_pruned
    
    # 3. Verify Session State Updates via Supervisor Agent
    from agents.supervisor import SupervisorAgent
    sv = SupervisorAgent()
    
    session_mock = {
        "api_key": "mock",
        "model_name": "mock",
        "n_years": 5,
        "results": {
            "selected_method": "CL",
            "best_estimate": 1000.0,
            "totalIBNR": 200.0,
            "methods": [{"code": "CL", "name": "Chain Ladder", "status": "success", "ultimate": 1000.0, "ibnr": 200.0, "loss_ratio": 0.6, "reserve": 200.0}]
        }
    }
    
    # Call run_parallel_chat and verify state updates
    from unittest.mock import MagicMock, patch
    
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Mock chatbot response"
    mock_choice.message.tool_calls = None
    mock_response.choices = [mock_choice]
    mock_response.usage = None
    mock_client.chat.completions.create.return_value = mock_response
    
    with patch("agents.supervisor.OpenAI", return_value=mock_client), \
         patch("agents.supervisor.StageManager.ensure_stage"):
        sv.run_parallel_chat("session_123", session_mock, "What is IBNR?", [])
        assert session_mock.get("last_intent") == ChatIntent.CONCEPTUAL.value
        
        # Test session method/basis persistence
        sv.run_parallel_chat("session_123", session_mock, "Calculate reserve using CL on paid basis", [])
        assert session_mock.get("last_intent") == ChatIntent.CALCULATION.value
        assert session_mock.get("last_method") == ["CL"]
        assert session_mock.get("last_basis") == "paid"
        
        # Test continuity: user asks "what about incurred?" (no method mentioned, should inherit "CL")
        sv.run_parallel_chat("session_123", session_mock, "what about incurred?", [])
        assert session_mock.get("last_intent") == ChatIntent.CALCULATION.value
        assert session_mock.get("last_method") == ["CL"] # inherited
        assert session_mock.get("last_basis") == "incurred" # updated

