"""
ldf_stability.py — LDF Stability Diagnostics
Analyzes coefficient of variation by development age and checks Chain Ladder assumptions.
"""
import numpy as np

def analyze(triangle):
    """
    Calculates LDF CoV by development age.
    Identifies unstable development periods and provides suitability indicators.
    Returns structured metrics.
    """
    ldfs_raw = triangle.compute_ldfs()
    
    # We examine all age-to-age transitions (excluding the final tail factor)
    cov_by_age = []
    unstable_periods = []
    
    for r in ldfs_raw[:-1]:
        cov = r.get('cov', 0.0)
        from_age = r['fromAge']
        to_age = r['toAge']
        
        cov_by_age.append({
            'from_age': from_age,
            'to_age': to_age,
            'cov': round(float(cov), 4),
            'n_points': r.get('n', 0)
        })
        
        # Stability threshold
        if cov > 0.12:
            unstable_periods.append({
                'from_age': from_age,
                'to_age': to_age,
                'cov': round(float(cov), 4)
            })
            
    # Calculate average CoV across transitions
    valid_covs = [r['cov'] for r in cov_by_age if r['n_points'] > 1]
    average_cov = np.mean(valid_covs) if valid_covs else 0.0
    
    # Determine suitability indicators
    if average_cov < 0.05:
        cl_suitable_indicator = "Highly Stable"
        cl_assumptions_reasonable = True
    elif average_cov <= 0.12:
        cl_suitable_indicator = "Moderate Volatility"
        cl_assumptions_reasonable = True
    else:
        cl_suitable_indicator = "Unstable"
        cl_assumptions_reasonable = False
        
    return {
        "cov_by_age": cov_by_age,
        "average_cov": round(float(average_cov), 4),
        "unstable_periods": unstable_periods,
        "cl_suitable_indicator": cl_suitable_indicator,
        "cl_assumptions_reasonable": cl_assumptions_reasonable
    }
