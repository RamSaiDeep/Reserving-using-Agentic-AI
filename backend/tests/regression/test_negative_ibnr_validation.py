import sys
import os
import pytest
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import agent_workflow
from reserving.schemas.reserving import ExecuteRequest, MethodConfig
from reserving.services.reserving_engine import ReservingEngine

@pytest.mark.regression
def test_negative_ibnr_clamping_control(sample_csv_text):
    # Create session with 10 years of development
    session_id = agent_workflow.create_session(sample_csv_text, 10)
    session = agent_workflow.SESSION_STORE[session_id]
    session['selected_entities'] = ['13587']
    
    agent_workflow.ingest_csv(session_id)
    agent_workflow.build_loss_triangle(session_id)
    agent_workflow.calculate_ldfs(session_id)
    
    # Mock LLM agent and restore it afterwards to prevent test pollution
    orig_recommend = agent_workflow.run_reserve_recommendation_agent
    try:
        agent_workflow.run_reserve_recommendation_agent = lambda *args, **kwargs: {"recommended_method": "CL_PAID", "confidence": "High", "reasoning": ["Mock"]}
        
        # 1. Run with allow_negative_ibnr = False
        req_clamped = ExecuteRequest(
            session_id=session_id,
            configs={
                "CL": MethodConfig(enabled=True, run_paid=True, run_incurred=True, allow_negative_ibnr=False)
            },
            api_key="mock",
            model_name="mock"
        )
        res_clamped = ReservingEngine.execute_models(req_clamped)
        cl_paid_clamped = next(m for m in res_clamped["methods"] if m["result_id"] == "CL_PAID")
        
        # 2. Run with allow_negative_ibnr = True
        req_unclamped = ExecuteRequest(
            session_id=session_id,
            configs={
                "CL": MethodConfig(enabled=True, run_paid=True, run_incurred=True, allow_negative_ibnr=True)
            },
            api_key="mock",
            model_name="mock"
        )
        res_unclamped = ReservingEngine.execute_models(req_unclamped)
        cl_paid_unclamped = next(m for m in res_unclamped["methods"] if m["result_id"] == "CL_PAID")
        
        # Check assertions
        results_clamped = cl_paid_clamped["results"]
        results_unclamped = cl_paid_unclamped["results"]
        
        assert len(results_clamped) == len(results_unclamped)
        
        has_difference = False
        for rc, ru in zip(results_clamped, results_unclamped):
            ay = rc["ay"]
            ibnr_c = rc["ibnr"]
            ibnr_u = ru["ibnr"]
            
            # Clamped IBNR must always be non-negative
            assert ibnr_c >= 0.0, f"Clamped IBNR is negative ({ibnr_c}) in accident year {ay}!"
            
            if abs(ibnr_c - ibnr_u) > 1e-4:
                has_difference = True
                # Ultimate when clamped must be equal to paid, and IBNR must be 0
                assert ibnr_c == 0.0, f"Expected clamped IBNR to be 0 when clamping applied, got {ibnr_c}"
                assert rc["ultimate"] == rc["reported"], f"Expected ultimate to equal reported when clamped"
                assert ibnr_u < 0.0, f"Expected unclamped IBNR to be negative when there is a difference, got {ibnr_u}"
                
        # Ensure that our test data actually triggered clamping for at least one year
        # (this confirms the regression test is actively testing clamping)
        assert has_difference, "Test did not trigger any negative IBNR clamping difference! Check test data."
        
    finally:
        agent_workflow.run_reserve_recommendation_agent = orig_recommend
