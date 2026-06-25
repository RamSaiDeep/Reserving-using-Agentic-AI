import numpy as np
import math
from .base import MethodBase

class MackChainladder(MethodBase):
    code = 'MCL'
    label = 'Mack Chain Ladder'
    needs_premium = False
    
    def _compute(self):
        ays = self.triangle.accident_years
        matrix = self.matrix
        N = len(ays)
        n_periods = len(self.triangle.dev_ages)
        
        diag = self.get_latest_diagonal()
        dev_idx = self.get_development_indices()
        inc_diag = self.get_incurred_diagonal()
        
        # Calculate sigma squared for each period j (development ages 0 to n_periods - 2)
        sigmas = []
        for j in range(n_periods - 1):
            sum_num = 0.0
            n_pts = 0
            for row in matrix:
                if j < len(row) - 1:
                    cur = row[j]
                    nxt = row[j+1]
                    if cur is not None and nxt is not None and not np.isnan(cur) and not np.isnan(nxt) and cur > 0:
                        sum_num += cur * (nxt/cur - self.ldfs[j])**2
                        n_pts += 1
            var = sum_num / (n_pts - 1) if n_pts > 1 else 0.0
            sigmas.append(var)
        sigmas.append(0.0) # Tail sigma
        
        # Extrapolate zero or near-zero sigmas for late periods (log-linear extrapolation)
        for j in range(len(sigmas) - 1):
            if sigmas[j] <= 0:
                prev_non_zeros = [sigmas[k] for k in range(j) if sigmas[k] > 0]
                if len(prev_non_zeros) >= 2:
                    ratio = prev_non_zeros[-1] / prev_non_zeros[-2]
                    sigmas[j] = prev_non_zeros[-1] * min(0.9, ratio)
                elif len(prev_non_zeros) == 1:
                    sigmas[j] = prev_non_zeros[0] * 0.5
                else:
                    sigmas[j] = 0.0001
        
        # Project ultimate matrix using LDFs
        projected_matrix = np.copy(matrix)
        for i in range(N):
            idx = dev_idx[i]
            for k in range(idx + 1, n_periods):
                projected_matrix[i, k] = projected_matrix[i, k-1] * self.ldfs[k-1]
                
        # Calculate sum of historical claims for each development age k
        sum_C_k = []
        for k in range(n_periods):
            val = sum(matrix[row_idx][k] for row_idx in range(N) if row_idx + k < n_periods and matrix[row_idx][k] is not None and not np.isnan(matrix[row_idx][k]))
            sum_C_k.append(val if val > 0 else 1.0)
            
        # Calculate individual accident year standard errors and risks
        proc_var_by_ay = {}
        param_var_by_ay = {}
        mse_by_ay = {}
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0.0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            
            ultimate = projected_matrix[i, n_periods - 1]
            inc_val = inc_diag[i] or 0.0
            if ultimate < inc_val:
                ultimate = inc_val
                
            ibnr = ultimate - paid
            pct_rep = (1.0 / cdf * 100) if cdf > 0 else 100
            
            p_var = 0.0
            pa_var = 0.0
            
            if ultimate > 0:
                for k in range(idx, n_periods - 1):
                    fk = self.ldfs[k]
                    if fk > 0 and sigmas[k] > 0:
                        C_ik = projected_matrix[i, k]
                        sum_C_jk = sum_C_k[k]
                        if C_ik > 0:
                            p_var += (sigmas[k] / (fk**2)) * (1.0 / C_ik)
                        if sum_C_jk > 0:
                            pa_var += (sigmas[k] / (fk**2)) * (1.0 / sum_C_jk)
                            
            proc_var_val = ultimate**2 * p_var
            param_var_val = ultimate**2 * pa_var
            mse_val = proc_var_val + param_var_val
            
            proc_var_by_ay[ay] = proc_var_val
            param_var_by_ay[ay] = param_var_val
            mse_by_ay[ay] = mse_val
            
            std_err = math.sqrt(mse_val) if mse_val > 0 else 0.0
            cv = (std_err / ibnr) if ibnr > 0 else 0.0
            
            # Confidence intervals
            ci_50 = ultimate
            ci_75 = ultimate + 0.67448 * std_err
            ci_95 = ultimate + 1.64485 * std_err
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': round(cdf, 4),
                'pctReported': round(pct_rep, 1),
                'ultimate': ultimate,
                'ibnr': ibnr,
                'stdError': std_err,
                'cv': round(cv, 3), # return as ratio
                'ibnr_50': ibnr,
                'ibnr_75': ibnr + 0.67448 * std_err,
                'ibnr_95': ibnr + 1.64485 * std_err,
                'ultimate_50': ci_50,
                'ultimate_75': ci_75,
                'ultimate_95': ci_95
            })
            
        # Compute Portfolio-wide Risks & Volatility
        total_proc_var = sum(proc_var_by_ay.values())
        total_param_var = sum(param_var_by_ay.values())
        
        # Covariance terms for parameter variance
        cov_sum = 0.0
        for i in range(N):
            for j in range(i + 1, N):
                idx_i = dev_idx[i]
                idx_j = dev_idx[j]
                start_k = max(idx_i, idx_j)
                
                cov_k_sum = 0.0
                for k in range(start_k, n_periods - 1):
                    fk = self.ldfs[k]
                    sum_C_jk = sum_C_k[k]
                    if fk > 0 and sigmas[k] > 0 and sum_C_jk > 0:
                        cov_k_sum += sigmas[k] / (fk**2 * sum_C_jk)
                        
                ult_i = projected_matrix[i, n_periods - 1]
                ult_j = projected_matrix[j, n_periods - 1]
                cov_sum += ult_i * ult_j * cov_k_sum
                
        total_param_var += 2.0 * cov_sum
        total_mse = total_proc_var + total_param_var
        
        self.volatility = math.sqrt(total_mse) if total_mse > 0 else 0.0
        self.process_risk = math.sqrt(total_proc_var) if total_proc_var > 0 else 0.0
        self.parameter_risk = math.sqrt(total_param_var) if total_param_var > 0 else 0.0
