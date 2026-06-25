import numpy as np
import math
from .base import MethodBase

class FrequencySeverity(MethodBase):
    code = 'FS'
    label = 'Frequency-Severity Method'
    needs_premium = False
    
    @classmethod
    def get_required_params(cls):
        return [
            {
                'key': 'approach',
                'label': 'F/S Approach',
                'type': 'select',
                'options': ['approach1', 'approach2', 'approach3'],
                'default': 'approach1',
                'hint': 'Chapter 11 Approach'
            },
            {
                'key': 'inflationRate',
                'label': 'Annual Inflation Rate (%)',
                'type': 'number',
                'default': 3.0,
                'hint': 'Severity inflation trend'
            }
        ]

    def _compute(self):
        ays = self.triangle.accident_years
        matrix = self.matrix
        N = len(ays)
        n_periods = len(self.triangle.dev_ages)
        
        approach = self.params.get('approach', 'approach1')
        inflation_rate = float(self.params.get('inflationRate', 3.0)) / 100.0
        
        # Get diagonals of active source
        diag = [next((v for v in reversed(row) if v is not None and not np.isnan(v)), 0) for row in matrix]
        dev_idx = [next((i for i, v in reversed(list(enumerate(row))) if v is not None and not np.isnan(v)), 0) for row in matrix]
        
        # Incurred diagonal for clamping
        inc_diag = []
        if hasattr(self.triangle, 'incurred_matrix') and self.triangle.incurred_matrix:
            for row in self.triangle.incurred_matrix:
                val = next((v for v in reversed(row) if v is not None and not np.isnan(v)), 0.0)
                inc_diag.append(val)
        else:
            inc_diag = list(diag)

        # Get count matrix and cumulative count diagonal
        count_matrix = self.triangle.count_matrix
        cnt_diag = [next((v for v in reversed(row) if v is not None and not np.isnan(v)), 0) for row in count_matrix]
        
        # 1. Project ultimate claim counts via Chain Ladder on counts triangle
        cnt_ldfs_raw = self.triangle.compute_ldfs_for_matrix(count_matrix)
        cnt_ldfs = [(r['volumeWeighted'] if r['volumeWeighted'] is not None else 1.0) for r in cnt_ldfs_raw[:-1]] + [1.0]
        cnt_cdfs = self.triangle.compute_cdfs(cnt_ldfs)
        
        ultimate_counts = []
        for i in range(N):
            idx = dev_idx[i]
            c_cdf = cnt_cdfs[idx] if idx < len(cnt_cdfs) else 1.0
            ult_cnt = cnt_diag[i] * c_cdf
            ultimate_counts.append(ult_cnt)

        # 2. Build Average Severity triangle
        severity_matrix = []
        for i in range(N):
            sev_row = []
            for j in range(n_periods):
                l_val = matrix[i][j]
                c_val = count_matrix[i][j]
                if l_val is not None and c_val is not None and not np.isnan(l_val) and not np.isnan(c_val) and c_val > 0:
                    sev_row.append(l_val / c_val)
                else:
                    sev_row.append(None)
            severity_matrix.append(sev_row)
            
        sev_diag = [next((v for v in reversed(row) if v is not None and not np.isnan(v)), 0) for row in severity_matrix]

        # Project ultimate average severity via Chain Ladder on severity triangle
        sev_ldfs_raw = self.triangle.compute_ldfs_for_matrix(severity_matrix)
        sev_ldfs = [(r['volumeWeighted'] if r['volumeWeighted'] is not None else 1.0) for r in sev_ldfs_raw[:-1]] + [1.0]
        sev_cdfs = self.triangle.compute_cdfs(sev_ldfs)
        
        ultimate_severities = []
        for i in range(N):
            idx = dev_idx[i]
            s_cdf = sev_cdfs[idx] if idx < len(sev_cdfs) else 1.0
            ult_sev = sev_diag[i] * s_cdf
            ultimate_severities.append(ult_sev)

        # Execute selected approach
        for i, ay in enumerate(ays):
            paid = diag[i] or 0
            idx = dev_idx[i]
            inc_val = inc_diag[i] or 0
            
            ult_cnt = ultimate_counts[i]
            ult_sev = ultimate_severities[i]
            
            if approach == 'approach1':
                # Count/Severity Development
                ultimate = ult_cnt * ult_sev
                
            elif approach == 'approach2':
                # Frequency Rate / Inflation Severity
                exp = self.triangle.exposures.get(ay, 1000.0)
                # Compute average frequency across portfolio
                obs_frequencies = []
                for k in range(N):
                    e_k = self.triangle.exposures.get(ays[k], 1000.0)
                    if e_k > 0:
                        obs_frequencies.append(ultimate_counts[k] / e_k)
                selected_freq = np.mean(obs_frequencies) if obs_frequencies else 0.1
                
                # Expected Counts = Exposure * Selected Frequency
                expected_counts = exp * selected_freq
                
                # Trend average severity using inflation
                base_sev = np.mean(ultimate_severities) if ultimate_severities else 5000.0
                trended_sev = base_sev * ((1.0 + inflation_rate) ** (i - (N - 1)))
                
                ultimate = expected_counts * trended_sev
                
            else: # approach3 (Disposal Rate / Incremental Severity)
                # Incremental Closed Counts and Paid Losses
                projected_paid = paid
                if idx < n_periods - 1:
                    # Disposal rates
                    disposal_rates = []
                    for j in range(n_periods):
                        d_r = count_matrix[i][j] / ult_cnt if ult_cnt > 0 else 1.0
                        disposal_rates.append(d_r)
                        
                    # Project disposal rates at future ages (use simple volume weighted projection)
                    proj_disp = list(disposal_rates)
                    for j in range(idx + 1, n_periods):
                        prev_disp = proj_disp[j-1] if j > 0 else 0.0
                        ratio = cnt_ldfs[j-1]
                        proj_disp[j] = min(1.0, prev_disp * ratio)
                        if proj_disp[j] < prev_disp:
                            proj_disp[j] = prev_disp

                    # Build incremental severity history
                    inc_severities_by_age = {k: [] for k in range(n_periods)}
                    for row_idx in range(N):
                        for k in range(1, n_periods):
                            p_curr = matrix[row_idx][k]
                            p_prev = matrix[row_idx][k-1]
                            c_curr = count_matrix[row_idx][k]
                            c_prev = count_matrix[row_idx][k-1]
                            if p_curr is not None and p_prev is not None and c_curr is not None and c_prev is not None:
                                inc_loss = p_curr - p_prev
                                inc_cnt = c_curr - c_prev
                                if inc_cnt > 0 and inc_loss > 0:
                                    inc_severities_by_age[k].append(inc_loss / inc_cnt)
                                    
                    # Average incremental severity by age
                    avg_inc_sev = {}
                    for k in range(n_periods):
                        sevs = inc_severities_by_age[k]
                        avg_inc_sev[k] = np.mean(sevs) if sevs else (ult_sev * 0.1)

                    # Project future incremental losses
                    future_paid = 0.0
                    for j in range(idx + 1, n_periods):
                        prev_disp = proj_disp[j-1]
                        curr_disp = proj_disp[j]
                        inc_cnt = ult_cnt * (curr_disp - prev_disp)
                        
                        trend_factor = (1.0 + inflation_rate) ** (i - (N - 1))
                        proj_sev = avg_inc_sev.get(j, ult_sev * 0.1) * trend_factor
                        
                        future_paid += max(0.0, inc_cnt * proj_sev)
                        
                    projected_paid += future_paid
                ultimate = projected_paid
                
            # Clamp ultimate to incurred claims
            if ultimate < inc_val:
                ultimate = inc_val
                
            ibnr = ultimate - paid
            cdf_val = cnt_cdfs[idx] if idx < len(cnt_cdfs) else 1.0
            pct_rep = (1.0 / cdf_val * 100) if cdf_val > 0 else 100
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': round(cdf_val, 4),
                'pctReported': round(pct_rep, 1),
                'ultimate': ultimate,
                'ibnr': ibnr,
                'ultimate_counts': round(ult_cnt, 1),
                'ultimate_severity': round(ult_sev, 2),
                'note': f'F/S {approach.capitalize()}'
            })
