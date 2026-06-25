"""
trace_generator.py — Decision Trace Generator
Generates an explainable decision trace deterministically from diagnostics and the selected method.
"""
def generate_decision_trace(diag_results, selected_method):
    """
    Constructs a list of trace strings describing the decision logic.
    Grounds agent decisions in deterministic evidence.
    """
    trace = []
    
    # 1. Volatility evidence
    ldf_stab = diag_results.get("ldf_stability", {})
    average_cov = ldf_stab.get("average_cov", 0.0)
    if average_cov > 0.12:
        trace.append("LDF CoV exceeded stability threshold")
        
    # 2. Calendar Year Trend evidence
    cal_effects = diag_results.get("calendar_effects", {})
    if cal_effects.get("trend_detected"):
        trace.append("Calendar year trend detected")
        
    # 3. Tail Sensitivity evidence
    tail_diag = diag_results.get("tail_analysis", {})
    if tail_diag.get("tail_uncertainty_materiality") == "High":
        trace.append("High tail factor sensitivity detected")
        
    # 4. Outliers evidence
    outliers_diag = diag_results.get("outliers", {})
    cell_outliers = outliers_diag.get("cell_outliers", [])
    tot_out_score = sum(10.0 if o["severity"] == "Critical" else (5.0 if o["severity"] == "High" else 2.0) for o in cell_outliers)
    if tot_out_score > 10.0:
        trace.append("Material development outliers detected")
        
    # 5. Reporting pattern evidence
    rep_pattern = diag_results.get("reporting_pattern", {})
    significant_deviations = rep_pattern.get("significant_deviations", [])
    if len(significant_deviations) > 0:
        trace.append("Reporting pattern deviations identified in specific accident years")
        
    # 6. Suitability reduction evidence
    suit = diag_results.get("suitability", {})
    scores = suit.get("scores", {})
    cl_score = scores.get("CL", 80)
    if cl_score < 70:
        trace.append("Chain Ladder suitability reduced")
        
    # 7. Final Selection Justification
    if selected_method == "MCL" or selected_method == "MACK":
        trace.append("Mack selected because it quantifies reserve uncertainty")
    elif selected_method == "BF":
        trace.append("Bornhuetter-Ferguson selected to stabilize volatile development")
    elif selected_method == "CC":
        trace.append("Cape Cod selected to stabilize volatile development")
    elif selected_method == "BK":
        trace.append("Benktander selected as an iterative compromise between CL and BF")
    elif selected_method == "CLK":
        trace.append("Clark Stochastic selected due to continuous growth curve fit")
    elif selected_method == "CL":
        trace.append("Chain Ladder selected due to stable historical development")
    elif selected_method == "CO":
        trace.append("Case Outstanding selected based on case reserve inventory")
    elif selected_method == "ELR":
        trace.append("Expected Loss Ratio selected as premium-based default")
    else:
        trace.append(f"{selected_method} method selected as best estimate")
        
    return trace
