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
        diag = [next((v for v in reversed(row) if v is not None and not np.isnan(v)), 0) for row in self.matrix]
        dev_idx = [next((i for i, v in reversed(list(enumerate(row))) if v is not None and not np.isnan(v)), 0) for row in self.matrix]
        
        elr = float(self.params.get('aprioriLossRatio', 65)) / 100.0
        iters = int(self.params.get('iterations', 1))
        
        # Get incurred diagonal to clamp ultimate and prevent negative IBNR
        inc_diag = []
        if hasattr(self.triangle, 'incurred_matrix') and self.triangle.incurred_matrix:
            for row in self.triangle.incurred_matrix:
                val = next((v for v in reversed(row) if v is not None and not np.isnan(v)), 0.0)
                inc_diag.append(val)
        else:
            inc_diag = list(diag)

        for i, ay in enumerate(ays):
            claims_val = diag[i] or 0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            prem = self.triangle.premiums.get(ay, 0)
            
            percent_unreported = 1.0 / cdf if cdf > 0 else 1.0
            percent_reported = 1.0 - percent_unreported
            
            expected_ultimate = elr * prem
            ultimate = (percent_unreported * expected_ultimate) + (percent_reported * claims_val)
            
            # Clamp ultimate to incurred claims
            inc_val = inc_diag[i] or 0
            if ultimate < inc_val:
                ultimate = inc_val
                
            ibnr = ultimate - claims_val
            
            self.results.append({
                'ay': ay,
                'paid': claims_val,
                'cdfToUlt': round(cdf, 4),
                'pctReported': round(percent_reported * 100, 1),
                'ultimate': ultimate,
                'ibnr': ibnr
            })
