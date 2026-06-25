import sys
import os
import json
import pytest
import asyncio
import copy

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import agent_workflow
from reserving.core.tools import compute_suggested_elr, compute_mature_accident_years
from main import ExecuteRequest, MethodConfig, execute_all_models

@pytest.mark.regression
def test_actuarial_elr_and_mature_years_calibration(sample_csv_text):
    session_id = agent_workflow.create_session(sample_csv_text, 5)
    agent_workflow.ingest_csv(session_id)
    agent_workflow.build_loss_triangle(session_id)
    agent_workflow.calculate_ldfs(session_id)
    
    session = agent_workflow.SESSION_STORE[session_id]
    t = session['triangle']
    
    assert t.premiums.get(1988) == 913636, f"Expected 913636, got {t.premiums.get(1988)}"
    
    m_years_105 = compute_mature_accident_years(t, 1.05)["mature_years"]
    m_years_110 = compute_mature_accident_years(t, 1.10)["mature_years"]
    assert len(m_years_110) >= len(m_years_105), "CDF 1.10 should include at least as many years as CDF 1.05"
    
    elr_paid_105 = compute_suggested_elr(t, "paid", 1.05)
    assert 60.0 <= elr_paid_105 <= 75.0, f"ELR suggestion out of range: {elr_paid_105}%"

@pytest.mark.regression
def test_execution_capabilities_and_version_contract(sample_csv_text):
    session_id = agent_workflow.create_session(sample_csv_text, 5)
    agent_workflow.ingest_csv(session_id)
    agent_workflow.build_loss_triangle(session_id)
    agent_workflow.calculate_ldfs(session_id)
    
    session = agent_workflow.SESSION_STORE[session_id]
    t = session['triangle']
    
    req = ExecuteRequest(
        session_id=session_id,
        configs={
            "CL": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
            "BF": MethodConfig(enabled=True, run_paid=True, run_incurred=False),
            "CO": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
        },
        paid_ldfs=[1.0] * len(t.dev_ages),
        incurred_ldfs=[1.0] * len(t.dev_ages),
        mature_cdf_threshold=1.05,
        api_key="mock-key",
        model_name="mock-model"
    )
    
    # Mock run_agent
    orig_run_agent = agent_workflow.run_agent
    agent_workflow.run_agent = lambda *args, **kwargs: '{"recommended_method": "CL_PAID", "confidence": "High", "reasoning": ["Mock test reasoning"]}'
    
    try:
        # PAID source
        req_paid = copy.deepcopy(req)
        req_paid.data_source = "paid"
        res_paid = asyncio.run(execute_all_models(req_paid))
        assert res_paid.get("success") == True
        
        methods_paid = res_paid.get("methods", [])
        result_ids_paid = [m.get("result_id") for m in methods_paid]
        assert "CL_PAID" in result_ids_paid
        assert "BF_PAID" in result_ids_paid
        assert "CO" in result_ids_paid
        
        # INCURRED source
        req_inc = copy.deepcopy(req)
        req_inc.data_source = "incurred"
        res_inc = asyncio.run(execute_all_models(req_inc))
        assert res_inc.get("success") == True
        
        methods_inc = res_inc.get("methods", [])
        result_ids_inc = [m.get("result_id") for m in methods_inc]
        assert "CL_INCURRED" in result_ids_inc
        
        bf_res = next((m for m in methods_inc if m.get("result_id") == "BF_INCURRED"), None)
        assert bf_res is not None and bf_res.get("status") == "disabled", "BF Incurred should be disabled"
        
        # Validate output contract
        all_methods = methods_paid + methods_inc
        for m in all_methods:
            if m.get("status") == "success":
                assert m.get("version") == "2.0"
                assert m.get("valuation_date") == "1997-12-31"
                assert m.get("source_basis") in ["paid", "incurred", "both"]
                assert isinstance(m.get("paid"), float)
                assert isinstance(m.get("case_outstanding"), float)
                assert isinstance(m.get("reported"), float)
                assert isinstance(m.get("ultimate"), float)
                assert isinstance(m.get("ibnr"), float)
                assert isinstance(m.get("reserve"), float)
                assert isinstance(m.get("future_paid"), float)
                assert m.get("future_paid") == m.get("reserve")
                assert isinstance(m.get("paid_maturity"), float)
                assert isinstance(m.get("reported_maturity"), float)
                assert isinstance(m.get("ultimate_by_ay"), dict)
                assert isinstance(m.get("ibnr_by_ay"), dict)
                assert isinstance(m.get("reserve_by_ay"), dict)
                
                dq = m.get("data_quality", {})
                assert "has_negative_ibnr" in dq
                assert "has_missing_premium" in dq
                assert "has_sparse_triangle" in dq
                assert "missing_incurred_data" in dq
                
                diag = m.get("diagnostics", {})
                assert "negative_ibnr_ays" in diag
                assert "negative_ibnr_count" in diag
                assert "reported_fallback_used" in diag
    finally:
        agent_workflow.run_agent = orig_run_agent
