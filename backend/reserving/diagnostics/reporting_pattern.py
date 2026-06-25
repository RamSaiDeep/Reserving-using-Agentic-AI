"""
reporting_pattern.py — Reporting Pattern Diagnostics
Fits parametric development growth curves and analyzes reporting consistency.
"""
import numpy as np

def analyze(triangle):
    """
    Fits Log-Logistic, Weibull, and Exponential curves to cumulative development progression.
    Computes R2, RMSE, and MAE.
    Returns best fitting curve, consistency assessment, and accident year deviations.
    """
    dev_ages = triangle.dev_ages
    ays = triangle.accident_years
    
    # 1. Compute cumulative development factors (CDFs) and actual ratios G(t)
    ldfs_raw = triangle.compute_ldfs()
    ldfs_list = [(r['volumeWeighted'] if r['volumeWeighted'] is not None else 1.0) for r in ldfs_raw[:-1]] + [1.0]
    cdfs = triangle.compute_cdfs(ldfs_list)
    
    # G(t) is 1 / CDF(t), representing percentage developed (0 to 1)
    g_actual = []
    t_points = []
    for j, cdf in enumerate(cdfs):
        if cdf and cdf > 0:
            g = 1.0 / cdf
            g_actual.append(g)
            t_points.append(dev_ages[j])
            
    n_points = len(g_actual)
    
    # If we have too few points to fit, return early with defaults
    if n_points < 3:
        return {
            "best_fit_curve": "None",
            "fit_metrics": {"r2": 1.0, "rmse": 0.0, "mae": 0.0},
            "curves": {},
            "reporting_consistency": "Consistent",
            "accident_year_fits": [{"ay": ay, "rmse": 0.0, "mae": 0.0, "is_deviating": False} for ay in ays],
            "significant_deviations": [],
            "g_actual": g_actual,
            "g_fitted": g_actual
        }
        
    # Helper to calculate goodness of fit
    def compute_gof(actual, fitted):
        actual = np.array(actual)
        fitted = np.array(fitted)
        sse = np.sum((actual - fitted) ** 2)
        mae = np.mean(np.abs(actual - fitted))
        rmse = np.sqrt(sse / len(actual))
        mean_actual = np.mean(actual)
        sst = np.sum((actual - mean_actual) ** 2)
        r2 = 1.0 - (sse / sst) if sst > 0 else 1.0
        return max(0.0, min(1.0, r2)), float(rmse), float(mae)

    # 2. Fit curves
    curves = {}
    
    # Prepare data for regression (clamp G to avoid log of 0 or 1)
    g_clamped = np.clip(g_actual, 0.0001, 0.9999)
    t_arr = np.array(t_points, dtype=float)
    ln_t = np.log(t_arr)
    
    # A. Log-Logistic Fit: G(t) = t^b / (a + t^b) => ln(G/(1-G)) = b*ln(t) - ln(a)
    try:
        y_ll = np.log(g_clamped / (1.0 - g_clamped))
        b_ll, intercept_ll = np.polyfit(ln_t, y_ll, 1)
        a_ll = np.exp(-intercept_ll)
        # Handle stability
        b_ll = max(0.01, b_ll)
        a_ll = max(0.01, a_ll)
        g_fitted_ll = t_arr**b_ll / (a_ll + t_arr**b_ll)
        r2_ll, rmse_ll, mae_ll = compute_gof(g_actual, g_fitted_ll)
        curves["loglogistic"] = {
            "r2": r2_ll, "rmse": rmse_ll, "mae": mae_ll, 
            "fitted": list(g_fitted_ll), "params": {"a": float(a_ll), "b": float(b_ll)}
        }
    except Exception:
        pass
        
    # B. Weibull Fit: G(t) = 1 - exp(-a * t^b) => ln(-ln(1-G)) = ln(a) + b*ln(t)
    try:
        y_wb = np.log(-np.log(1.0 - g_clamped))
        b_wb, intercept_wb = np.polyfit(ln_t, y_wb, 1)
        a_wb = np.exp(intercept_wb)
        b_wb = max(0.01, b_wb)
        a_wb = max(0.01, a_wb)
        g_fitted_wb = 1.0 - np.exp(-a_wb * (t_arr**b_wb))
        r2_wb, rmse_wb, mae_wb = compute_gof(g_actual, g_fitted_wb)
        curves["weibull"] = {
            "r2": r2_wb, "rmse": rmse_wb, "mae": mae_wb, 
            "fitted": list(g_fitted_wb), "params": {"a": float(a_wb), "b": float(b_wb)}
        }
    except Exception:
        pass
        
    # C. Exponential Fit: G(t) = 1 - exp(-(a * t + c)) => ln(1-G) = -a * t - c
    try:
        y_exp = np.log(1.0 - g_clamped)
        neg_a_exp, neg_c_exp = np.polyfit(t_arr, y_exp, 1)
        a_exp = -neg_a_exp
        c_exp = -neg_c_exp
        a_exp = max(1e-6, a_exp)
        g_fitted_exp = 1.0 - np.exp(-(a_exp * t_arr + c_exp))
        g_fitted_exp = np.clip(g_fitted_exp, 0.0, 1.0)
        r2_exp, rmse_exp, mae_exp = compute_gof(g_actual, g_fitted_exp)
        curves["exponential"] = {
            "r2": r2_exp, "rmse": rmse_exp, "mae": mae_exp, 
            "fitted": list(g_fitted_exp), "params": {"a": float(a_exp), "c": float(c_exp)}
        }
    except Exception:
        pass

    # 3. Determine best fitting curve
    best_curve = "None"
    best_r2 = -1.0
    best_metrics = {"r2": 0.0, "rmse": 999.0, "mae": 999.0}
    
    for name, c_data in curves.items():
        if c_data["r2"] > best_r2:
            best_r2 = c_data["r2"]
            best_curve = name
            best_metrics = {"r2": c_data["r2"], "rmse": c_data["rmse"], "mae": c_data["mae"]}
            
    # If no curve fit successfully, use raw or fallback
    if best_curve == "None":
        best_curve = "loglogistic"
        g_fitted_best = np.array(g_actual)
    else:
        g_fitted_best = np.array(curves[best_curve]["fitted"])

    # 4. Analyze individual accident years
    accident_year_fits = []
    significant_deviations = []
    
    for i, ay in enumerate(ays):
        row = triangle.matrix[i]
        actual_vals = []
        expected_vals = []
        
        # Get latest value and its index to compute Chain Ladder ultimate
        latest_idx = next((j for j, v in reversed(list(enumerate(row))) if v is not None and not np.isnan(v)), None)
        if latest_idx is None:
            accident_year_fits.append({"ay": ay, "rmse": 0.0, "mae": 0.0, "is_deviating": False})
            continue
            
        latest_val = row[latest_idx]
        cdf_latest = cdfs[latest_idx] if latest_idx < len(cdfs) else 1.0
        ultimate = latest_val * cdf_latest
        
        if ultimate <= 0:
            accident_year_fits.append({"ay": ay, "rmse": 0.0, "mae": 0.0, "is_deviating": False})
            continue
            
        for j, val in enumerate(row):
            if val is not None and not np.isnan(val) and j < len(g_fitted_best):
                actual_vals.append(val / ultimate)
                expected_vals.append(g_fitted_best[j])
                
        if len(actual_vals) > 0:
            actual_vals = np.array(actual_vals)
            expected_vals = np.array(expected_vals)
            sse_ay = np.sum((actual_vals - expected_vals) ** 2)
            mae_ay = np.mean(np.abs(actual_vals - expected_vals))
            rmse_ay = np.sqrt(sse_ay / len(actual_vals))
            
            is_deviating = bool(rmse_ay > 0.05)
            if is_deviating:
                significant_deviations.append(ay)
                
            accident_year_fits.append({
                "ay": ay,
                "rmse": round(float(rmse_ay), 4),
                "mae": round(float(mae_ay), 4),
                "is_deviating": is_deviating
            })
        else:
            accident_year_fits.append({"ay": ay, "rmse": 0.0, "mae": 0.0, "is_deviating": False})

    # 5. Assess reporting consistency
    valid_rmses = [f["rmse"] for f in accident_year_fits if f["rmse"] > 0]
    avg_rmse = np.mean(valid_rmses) if valid_rmses else 0.0
    
    if avg_rmse < 0.02:
        consistency = "Highly Consistent"
    elif avg_rmse < 0.05:
        consistency = "Consistent"
    elif avg_rmse < 0.10:
        consistency = "Moderately Consistent"
    else:
        consistency = "Inconsistent"
        
    return {
        "best_fit_curve": best_curve,
        "fit_metrics": best_metrics,
        "curves": {name: {"r2": c["r2"], "rmse": c["rmse"], "mae": c["mae"]} for name, c in curves.items()},
        "reporting_consistency": consistency,
        "accident_year_fits": accident_year_fits,
        "significant_deviations": significant_deviations,
        "g_actual": [round(float(v), 4) for v in g_actual],
        "g_fitted": [round(float(v), 4) for v in g_fitted_best]
    }
