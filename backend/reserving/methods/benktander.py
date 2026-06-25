import numpy as np
from .base import MethodBase

class Benktander(MethodBase):
    code = 'BK'
    label = 'Benktander'
    needs_premium = True
    
    @classmethod
    def get_required_params(cls):
        return [{
            'key': 'aprioriLossRatio',
            'label': 'A Priori Loss Ratio (%)',
            'type': 'percent',
            'default': 65,
            'hint': 'Expected loss ratio (e.g., 65 for 65%)'
        }, {
            'key': 'iterations',
            'label': 'Iterations (c)',
            'type': 'number',
            'default': 1,
            'hint': 'c=1 is standard Benktander. Higher values converge to Chain Ladder.'
        }]
        
    def _compute(self):
        ays = self.triangle.accident_years
        diag = self.get_latest_diagonal()
        dev_idx = self.get_development_indices()
        
        elr = float(self.params.get('aprioriLossRatio', 65)) / 100.0
        iters = int(self.params.get('iterations', 1))
        legacy_comp = self.params.get('legacy_compatibility', True)
        allow_neg = self.params.get('allow_negative_ibnr', False)
        
        # Get incurred diagonal to clamp ultimate and prevent negative IBNR
        inc_diag = self.get_incurred_diagonal()

        for i, ay in enumerate(ays):
            claims_val = diag[i] or 0.0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            prem = self.triangle.premiums.get(ay, 0)
            
            expected_ultimate = elr * prem
            
            if legacy_comp:
                percent_unreported = 1.0 / cdf if cdf > 0 else 1.0
                percent_reported = 1.0 - percent_unreported
                ultimate = (percent_unreported * expected_ultimate) + (percent_reported * claims_val)
                percent_rep_display = percent_reported
            else:
                pct_reported = 1.0 / cdf if cdf > 0 else 1.0
                pct_unreported = 1.0 - pct_reported
                
                u_k = expected_ultimate
                for _ in range(iters):
                    u_k = claims_val + u_k * pct_unreported
                ultimate = u_k
                percent_rep_display = pct_reported
            
            # Clamp ultimate to incurred claims if not allow_neg
            inc_val = inc_diag[i] or 0.0
            if not allow_neg and ultimate < inc_val:
                ultimate = inc_val
                
            ibnr = ultimate - claims_val
            
            self.results.append({
                'ay': ay,
                'paid': claims_val,
                'cdfToUlt': round(cdf, 4),
                'pctReported': round(percent_rep_display * 100, 1),
                'ultimate': ultimate,
                'ibnr': ibnr
            })
