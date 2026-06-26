"""
outliers.py — Outlier Detection
Detects cell-level anomalies in link ratios using column-level z-scores and ranks accident years.
"""
import numpy as np

def analyze(triangle):
    """
    Detects cell-level outliers in age-to-age factors using column-level statistics.
    Scores and ranks accident years by outlier severity.
    Returns structured results.
    """
    dev_ages = triangle.dev_ages
    ays = triangle.accident_years
    matrix = triangle.matrix
    
    # 1. Compute cell-level age-to-age factors
    cell_outliers = []
    
    # We will score each accident year
    ay_scores = {ay: {"critical": 0, "high": 0, "medium": 0, "total_score": 0.0} for ay in ays}
    
    for j in range(len(dev_ages) - 1):
        factors = []
        rows_with_data = []
        
        # Collect factors for column j
        for i, ay in enumerate(ays):
            cur = matrix[i][j]
            nxt = matrix[i][j+1]
            if cur is not None and nxt is not None and not np.isnan(cur) and not np.isnan(nxt) and cur > 0:
                f = nxt / cur
                factors.append(f)
                rows_with_data.append((ay, f))
                
        if len(factors) < 2:
            continue
            
        mean_j = float(np.mean(factors))
        std_j = float(np.std(factors, ddof=1)) if len(factors) > 1 else 0.0
        
        for ay, f in rows_with_data:
            if std_j > 0:
                z = (f - mean_j) / std_j
            else:
                z = 0.0
                
            abs_z = abs(z)
            
            # Outlier thresholds
            is_outlier = False
            severity = "Low"
            
            if abs_z > 3.0:
                is_outlier = True
                severity = "Critical"
                ay_scores[ay]["critical"] += 1
                ay_scores[ay]["total_score"] += 10.0
            elif abs_z > 2.5:
                is_outlier = True
                severity = "High"
                ay_scores[ay]["high"] += 1
                ay_scores[ay]["total_score"] += 5.0
            elif abs_z > 1.8:
                is_outlier = True
                severity = "Medium"
                ay_scores[ay]["medium"] += 1
                ay_scores[ay]["total_score"] += 2.0
            elif std_j == 0.0:
                # Fallback if standard deviation is 0 but factor deviates significantly from the mean
                deviation_pct = abs(f - mean_j) / mean_j if mean_j > 0 else 0.0
                if deviation_pct > 0.15 and abs(f - mean_j) > 0.05:
                    is_outlier = True
                    severity = "Medium"
                    ay_scores[ay]["medium"] += 1
                    ay_scores[ay]["total_score"] += 2.0
                    
            if is_outlier:
                severity_val = "Moderate" if severity == "Medium" else severity
                ratio_val = round(float(f / mean_j), 2) if mean_j > 0 else 1.0
                cell_outliers.append({
                    "accident_year": ay,
                    "ay": ay,
                    "from_age": dev_ages[j],
                    "to_age": dev_ages[j+1],
                    "lag": dev_ages[j],
                    "factor": round(float(f), 4),
                    "value": round(float(f), 4),
                    "expected_factor": round(mean_j, 4),
                    "median": round(mean_j, 4),
                    "z_score": round(float(z), 2),
                    "ratio": ratio_val,
                    "severity": severity_val,
                    "reason": f"Age-to-age factor {f:.4f} deviates from column average of {mean_j:.4f} (Z-score: {z:.2f})"
                })
                
    # Rank accident years by total outlier score
    accident_year_ranking = []
    for rank, (ay, score_dict) in enumerate(sorted(ay_scores.items(), key=lambda x: x[1]["total_score"], reverse=True), start=1):
        accident_year_ranking.append({
            "accident_year": ay,
            "rank": rank,
            "outlier_score": score_dict["total_score"],
            "details": {
                "critical_count": score_dict["critical"],
                "high_count": score_dict["high"],
                "medium_count": score_dict["medium"]
            }
        })
        
    return {
        "cell_outliers": cell_outliers,
        "accident_year_ranking": accident_year_ranking
    }
