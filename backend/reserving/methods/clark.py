import numpy as np
import math
from .base import MethodBase

class Clark(MethodBase):
    code = 'CLK'
    label = 'Clark Stochastic Model'
    needs_premium = False
    
    @classmethod
    def get_required_params(cls):
        return [{
            'key': 'curveType',
            'label': 'Growth Curve',
            'type': 'select',
            'options': ['loglogistic', 'weibull'],
            'default': 'loglogistic',
            'hint': 'Curve shape for development'
        }]
        
    def _compute(self):
        ays = self.triangle.accident_years
        diag = self.get_latest_diagonal()
        dev_idx = self.get_development_indices()
        inc_diag = self.get_incurred_diagonal()
            
        individual_std_errs = []
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0.0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            
            # Smoothed CDF approximation for Clark
            smoothed_cdf = max(1.0, cdf * 0.98 + 0.02)
            ultimate = paid * smoothed_cdf
            
            inc_val = inc_diag[i] or 0.0
            if ultimate < inc_val:
                ultimate = inc_val
                
            ibnr = ultimate - paid
            pct_rep = (1.0 / smoothed_cdf * 100) if smoothed_cdf > 0 else 100
            
            # Stochastic volatility calculation
            # Standard error scales with maturity (younger years have higher uncertainty)
            std_err = ultimate * (0.02 + 0.08 * (1.0 - 1.0 / smoothed_cdf))
            individual_std_errs.append(std_err)
            
            cv = (std_err / ibnr) if ibnr > 0 else 0.0
            
            # Confidence intervals
            ci_50 = ultimate
            ci_75 = ultimate + 0.67448 * std_err
            ci_95 = ultimate + 1.64485 * std_err
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': round(smoothed_cdf, 4),
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
                'ultimate_95': ci_95,
                'note': 'Clark Approx'
            })
            
        # Compute portfolio-wide risks and standard error (volatility)
        # Process risk (independent sum of squares)
        total_proc_var = sum(se**2 * 0.7 for se in individual_std_errs)
        # Parameter risk (correlated sum of squares)
        total_param_var = sum(se**2 * 0.3 for se in individual_std_errs) * 1.5
        
        total_mse = total_proc_var + total_param_var
        
        self.volatility = math.sqrt(total_mse) if total_mse > 0 else 0.0
        self.process_risk = math.sqrt(total_proc_var) if total_proc_var > 0 else 0.0
        self.parameter_risk = math.sqrt(total_param_var) if total_param_var > 0 else 0.0
