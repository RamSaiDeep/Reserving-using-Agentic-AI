"""
diagnostics.py — Actuarial Computed Metrics Orchestrator
Orchestrates modular diagnostics and returns backward-compatible plus new advanced diagnostic fields.
"""
import numpy as np

# Import sub-modules
from reserving.diagnostics import (
    reporting_pattern,
    ldf_stability,
    calendar_effects,
    tail_analysis,
    outliers,
    suitability,
    trace_generator
)

def compute_diagnostics(triangle):
    """
    Orchestrates the execution of all diagnostic sub-modules.
    Merges their output with original metrics to ensure backward compatibility.
    """
    # ── Backward Compatible Heuristics (Original Code) ──────────────────────
    diag = triangle.get_latest_diagonal()
    total_paid = sum(v for v in diag if v is not None and not np.isnan(v))
    ays = triangle.accident_years
    ldfs_raw = triangle.compute_ldfs()

    loss_ratios = []
    total_premium = 0.0
    if triangle.premiums:
        ldfs_list = [r['volumeWeighted'] for r in ldfs_raw[:-1]] + [1.0]
        cdfs = triangle.compute_cdfs(ldfs_list)
        for i, ay in enumerate(ays):
            prem = triangle.premiums.get(ay)
            paid_val = diag[i]
            if prem and prem > 0:
                total_premium += prem
                dev_idx = next((j for j, v in reversed(list(enumerate(triangle.matrix[i]))) if v is not None), 0)
                cdf = cdfs[dev_idx] if dev_idx < len(cdfs) else 1.0
                ultimate = round(paid_val * cdf, 2) if paid_val else None
                paid_lr = round(paid_val / prem * 100, 2) if paid_val else None
                ult_lr  = round(ultimate / prem * 100, 2) if ultimate else None
                loss_ratios.append({
                    'ay': ay,
                    'premium': round(prem, 0),
                    'paid': round(paid_val, 0) if paid_val else None,
                    'paid_lr_pct': paid_lr,
                    'estimated_ultimate': round(ultimate, 0) if ultimate else None,
                    'ultimate_lr_pct': ult_lr
                })

    suggested_elr = None
    if triangle.premiums and ldfs_raw:
        ldfs_list = [r['volumeWeighted'] for r in ldfs_raw[:-1]] + [1.0]
        cdfs = triangle.compute_cdfs(ldfs_list)
        used_up_prem = 0.0
        total_reported = 0.0
        for i, ay in enumerate(ays):
            prem = triangle.premiums.get(ay)
            paid_val = diag[i]
            dev_idx = next((j for j, v in reversed(list(enumerate(triangle.matrix[i]))) if v is not None), 0)
            cdf = cdfs[dev_idx] if dev_idx < len(cdfs) else 1.0
            pct_rep = 1.0 / cdf if cdf > 0 else 1.0
            if prem and paid_val is not None:
                used_up_prem += prem * pct_rep
                total_reported += paid_val
        if used_up_prem > 0:
            suggested_elr = round(total_reported / used_up_prem * 100, 2)

    ldf_diagnostics = []
    for row in ldfs_raw[:-1]:
        cov = row.get('cov', 0)
        n   = row.get('n', 0)
        vw  = row.get('volumeWeighted')
        sa  = row.get('straightAvg')
        stability_lbl = 'High' if cov < 0.05 else ('Moderate' if cov < 0.15 else 'Low')
        credibility = 'Full' if n >= 5 else ('Partial' if n >= 3 else 'Thin')
        dev_pct = round(abs(vw - sa) / sa * 100, 2) if sa and sa > 0 and vw else None
        ldf_diagnostics.append({
            'fromAge': row['fromAge'],
            'toAge': row['toAge'],
            'volumeWeighted': round(vw, 4) if vw else None,
            'straightAvg': round(sa, 4) if sa else None,
            'cov_pct': round(cov * 100, 2),
            'n': n,
            'stability': stability_lbl,
            'credibility': credibility,
            'vw_vs_sa_deviation_pct': dev_pct
        })

    ay_summary = []
    if ldfs_raw:
        ldfs_list = [r['volumeWeighted'] for r in ldfs_raw[:-1]] + [1.0]
        cdfs = triangle.compute_cdfs(ldfs_list)
        for i, ay in enumerate(ays):
            paid_val = diag[i]
            dev_idx = next((j for j, v in reversed(list(enumerate(triangle.matrix[i]))) if v is not None), 0)
            cdf = cdfs[dev_idx] if dev_idx < len(cdfs) else 1.0
            pct_rep = round(1.0 / cdf * 100, 1) if cdf > 0 else 100.0
            ultimate = round(paid_val * cdf, 0) if paid_val else None
            ibnr     = round(ultimate - paid_val, 0) if ultimate and paid_val else None
            ay_summary.append({
                'ay': ay,
                'paid': round(paid_val, 0) if paid_val else None,
                'cdf_to_ult': round(cdf, 4),
                'pct_reported': pct_rep,
                'estimated_ultimate': ultimate,
                'estimated_ibnr': ibnr
            })

    volume_trends = []
    for i in range(1, len(diag)):
        prev = diag[i - 1]
        curr = diag[i]
        if prev and curr and prev > 0:
            change_pct = round((curr - prev) / prev * 100, 1)
            volume_trends.append({
                'from_ay': ays[i - 1],
                'to_ay': ays[i],
                'change_pct': change_pct,
                'direction': 'up' if change_pct > 5 else ('down' if change_pct < -5 else 'stable')
            })

    avg_trend = round(float(np.mean([t['change_pct'] for t in volume_trends])), 1) if volume_trends else 0.0
    overall = {
        'total_paid': round(total_paid, 0),
        'total_premium': round(total_premium, 0) if total_premium else None,
        'overall_paid_lr_pct': round(total_paid / total_premium * 100, 2) if total_premium else None,
        'suggested_elr_for_bf_bk': suggested_elr,
        'n_accident_years': len(ays),
        'n_dev_periods': len(triangle.dev_ages),
        'has_premium': bool(triangle.premiums),
        'has_counts': any(v is not None for v in triangle.counts.values()) if hasattr(triangle, 'counts') and triangle.counts else False,
        'is_long_tail': len(triangle.dev_ages) > 7,
        'avg_paid_volume_trend_pct': avg_trend
    }

    # ── Modular Advanced Diagnostics (New Functions) ────────────────────────
    rep_fit = reporting_pattern.analyze(triangle)
    ldf_stab_results = ldf_stability.analyze(triangle)
    cal_effects = calendar_effects.analyze(triangle)
    
    # Selected tail defaults to LDF tail
    sel_tail = float(ldfs_raw[-1]['volumeWeighted']) if ldfs_raw else 1.0
    tail_diag = tail_analysis.analyze(triangle, selected_tail=sel_tail)
    
    outliers_diag = outliers.analyze(triangle)
    
    # Suitability scores
    diag_for_suitability = {
        "reporting_pattern": rep_fit,
        "ldf_stability": ldf_stab_results,
        "calendar_effects": cal_effects,
        "tail_analysis": tail_diag,
        "outliers": outliers_diag
    }
    suit_diag = suitability.analyze(triangle, diag_for_suitability)
    
    # ── Final Merge ─────────────────────────────────────────────────────────
    return {
        # Original fields
        'overall': overall,
        'loss_ratios_by_ay': loss_ratios,
        'suggested_elr': suggested_elr,
        'ldf_diagnostics': ldf_diagnostics,
        'ay_summary': ay_summary,
        'volume_trends': volume_trends,
        
        # New advanced diagnostic modules
        'reporting_pattern': rep_fit,
        'ldf_stability': ldf_stab_results,
        'calendar_effects': cal_effects,
        'tail_analysis': tail_diag,
        'outliers': outliers_diag,
        'suitability': suit_diag
    }
