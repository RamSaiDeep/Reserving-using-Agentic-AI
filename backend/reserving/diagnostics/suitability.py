"""
suitability.py — Reserving Method Suitability Assessment
Computes deterministic suitability scores (0-100) for each reserving method based on diagnostics.
"""
import numpy as np

def analyze(triangle, diag_results):
    """
    Computes suitability scores and ranks reserving methods.
    Accounts for premium availability, stability, outliers, trends, tail uncertainty, and pattern fits.
    Returns structured suitability scores.
    """
    # Initialize baseline scores
    methods = ["CL", "MCL", "BF", "CC", "BK", "CO", "CLK", "ELR"]
    scores = {m: 80 for m in methods}
    pros = {m: [] for m in methods}
    cons = {m: [] for m in methods}
    
    has_premium = bool(triangle.premiums)
    
    # 1. Premium Availability check
    if not has_premium:
        for m in ["BF", "CC", "BK", "ELR"]:
            scores[m] = 0
            cons[m].append("Requires Premium data which is missing.")
            
    # 2. LDF Stability check
    ldf_stab = diag_results.get("ldf_stability", {})
    avg_cov = ldf_stab.get("average_cov", 0.0)
    unstable_periods = ldf_stab.get("unstable_periods", [])
    
    if avg_cov > 0.0:
        # Penalties based on average CoV
        cl_penalty = min(40.0, avg_cov * 150.0)
        mcl_penalty = min(45.0, avg_cov * 180.0)
        bk_penalty = min(25.0, avg_cov * 100.0)
        clk_penalty = min(20.0, avg_cov * 80.0)
        bf_penalty = min(15.0, avg_cov * 50.0)
        
        # Apply penalties if premium is available (or CL if not)
        scores["CL"] = max(0, scores["CL"] - cl_penalty)
        scores["MCL"] = max(0, scores["MCL"] - mcl_penalty)
        if has_premium:
            scores["BK"] = max(0, scores["BK"] - bk_penalty)
            scores["CLK"] = max(0, scores["CLK"] - clk_penalty)
            scores["BF"] = max(0, scores["BF"] - bf_penalty)
            scores["CC"] = max(0, scores["CC"] - bf_penalty)
            
        if avg_cov < 0.05:
            scores["CL"] += 10
            scores["MCL"] += 10
            pros["CL"].append("Highly stable historical link ratios.")
            pros["MCL"].append("Highly stable historical link ratios; ideal for Mack variance estimation.")
        elif avg_cov > 0.12:
            cons["CL"].append(f"Highly volatile LDFs (avg CoV of {avg_cov:.1%}) violating Chain Ladder assumptions.")
            cons["MCL"].append(f"Highly volatile LDFs (avg CoV of {avg_cov:.1%}); standard error calculations will be wide.")
            if has_premium:
                pros["BF"].append("Bornhuetter-Ferguson expected losses stabilize volatile development.")
                pros["CC"].append("Cape Cod expected losses stabilize volatile development.")
                
    # 3. Tail Sensitivity check
    tail_diag = diag_results.get("tail_analysis", {})
    tail_sens = tail_diag.get("sensitivity", {}).get("high_vs_selected_pct", 0.0)
    materiality = tail_diag.get("tail_uncertainty_materiality", "Low")
    
    if materiality == "High":
        scores["CL"] = max(0, scores["CL"] - 15)
        scores["MCL"] = max(0, scores["MCL"] - 15)
        if has_premium:
            scores["BK"] = max(0, scores["BK"] - 10)
            scores["BF"] += 5
            scores["CC"] += 5
            scores["ELR"] += 10
            pros["ELR"].append("Unaffected by high tail development factor sensitivity.")
            cons["CL"].append(f"High tail factor sensitivity ({tail_sens:.1f}% change in ultimate).")
            cons["MCL"].append(f"High tail factor sensitivity ({tail_sens:.1f}% change in ultimate).")
    elif materiality == "Moderate":
        scores["CL"] = max(0, scores["CL"] - 5)
        scores["MCL"] = max(0, scores["MCL"] - 5)
        
    # Immature check (number of dev periods < 5)
    n_dev = len(triangle.dev_ages)
    if n_dev < 5:
        scores["CL"] = max(0, scores["CL"] - 15)
        scores["MCL"] = max(0, scores["MCL"] - 15)
        if has_premium:
            scores["BF"] += 10
            scores["CC"] += 10
            scores["BK"] += 5
            scores["ELR"] += 10
            pros["BF"].append("Immature triangle; BF anchors estimates in expected losses.")
            pros["CC"].append("Immature triangle; CC anchors estimates in expected losses.")
            cons["CL"].append("Immature triangle with very few development periods.")
            
    # 4. Outliers check
    outliers_diag = diag_results.get("outliers", {})
    cell_outliers = outliers_diag.get("cell_outliers", [])
    
    # Calculate total outlier score
    tot_out_score = sum(10.0 if o["severity"] == "Critical" else (5.0 if o["severity"] == "High" else 2.0) for o in cell_outliers)
    
    if tot_out_score > 0:
        cl_out_penalty = min(30.0, tot_out_score * 2.5)
        clk_out_penalty = min(20.0, tot_out_score * 1.5)
        bk_out_penalty = min(15.0, tot_out_score * 1.2)
        bf_out_penalty = min(10.0, tot_out_score * 0.5)
        
        scores["CL"] = max(0, scores["CL"] - cl_out_penalty)
        scores["MCL"] = max(0, scores["MCL"] - cl_out_penalty)
        scores["CLK"] = max(0, scores["CLK"] - clk_out_penalty)
        if has_premium:
            scores["BK"] = max(0, scores["BK"] - bk_out_penalty)
            scores["BF"] = max(0, scores["BF"] - bf_out_penalty)
            scores["CC"] = max(0, scores["CC"] - bf_out_penalty)
            
        if tot_out_score > 10.0:
            cons["CL"].append("Multiple severe outliers distorting development factors.")
            cons["MCL"].append("Multiple severe outliers distorting development factors.")
            if has_premium:
                pros["BF"].append("Bornhuetter-Ferguson mitigates outlier distortion through expected losses.")
                
    # 5. Calendar Year Trend check
    cal_diag = diag_results.get("calendar_effects", {})
    slope = cal_diag.get("slope", 0.0)
    trend_detected = cal_diag.get("trend_detected", False)
    
    if trend_detected:
        scores["CL"] = max(0, scores["CL"] - 25)
        scores["MCL"] = max(0, scores["MCL"] - 25)
        scores["CLK"] = max(0, scores["CLK"] - 15)
        if has_premium:
            scores["BK"] = max(0, scores["BK"] - 15)
            scores["BF"] = max(0, scores["BF"] - 10)
            scores["CC"] = max(0, scores["CC"] - 10)
        scores["CO"] = max(0, scores["CO"] - 5)
        
        direction = cal_diag.get("trend_direction", "up")
        cons["CL"].append(f"Significant calendar year {direction}ward trend violating independent-year development assumptions.")
        cons["MCL"].append(f"Significant calendar year {direction}ward trend violating independent-year development assumptions.")
        if has_premium:
            pros["BF"].append("Bornhuetter-Ferguson uses expected losses, reducing calendar year trend bias.")
            pros["CC"].append("Cape Cod uses expected losses, reducing calendar year trend bias.")
            
    # 6. Reporting Pattern Consistency check
    rep_diag = diag_results.get("reporting_pattern", {})
    avg_ay_rmse = np.mean([item["rmse"] for item in rep_diag.get("accident_year_fits", []) if item["rmse"] > 0]) if rep_diag.get("accident_year_fits") else 0.0
    curve_r2 = rep_diag.get("fit_metrics", {}).get("r2", 0.0)
    
    if avg_ay_rmse > 0.05:
        scores["CL"] = max(0, scores["CL"] - 15)
        scores["MCL"] = max(0, scores["MCL"] - 15)
        if has_premium:
            scores["BF"] += 5
            scores["CC"] += 5
            scores["ELR"] += 10
        cons["CL"].append("Inconsistent development patterns across accident years.")
        
    if curve_r2 > 0.90:
        scores["CLK"] += 15
        pros["CLK"].append(f"Excellent growth curve fit (R2 of {curve_r2:.2f}); ideal for Clark stochastic model.")
    elif curve_r2 < 0.60:
        scores["CLK"] = max(0, scores["CLK"] - 15)
        cons["CLK"].append(f"Poor growth curve fit (R2 of {curve_r2:.2f}).")
        
    # Standardize output
    scores_dict = {}
    for m in methods:
        scores_dict[m] = int(round(scores[m]))
        
    return {
        "scores": scores_dict,
        "pros": pros,
        "cons": cons
    }
