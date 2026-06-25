import numpy as np
from .base import MethodBase

class CaseOutstanding(MethodBase):
    code = 'CO'
    label = 'Case Outstanding'
    needs_premium = False
    requires_paid_triangle = True
    requires_incurred_triangle = True
    supports_source_selection = False
    
    def _compute(self):
        ays = self.triangle.accident_years
        
        # Get diagonals of paid and incurred matrices
        diag = self.get_latest_diagonal()
        inc_diag = self.get_incurred_diagonal()
        dev_idx = self.get_development_indices()
        
        # Compute paid CDFs using volume weighted averages
        paid_ldfs_raw = self.triangle.compute_ldfs_for_matrix(self.triangle.matrix)
        paid_ldfs_list = [(r['volumeWeighted'] if r['volumeWeighted'] is not None else 1.0) for r in paid_ldfs_raw[:-1]] + [1.0]
        paid_cdfs = self.triangle.compute_cdfs(paid_ldfs_list)
        
        # Compute incurred CDFs using volume weighted averages
        inc_ldfs_raw = self.triangle.compute_ldfs_for_matrix(self.triangle.incurred_matrix)
        inc_ldfs_list = [(r['volumeWeighted'] if r['volumeWeighted'] is not None else 1.0) for r in inc_ldfs_raw[:-1]] + [1.0]
        inc_cdfs = self.triangle.compute_cdfs(inc_ldfs_list)
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0.0
            incurred = inc_diag[i] if i < len(inc_diag) and inc_diag[i] is not None else paid
            case_os = max(0.0, incurred - paid)
            
            # Determine Case CDF
            idx = dev_idx[i]
            p_cdf = paid_cdfs[idx] if idx < len(paid_cdfs) else 1.0
            r_cdf = inc_cdfs[idx] if idx < len(inc_cdfs) else 1.0
            
            if p_cdf > r_cdf:
                case_cdf = ((r_cdf - 1.0) * p_cdf) / (p_cdf - r_cdf) + 1.0
            else:
                case_cdf = r_cdf
                
            reserve = case_os * case_cdf
            ultimate = paid + reserve
            ibnr = ultimate - incurred
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': round(case_cdf, 4),
                'pctReported': round((1.0 / case_cdf * 100) if case_cdf > 0 else 100, 1),
                'ultimate': ultimate,
                'ibnr': ibnr,
                'note': 'Case CDF Method'
            })
