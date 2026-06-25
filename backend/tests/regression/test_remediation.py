import sys
import os
import pytest
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import agent_workflow
from main import ExecuteRequest, MethodConfig, execute_all_models

@pytest.mark.regression
def test_actuarial_compliance_and_identities(sample_csv_text):
    # Setup Session
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
            "BF": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
            "CC": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
            "ELR": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
            "CO": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
            "BK": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
            "CLK": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
            "MCL": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
            "FS": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
        },
        paid_ldfs=[1.0] * len(t.dev_ages),
        incurred_ldfs=[1.0] * len(t.dev_ages),
        mature_cdf_threshold=1.05,
        api_key="mock-key",
        model_name="mock-model"
    )
    
    # Mock LLM calls
    orig_run_agent = agent_workflow.run_agent
    agent_workflow.run_agent = lambda *args, **kwargs: '{"recommended_method": "CL_PAID", "confidence": "High", "reasoning": ["Mock test reasoning"]}'
    
    try:
        # Run all methods
        res = asyncio.run(execute_all_models(req))
        assert res.get("success") == True, f"Failed execution: {res}"
        
        methods_results = res.get("methods", [])
        assert len(methods_results) > 0
        
        success_count = 0
        for m in methods_results:
            if m.get("status") != "success":
                continue
                
            tot_paid = m.get("paid")
            tot_case = m.get("case_outstanding")
            tot_reported = m.get("reported")
            tot_ultimate = m.get("ultimate")
            tot_ibnr = m.get("ibnr")
            tot_reserve = m.get("reserve")
            
            # 1. Reported = Paid + Case
            assert abs(tot_reported - (tot_paid + tot_case)) < 1.0, f"Identity fail: Reported ({tot_reported}) != Paid ({tot_paid}) + Case ({tot_case})"
            
            # 2. Reserve = Ultimate - Paid
            assert abs(tot_reserve - (tot_ultimate - tot_paid)) < 1.0, f"Identity fail: Reserve ({tot_reserve}) != Ultimate ({tot_ultimate}) - Paid ({tot_paid})"
            
            # 3. Reserve = Case + IBNR
            assert abs(tot_reserve - (tot_case + tot_ibnr)) < 1.0, f"Identity fail: Reserve ({tot_reserve}) != Case ({tot_case}) + IBNR ({tot_ibnr})"
            
            # 4. Ultimate >= Reported / Non-negative IBNR
            negative_ibnr_count = m.get("diagnostics", {}).get("negative_ibnr_count", 0)
            assert negative_ibnr_count == 0, f"Method {m.get('result_id')} has negative IBNR accident years!"
            
            # 5. Stochastic Uncertainty metrics check
            method_code = m.get("method_code")
            if method_code in ['MCL', 'CLK']:
                cv = m.get("cv", 0.0)
                se = m.get("diagnostics", {}).get("std_error", 0.0)
                if tot_ibnr > 0:
                    assert cv > 0.0, f"Method {m.get('result_id')} must have non-zero CV!"
                assert se > 0.0, f"Method {m.get('result_id')} must have non-zero standard error!"
                
            # Check individual accident year results
            for ay_res in m.get("results", []):
                ay = ay_res["ay"]
                p_ay = ay_res["paid"]
                c_ay = ay_res["case_outstanding"]
                r_ay = ay_res["reported"]
                u_ay = ay_res["ultimate"]
                i_ay = ay_res["ibnr"]
                res_ay = ay_res["reserve"]
                
                # Decompositions per AY
                assert abs(r_ay - (p_ay + c_ay)) < 1.0, f"AY {ay} reported mismatch"
                assert abs(res_ay - (u_ay - p_ay)) < 1.0, f"AY {ay} reserve mismatch"
                assert abs(res_ay - (c_ay + i_ay)) < 1.0, f"AY {ay} IBNR decomposition mismatch"
                assert i_ay >= 0.0, f"AY {ay} has negative IBNR: {i_ay}"
                
            success_count += 1
            
        assert success_count > 0, "No methods completed successfully!"
    finally:
        agent_workflow.run_agent = orig_run_agent
