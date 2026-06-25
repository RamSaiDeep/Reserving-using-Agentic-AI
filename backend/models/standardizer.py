import numpy as np
from typing import Dict, Any, List, Optional
from models.triangle import Triangle

def standardize_method_output(
    code: str,
    label: str,
    source_val: str,
    t_eval: Triangle,
    model,
    configs: Dict[str, Any]
) -> dict:
    # 1. Fetch latest diagonal values for paid and incurred matrices
    ays = t_eval.accident_years
    paid_diag = []
    incurred_diag = []
    
    missing_incurred_data = False
    reported_fallback_used = False
    
    # Check if incurred_matrix is missing, empty, or all None
    has_incurred = True
    if not hasattr(t_eval, 'incurred_matrix') or t_eval.incurred_matrix is None or len(t_eval.incurred_matrix) == 0:
        has_incurred = False
    else:
        # Check if all cells are None/NaN
        all_null = True
        for row in t_eval.incurred_matrix:
            for val in row:
                if val is not None and not np.isnan(val):
                    all_null = False
                    break
        if all_null:
            has_incurred = False
            
    if not has_incurred:
        missing_incurred_data = True
        reported_fallback_used = True

    for i, ay in enumerate(ays):
        paid_row = t_eval.matrix[i]
        
        last_paid = next((v for v in reversed(paid_row) if v is not None and not np.isnan(v)), 0.0)
        paid_diag.append(last_paid)
        
        if has_incurred:
            inc_row = t_eval.incurred_matrix[i]
            last_inc = next((v for v in reversed(inc_row) if v is not None and not np.isnan(v)), last_paid)
            incurred_diag.append(last_inc)
        else:
            incurred_diag.append(last_paid)

    # 2. Extract results by AY
    model_results_by_ay = {r['ay']: r for r in model.results}
    
    standardized_ay_results = []
    ultimate_by_ay = {}
    ibnr_by_ay = {}
    reserve_by_ay = {}
    
    negative_ibnr_ays = []
    
    for i, ay in enumerate(ays):
        p_ay = paid_diag[i]
        r_ay = incurred_diag[i]
        c_ay = max(0.0, r_ay - p_ay)
        
        m_res = model_results_by_ay.get(ay, {})
        u_ay = m_res.get('ultimate', p_ay)
        
        # Calculate IBNR = Ultimate - Reported (no clamping!)
        ibnr_ay = u_ay - r_ay
        if ibnr_ay < 0:
            negative_ibnr_ays.append(int(ay))
            
        # Total Reserve = Ultimate - Paid
        reserve_ay = u_ay - p_ay
        
        # Maturity calculations
        paid_mat_ay = p_ay / u_ay if u_ay > 0 else 1.0
        reported_mat_ay = r_ay / u_ay if u_ay > 0 else 1.0
        
        ultimate_by_ay[str(ay)] = float(u_ay)
        ibnr_by_ay[str(ay)] = float(ibnr_ay)
        reserve_by_ay[str(ay)] = float(reserve_ay)
        
        cdf = m_res.get('cdfToUlt', 1.0)
        pct_rep = m_res.get('pctReported', 100.0)
        
        standardized_ay_results.append({
            "ay": int(ay),
            "paid": float(p_ay),
            "case_outstanding": float(c_ay),
            "reported": float(r_ay),
            "ultimate": float(u_ay),
            "ibnr": float(ibnr_ay),
            "reserve": float(reserve_ay),
            "paid_maturity": float(paid_mat_ay),
            "reported_maturity": float(reported_mat_ay),
            "cdfToUlt": float(cdf),
            "pctReported": float(pct_rep)
        })

    # 3. Aggregate totals
    tot_paid = sum(paid_diag)
    tot_reported = sum(incurred_diag)
    tot_case_os = max(0.0, tot_reported - tot_paid)
    tot_ultimate = sum(ultimate_by_ay.values())
    tot_ibnr = sum(ibnr_by_ay.values())
    tot_reserve = sum(reserve_by_ay.values())
    
    agg_paid_maturity = tot_paid / tot_ultimate if tot_ultimate > 0 else 1.0
    agg_reported_maturity = tot_reported / tot_ultimate if tot_ultimate > 0 else 1.0
    
    # 4. Method Specific Diagnostics and Assumptions
    diagnostics = {
        "negative_ibnr_ays": negative_ibnr_ays,
        "negative_ibnr_count": len(negative_ibnr_ays),
        "reported_fallback_used": reported_fallback_used
    }
    
    if code == 'MCL':
        diagnostics["process_risk"] = float(getattr(model, 'process_risk', 0.0))
        diagnostics["parameter_risk"] = float(getattr(model, 'parameter_risk', 0.0))
        diagnostics["std_error"] = float(getattr(model, 'volatility', 0.0))
    elif code == 'CLK':
        diagnostics["p_value"] = float(getattr(model, 'p_value', 0.05))
        diagnostics["covariance_matrix"] = getattr(model, 'cov_matrix', [])
    elif code == 'ELR':
        diagnostics["mature_years"] = [int(y) for y in model.params.get('matureYears', [])]
        
    assumptions = {
        "source": source_val,
        "tail_factor": float(model.ldfs[-1]) if hasattr(model, 'ldfs') and model.ldfs else 1.0
    }
    
    cfg = configs.get(code) if configs else None
    if cfg:
        # Check standard properties of MethodConfig model
        if hasattr(cfg, 'aprioriLossRatio') and cfg.aprioriLossRatio is not None:
            assumptions["apriori_loss_ratio"] = float(cfg.aprioriLossRatio)
        if hasattr(cfg, 'iterations') and cfg.iterations is not None:
            assumptions["iterations"] = int(cfg.iterations)
        if hasattr(cfg, 'decay') and cfg.decay is not None:
            assumptions["decay"] = float(cfg.decay)

    # 5. Data Quality Flags
    # Missing premium check
    has_missing_premium = False
    if not t_eval.premiums:
        has_missing_premium = True
    else:
        for ay in ays:
            if ay not in t_eval.premiums or t_eval.premiums[ay] is None or t_eval.premiums[ay] <= 0:
                has_missing_premium = True
                break
                
    # Sparse triangle check (e.g. if more than 30% of triangle cells are null/NaN)
    has_sparse_triangle = False
    total_cells = len(ays) * len(t_eval.dev_ages)
    null_cells = 0
    for row in t_eval.matrix:
        for val in row:
            if val is None or (isinstance(val, float) and np.isnan(val)):
                null_cells += 1
    if total_cells > 0 and (null_cells / total_cells) > 0.3:
        has_sparse_triangle = True

    data_quality = {
        "has_negative_ibnr": len(negative_ibnr_ays) > 0,
        "has_missing_premium": has_missing_premium,
        "has_sparse_triangle": has_sparse_triangle,
        "missing_incurred_data": missing_incurred_data
    }

    # 6. Format Valuation Date (e.g., "1997-12-31")
    val_year = t_eval.valuation_year if t_eval.valuation_year is not None else int(max(ays))
    valuation_date = f"{val_year}-12-31"

    # Calculate Loss Ratio
    tot_premium = sum(t_eval.premiums.values()) if t_eval.premiums else 0.0
    loss_ratio = tot_ultimate / tot_premium if tot_premium > 0 else 0.0

    return {
        "version": "2.0",
        "valuation_date": valuation_date,
        
        "method_code": code,
        "method_name": label,
        "source_basis": source_val,
        
        "paid": float(tot_paid),
        "case_outstanding": float(tot_case_os),
        "reported": float(tot_reported),
        
        "ultimate": float(tot_ultimate),
        "ibnr": float(tot_ibnr),
        "reserve": float(tot_reserve),
        "future_paid": float(tot_reserve),
        
        "paid_maturity": float(agg_paid_maturity),
        "reported_maturity": float(agg_reported_maturity),
        
        "ultimate_by_ay": {str(k): float(v) for k, v in ultimate_by_ay.items()},
        "ibnr_by_ay": {str(k): float(v) for k, v in ibnr_by_ay.items()},
        "reserve_by_ay": {str(k): float(v) for k, v in reserve_by_ay.items()},
        
        "results": standardized_ay_results,
        
        "diagnostics": diagnostics,
        "data_quality": data_quality,
        "assumptions": assumptions,
        
        # Backward compatibility properties for current Next.js charts/tables
        "result_id": f"{code}_{source_val.upper()}" if source_val != "both" else code,
        "name": f"{label} ({source_val.capitalize()})" if source_val != "both" else label,
        "code": f"{code}_{source_val.upper()}" if source_val != "both" else code,
        "status": "success",
        "loss_ratio": float(loss_ratio),
        "cv": float(diagnostics.get("std_error", 0.0) / tot_ibnr if tot_ibnr > 0 else 0.0),
        "reserve_to_case_ratio": float(tot_reserve / tot_case_os if tot_case_os > 0 else 0.0),
        "maturity_score": float(agg_paid_maturity)
    }
