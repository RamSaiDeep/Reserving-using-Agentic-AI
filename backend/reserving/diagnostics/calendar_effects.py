"""
calendar_effects.py — Calendar Year Effects
Detects calendar-year inflation trends and abnormal calendar year anomalies.
"""
import numpy as np
from collections import defaultdict

def analyze(triangle):
    """
    Groups link ratio deviations by calendar year.
    Fits a linear regression to detect multi-year calendar year trends.
    Flags calendar years with significant abnormal deviations.
    Returns structured metrics.
    """
    dev_ages = triangle.dev_ages
    ays = triangle.accident_years
    matrix = triangle.matrix
    
    # 1. Compute column-level simple average LDFs
    ldfs_raw = triangle.compute_ldfs()
    sa_factors = {r['fromAge']: r['straightAvg'] for r in ldfs_raw[:-1] if r['straightAvg'] is not None}
    
    # Map index to column age
    age_keys = {j: dev_ages[j] for j in range(len(dev_ages) - 1)}
    
    # Collect cell-level link ratio deviations: d_ij = f_ij / sa_j
    cy_data = defaultdict(list)
    
    for i, ay in enumerate(ays):
        row = matrix[i]
        for j in range(len(dev_ages) - 1):
            cur = row[j]
            nxt = row[j+1]
            
            if cur is not None and nxt is not None and not np.isnan(cur) and not np.isnan(nxt) and cur > 0:
                f_ij = nxt / cur
                age_key = age_keys[j]
                sa_j = sa_factors.get(age_key)
                
                if sa_j and sa_j > 0:
                    d_ij = f_ij / sa_j
                    # Calendar Year calculation: AY + (Lag / 12) - 1
                    # Since dev_ages is in months: Lag = dev_ages[j+1]
                    lag_months = dev_ages[j+1]
                    cy = int(ay + (lag_months / 12) - 1)
                    cy_data[cy].append(d_ij)
                    
    # Summarize by calendar year
    calendar_years_list = []
    anomalies = []
    
    for cy, vals in sorted(cy_data.items()):
        avg_dev = float(np.mean(vals))
        count = len(vals)
        dev_pct = (avg_dev - 1.0) * 100
        
        is_anomaly = bool(abs(avg_dev - 1.0) > 0.05)
        if is_anomaly:
            anomalies.append(cy)
            
        calendar_years_list.append({
            "calendar_year": cy,
            "avg_deviation": round(avg_dev, 4),
            "avg_deviation_pct": round(dev_pct, 2),
            "n_factors": count,
            "is_anomaly": is_anomaly
        })
        
    # Fit linear regression across calendar years to detect multi-year trends
    slope = 0.0
    intercept = 0.0
    r_squared = 0.0
    trend_detected = False
    trend_direction = "none"
    
    if len(calendar_years_list) >= 3:
        x_cy = np.array([item["calendar_year"] for item in calendar_years_list], dtype=float)
        y_dev = np.array([item["avg_deviation"] for item in calendar_years_list], dtype=float)
        
        try:
            # Linear fit
            slope, intercept = np.polyfit(x_cy, y_dev, 1)
            
            # Compute R-squared
            y_pred = slope * x_cy + intercept
            sse = np.sum((y_dev - y_pred) ** 2)
            sst = np.sum((y_dev - np.mean(y_dev)) ** 2)
            r_squared = 1.0 - (sse / sst) if sst > 0 else 1.0
            r_squared = max(0.0, min(1.0, r_squared))
            
            # Trend significance: slope magnitude > 0.005 and R2 > 0.3
            if abs(slope) > 0.005 and r_squared > 0.3:
                trend_detected = True
                trend_direction = "up" if slope > 0 else "down"
        except Exception:
            pass
            
    return {
        "calendar_years": calendar_years_list,
        "slope": round(float(slope), 6),
        "r_squared": round(float(r_squared), 4),
        "trend_detected": trend_detected,
        "trend_direction": trend_direction,
        "anomalies": anomalies
    }
