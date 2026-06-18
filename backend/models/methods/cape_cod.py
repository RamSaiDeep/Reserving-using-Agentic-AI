import numpy as np
from .base import MethodBase

class CapeCod(MethodBase):
    code = 'CC'
    label = 'Cape Cod (Stanard-Bühlmann)'
    needs_premium = True
    
    @classmethod
    def get_required_params(cls):
        return [{
            'key': 'decay',
            'label': 'Decay Factor',
            'type': 'percent',
            'default': 1.0,
            'hint': '1.0 = standard Cape Cod. <1.0 gives more weight to recent years.'
        }]
        
    def _compute(self):
        ays = self.triangle.accident_years
        diag = self.triangle.get_latest_diagonal()
        dev_idx = [next((i for i, v in reversed(list(enumerate(row))) if v is not None and not np.isnan(v)), 0) for row in self.triangle.matrix]
        decay = float(self.params.get('decay', 1.0))
        
        # Calculate overall ELR
        used_prem = 0
        used_ult_cl = 0
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            prem = self.triangle.premiums.get(ay, 0)
            
            pct_rep = 1.0 / cdf if cdf > 0 else 1.0
            weight = decay ** (len(ays) - 1 - i)
            
            used_prem += prem * pct_rep * weight
            used_ult_cl += paid * weight
            
        overall_elr = used_ult_cl / used_prem if used_prem > 0 else 0.65
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            prem = self.triangle.premiums.get(ay, 0)
            
            pct_unreported = 1.0 - (1.0 / cdf) if cdf > 0 else 0
            ibnr = prem * overall_elr * pct_unreported
            ultimate = paid + ibnr
            pct_rep = (1.0 / cdf * 100) if cdf > 0 else 100
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': round(cdf, 4),
                'pctReported': round(pct_rep, 1),
                'ultimate': ultimate,
                'ibnr': ibnr,
                'capeCodELR': round(overall_elr, 4)
            })
