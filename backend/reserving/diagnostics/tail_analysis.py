"""
tail_analysis.py — Tail Factor Diagnostics
Evaluates tail factor sensitivity and materiality of tail uncertainty.
"""
import numpy as np

def analyze(triangle, selected_tail=None):
    """
    Computes ultimate claims and IBNR under No Tail, Selected Tail, and High Tail scenarios.
    Calculates percentage changes and materiality of tail uncertainty.
    Returns structured metrics.
    """
    ldfs_raw = triangle.compute_ldfs()
    ldfs_list = [(r['volumeWeighted'] if r['volumeWeighted'] is not None else 1.0) for r in ldfs_raw[:-1]] + [1.0]
    
    # If selected_tail is not provided, extract it from raw LDF tail or use fallback
    if selected_tail is None:
        selected_tail = float(ldfs_raw[-1]['volumeWeighted'] if ldfs_raw else 1.0)
        
    # Standardize selected tail to be at least 1.0
    selected_tail = max(1.0, selected_tail)
    
    # Define scenarios
    t_no_tail = 1.0
    t_selected = selected_tail
    t_high = max(selected_tail + 0.05, 1.0 + (selected_tail - 1.0) * 1.5)
    
    # Helper to run Chain Ladder on matrix with a specific tail factor
    def run_chain_ladder_scenario(tail_factor):
        scenario_ldfs = list(ldfs_list)
        scenario_ldfs[-1] = tail_factor
        
        cdfs = triangle.compute_cdfs(scenario_ldfs)
        diag = triangle.get_latest_diagonal()
        
        inc_diag = []
        if hasattr(triangle, 'incurred_matrix') and triangle.incurred_matrix:
            for row in triangle.incurred_matrix:
                val = next((v for v in reversed(row) if v is not None and not np.isnan(v)), 0.0)
                inc_diag.append(val)
        else:
            inc_diag = list(diag)
            
        tot_ult = 0.0
        tot_ibnr = 0.0
        tot_paid = 0.0
        
        for i, val in enumerate(diag):
            paid = val or 0.0
            cdf = cdfs[i] if i < len(cdfs) else 1.0
            ult = paid * cdf
            
            # Clamp to incurred diagonal to avoid negative IBNR
            inc = inc_diag[i] if i < len(inc_diag) else paid
            if ult < inc:
                ult = inc
                
            ibnr = max(0.0, ult - inc)
            
            tot_ult += ult
            tot_ibnr += ibnr
            tot_paid += paid
            
        return float(tot_ult), float(tot_ibnr), float(tot_paid)

    ult_no_tail, ibnr_no_tail, _ = run_chain_ladder_scenario(t_no_tail)
    ult_selected, ibnr_selected, _ = run_chain_ladder_scenario(t_selected)
    ult_high, ibnr_high, _ = run_chain_ladder_scenario(t_high)
    
    # Calculate sensitivities
    sensitivity_high_vs_selected_pct = 0.0
    if ult_selected > 0:
        sensitivity_high_vs_selected_pct = ((ult_high - ult_selected) / ult_selected) * 100
        
    sensitivity_selected_vs_no_tail_pct = 0.0
    if ult_no_tail > 0:
        sensitivity_selected_vs_no_tail_pct = ((ult_selected - ult_no_tail) / ult_no_tail) * 100
        
    # Materiality determination
    if sensitivity_high_vs_selected_pct > 5.0 or sensitivity_selected_vs_no_tail_pct > 10.0:
        materiality = "High"
    elif sensitivity_high_vs_selected_pct > 2.0 or sensitivity_selected_vs_no_tail_pct > 4.0:
        materiality = "Moderate"
    else:
        materiality = "Low"
        
    return {
        "selected_tail": round(float(selected_tail), 4),
        "high_tail": round(float(t_high), 4),
        "scenarios": {
            "no_tail": {"ultimate": round(ult_no_tail, 0), "ibnr": round(ibnr_no_tail, 0)},
            "selected": {"ultimate": round(ult_selected, 0), "ibnr": round(ibnr_selected, 0)},
            "high": {"ultimate": round(ult_high, 0), "ibnr": round(ibnr_high, 0)}
        },
        "sensitivity": {
            "high_vs_selected_pct": round(sensitivity_high_vs_selected_pct, 2),
            "selected_vs_no_tail_pct": round(sensitivity_selected_vs_no_tail_pct, 2)
        },
        "tail_uncertainty_materiality": materiality
    }
