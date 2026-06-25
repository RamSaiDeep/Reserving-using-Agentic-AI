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
        diag = self.get_latest_diagonal()
        dev_idx = self.get_development_indices()
        inc_diag = self.get_incurred_diagonal()
        
        # Read initial ELR from params (aprioriLossRatio) defaulting to suggested ELR if not provided or 65%
        initial_expected_lr = float(self.params.get('aprioriLossRatio', 65)) / 100.0
        legacy_comp = self.params.get('legacy_compatibility', True)
        allow_neg = self.params.get('allow_negative_ibnr', False)
        
        reported_claims = []
        earned_premium = []
        for i, ay in enumerate(ays):
            reported_claims.append(diag[i] or 0.0)
            earned_premium.append(self.triangle.premiums.get(ay, 0.0))
            
        reported_claims = np.array(reported_claims)
        earned_premium = np.array(earned_premium)
        
        if legacy_comp:
            # Step 1: Calculate expected ultimate using initial LR
            expected_ultimate_basic = initial_expected_lr * earned_premium
            
            # Step 2: Calculate reported as % of expected ultimate
            pct_reported = []
            for rc, eub in zip(reported_claims, expected_ultimate_basic):
                pct_reported.append(rc / eub if eub > 0 else 0.0)
            pct_reported = np.array(pct_reported)
            
            # Step 3: Calculate adjusted LR (exposure-credibility weighted)
            denom = sum(earned_premium * initial_expected_lr)
            adjusted_expected_lr = sum(reported_claims) / denom if denom > 0 else 0.65
            
            # Step 4: Recalculate ultimate with adjusted LR
            expected_ultimate = adjusted_expected_lr * earned_premium
        else:
            # Textbook Cape Cod (Stanard-Bühlmann)
            used_up_premium = 0.0
            for i, ay in enumerate(ays):
                prem = earned_premium[i]
                idx = dev_idx[i]
                cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
                pct_rep = 1.0 / cdf if cdf > 0 else 1.0
                used_up_premium += prem * pct_rep
            
            adjusted_expected_lr = sum(reported_claims) / used_up_premium if used_up_premium > 0 else 0.65
            
            expected_ultimate = []
            for i, ay in enumerate(ays):
                claims_val = reported_claims[i]
                prem = earned_premium[i]
                idx = dev_idx[i]
                cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
                pct_unrep = 1.0 - (1.0 / cdf if cdf > 0 else 1.0)
                expected_ultimate.append(claims_val + adjusted_expected_lr * prem * pct_unrep)
            expected_ultimate = np.array(expected_ultimate)
            
        for i, ay in enumerate(ays):
            claims_val = diag[i] or 0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            prem = earned_premium[i]
            
            ultimate = expected_ultimate[i]
            
            # Clamp ultimate to incurred claims
            inc_val = inc_diag[i] or 0.0
            if not allow_neg and ultimate < inc_val:
                ultimate = inc_val
                
            ibnr = ultimate - claims_val
            pct_rep = (1.0 / cdf * 100) if cdf > 0 else 100
            
            self.results.append({
                'ay': ay,
                'paid': claims_val,
                'cdfToUlt': round(cdf, 4),
                'pctReported': round(pct_rep, 1),
                'ultimate': ultimate,
                'ibnr': ibnr,
                'capeCodELR': round(adjusted_expected_lr, 4),
                'premium': prem
            })
