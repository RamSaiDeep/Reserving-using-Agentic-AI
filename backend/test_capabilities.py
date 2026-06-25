import sys
import os
import json

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import agent_workflow
from models.tools import compute_suggested_elr, compute_mature_accident_years
import copy
from main import ExecuteRequest, MethodConfig, execute_all_models

# Load test data
with open("../data/df_masked.csv", "r") as f:
    csv_text = f.read()

# 1. Setup Session
session_id = agent_workflow.create_session(csv_text, 5)
agent_workflow.ingest_csv(session_id)
agent_workflow.build_loss_triangle(session_id)
agent_workflow.calculate_ldfs(session_id)

session = agent_workflow.SESSION_STORE[session_id]
t = session['triangle']

print("==========================================================")
print("TEST 1: ACTUARIAL ELR & MATURE YEARS FORMULA CALIBRATION")
print("==========================================================")
print("Premiums mapping length (accident years):", len(t.premiums))
# We expect aggregated premium sum for 1988 to be ~913,636 (from test_prem_agg)
print("Aggregated Premium for 1988:", t.premiums.get(1988))
assert t.premiums.get(1988) == 913636, f"Expected 913636, got {t.premiums.get(1988)}"

# Test configurable mature years CDF threshold
m_years_105 = compute_mature_accident_years(t, 1.05)["mature_years"]
m_years_110 = compute_mature_accident_years(t, 1.10)["mature_years"]
print("Mature years (CDF <= 1.05):", m_years_105)
print("Mature years (CDF <= 1.10):", m_years_110)
assert len(m_years_110) >= len(m_years_105), "CDF 1.10 should include at least as many years as CDF 1.05"

# Calculate suggested ELRs using the proper formula
elr_paid_105 = compute_suggested_elr(t, "paid", 1.05)
elr_paid_110 = compute_suggested_elr(t, "paid", 1.10)
print(f"Suggested Paid ELR (CDF <= 1.05): {elr_paid_105}%")
print(f"Suggested Paid ELR (CDF <= 1.10): {elr_paid_110}%")

# We expect ELR to be ~68% instead of the old max-premium based ~220%
assert 60.0 <= elr_paid_105 <= 75.0, f"ELR suggestion out of range: {elr_paid_105}%"
print("Actuarial calibration: SUCCESS!")

print("\n==========================================================")
print("TEST 2: EXECUTION CAPABILITIES & RESULT_ID VERIFICATION")
print("==========================================================")

# Execute request with capabilities setup
req = ExecuteRequest(
    session_id=session_id,
    configs={
        "CL": MethodConfig(enabled=True, run_paid=True, run_incurred=True),
        "BF": MethodConfig(enabled=True, run_paid=True, run_incurred=False),
        "CO": MethodConfig(enabled=True, run_paid=True, run_incurred=True), # CO ignores source and runs both_required
    },
    paid_ldfs=[1.0] * len(t.dev_ages),
    incurred_ldfs=[1.0] * len(t.dev_ages),
    mature_cdf_threshold=1.05,
    api_key="mock-key",
    model_name="mock-model"
)

# Mock run_agent to avoid slow/unauthenticated network calls during unit test
agent_workflow.run_agent = lambda *args, **kwargs: '{"recommended_method": "CL_PAID", "confidence": "High", "reasoning": ["Mock test reasoning"]}'

class MockApp:
    def __init__(self):
        pass

# Call the endpoint handler directly (for PAID source)
import asyncio
req_paid = copy.deepcopy(req)
req_paid.data_source = "paid"
res_paid = asyncio.run(execute_all_models(req_paid))
assert res_paid.get("success") == True, f"Failed PAID execution: {res_paid}"

methods_paid = res_paid.get("methods", [])
print(f"Total PAID methods executed: {len(methods_paid)}")
for m in methods_paid:
    print(f" - Result ID: {m.get('result_id')} | Method: {m.get('method')} | Source: {m.get('source')} | Status: {m.get('status')}")

result_ids_paid = [m.get("result_id") for m in methods_paid]
print("Executed PAID Result IDs:", result_ids_paid)

assert "CL_PAID" in result_ids_paid, "CL Paid should have run"
assert "BF_PAID" in result_ids_paid, "BF Paid should have run"
assert "CO" in result_ids_paid, "Case Outstanding should have run as CO"

# Call the endpoint handler directly (for INCURRED source)
req_inc = copy.deepcopy(req)
req_inc.data_source = "incurred"
res_inc = asyncio.run(execute_all_models(req_inc))
assert res_inc.get("success") == True, f"Failed INCURRED execution: {res_inc}"

methods_inc = res_inc.get("methods", [])
print(f"Total INCURRED methods executed: {len(methods_inc)}")
for m in methods_inc:
    print(f" - Result ID: {m.get('result_id')} | Method: {m.get('method')} | Source: {m.get('source')} | Status: {m.get('status')}")

result_ids_inc = [m.get("result_id") for m in methods_inc]
print("Executed INCURRED Result IDs:", result_ids_inc)

assert "CL_INCURRED" in result_ids_inc, "CL Incurred should have run"
assert "BF_INCURRED" in result_ids_inc, "BF Incurred should have run under Incurred source (even if disabled per-method BF config, wait, in config it is run_paid=True, run_incurred=False. Since run_incurred is false in config, BF Incurred should be disabled.)"
# Let's verify BF is indeed disabled in Incurred run because run_incurred is False
bf_res = next((m for m in methods_inc if m.get("result_id") == "BF_INCURRED"), None)
assert bf_res is not None and bf_res.get("status") == "disabled", "BF Incurred should be disabled because run_incurred=False in config"

# Assert standard reserving output contract (Version 2.0)
all_methods = methods_paid + methods_inc
for m in all_methods:
    if m.get("status") == "success":
        assert m.get("version") == "2.0", f"Expected version 2.0, got {m.get('version')}"
        assert m.get("valuation_date") == "1997-12-31", f"Expected valuation date 1997-12-31, got {m.get('valuation_date')}"
        assert m.get("source_basis") in ["paid", "incurred", "both"], f"Invalid source_basis: {m.get('source_basis')}"
        assert isinstance(m.get("paid"), float), "paid should be float"
        assert isinstance(m.get("case_outstanding"), float), "case_outstanding should be float"
        assert isinstance(m.get("reported"), float), "reported should be float"
        assert isinstance(m.get("ultimate"), float), "ultimate should be float"
        assert isinstance(m.get("ibnr"), float), "ibnr should be float"
        assert isinstance(m.get("reserve"), float), "reserve should be float"
        assert isinstance(m.get("future_paid"), float), "future_paid should be float"
        assert m.get("future_paid") == m.get("reserve"), "future_paid should equal reserve"
        assert isinstance(m.get("paid_maturity"), float), "paid_maturity should be float"
        assert isinstance(m.get("reported_maturity"), float), "reported_maturity should be float"
        assert isinstance(m.get("ultimate_by_ay"), dict), "ultimate_by_ay should be dict"
        assert isinstance(m.get("ibnr_by_ay"), dict), "ibnr_by_ay should be dict"
        assert isinstance(m.get("reserve_by_ay"), dict), "reserve_by_ay should be dict"
        
        # Data Quality Flags
        dq = m.get("data_quality", {})
        assert "has_negative_ibnr" in dq, "data_quality should have has_negative_ibnr"
        assert "has_missing_premium" in dq, "data_quality should have has_missing_premium"
        assert "has_sparse_triangle" in dq, "data_quality should have has_sparse_triangle"
        assert "missing_incurred_data" in dq, "data_quality should have missing_incurred_data"
        
        # Diagnostics
        diag = m.get("diagnostics", {})
        assert "negative_ibnr_ays" in diag, "diagnostics should have negative_ibnr_ays"
        assert "negative_ibnr_count" in diag, "diagnostics should have negative_ibnr_count"
        assert "reported_fallback_used" in diag, "diagnostics should have reported_fallback_used"

print("Capabilities execution: SUCCESS!")
