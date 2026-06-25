import os
import sys
import json
import asyncio

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import agent_workflow
from reserving.schemas.reserving import ExecuteRequest, MethodConfig
from reserving.services.reserving_engine import ReservingEngine

def main():
    # Load test data
    csv_path = r"c:\Reserving-using-Agentic-AI\data\df_masked.csv"
    with open(csv_path, "r") as f:
        csv_text = f.read()

    import numpy as np
    
    # Create session with 10 years of development
    session_id = agent_workflow.create_session(csv_text, 10)
    session = agent_workflow.SESSION_STORE[session_id]
    session['selected_entities'] = ['13587']
    
    agent_workflow.ingest_csv(session_id)
    agent_workflow.build_loss_triangle(session_id)
    agent_workflow.calculate_ldfs(session_id)
    
    # Mock LLM agent
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
    
    print("COMPARISON: CL_PAID FOR GRCODE 13587")
    print(f"{'Accident Year':<15} | {'Paid':<12} | {'Reported':<12} | {'Ultimate (Clamped)':<20} | {'Ultimate (Unclamped)':<20} | {'IBNR (Clamped)':<15} | {'IBNR (Unclamped)':<15}")
    print("-" * 115)
    
    results_clamped = cl_paid_clamped["results"]
    results_unclamped = cl_paid_unclamped["results"]
    
    for rc, ru in zip(results_clamped, results_unclamped):
        ay = rc["ay"]
        paid = rc["paid"]
        rep = rc["reported"]
        ult_c = rc["ultimate"]
        ult_u = ru["ultimate"]
        ibnr_c = rc["ibnr"]
        ibnr_u = ru["ibnr"]
        print(f"{ay:<15} | {paid:<12,.0f} | {rep:<12,.0f} | {ult_c:<20,.2f} | {ult_u:<20,.2f} | {ibnr_c:<15,.2f} | {ibnr_u:<15,.2f}")

main()
