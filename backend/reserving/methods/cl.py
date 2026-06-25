import numpy as np
from .base import MethodBase

class ChainLadder(MethodBase):
    code = 'CL'
    label = 'Chain Ladder (Basic)'
    needs_premium = False
    
    def _compute(self):
        ays = self.triangle.accident_years
        diag = self.get_latest_diagonal()
        dev_idx = self.get_development_indices()
        
        matching_cdfs = []
        for i in range(len(ays)):
            idx = dev_idx[i]
            matching_cdfs.append(self.cdfs[idx] if idx < len(self.cdfs) else 1.0)
            
        from reserving.core.development_engine import DevelopmentEngine
        ultimates = DevelopmentEngine.project_ultimate(diag, matching_cdfs)
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0.0
            cdf = matching_cdfs[i]
            ultimate = ultimates[i]
            ibnr = ultimate - paid
            pct_rep = (1.0 / cdf * 100) if cdf > 0 else 100
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': round(cdf, 4),
                'pctReported': round(pct_rep, 1),
                'ultimate': ultimate,
                'ibnr': ibnr
            })
