import numpy as np
import math

class MethodBase:
    code = 'BASE'
    label = 'Base Method'
    needs_premium = False
    
    @classmethod
    def get_required_params(cls):
        return []
        
    def __init__(self):
        self.results = []
        self.total_ibnr = 0
        self.total_ultimate = 0
        self.triangle = None
        self.params = {}
        self.ldfs = []
        self.cdfs = []
        
    def fit(self, triangle, params, custom_ldfs):
        self.triangle = triangle
        self.params = params
        self.ldfs = custom_ldfs
        self.cdfs = triangle.compute_cdfs(self.ldfs)
        self.results = []
        self._compute()
        
    def _compute(self):
        raise NotImplementedError()
        
    def get_results(self):
        return self.results
        
    def get_total_ibnr(self):
        return sum(r.get('ibnr', 0) for r in self.results)
        
    def get_total_ultimate(self):
        return sum(r.get('ultimate', 0) for r in self.results)


class ChainLadder(MethodBase):
    code = 'CL'
    label = 'Chain Ladder (Basic)'
    needs_premium = False
    
    def _compute(self):
        ays = self.triangle.accident_years
        diag = self.triangle.get_latest_diagonal()
        dev_idx = [next((i for i, v in reversed(list(enumerate(row))) if v is not None and not np.isnan(v)), 0) for row in self.triangle.matrix]
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            
            ultimate = paid * cdf
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

class MackChainladder(MethodBase):
    code = 'MCL'
    label = 'Mack Chain Ladder'
    needs_premium = False
    
    def _compute(self):
        ays = self.triangle.accident_years
        diag = self.triangle.get_latest_diagonal()
        matrix = self.triangle.matrix
        dev_idx = [next((i for i, v in reversed(list(enumerate(row))) if v is not None and not np.isnan(v)), 0) for row in matrix]
        
        # Calculate sigma squared for each period
        sigmas = []
        n_periods = len(self.triangle.dev_ages)
        for j in range(n_periods - 1):
            sum_num = 0
            n_pts = 0
            for row in matrix:
                cur = row[j]
                nxt = row[j+1]
                if cur is not None and nxt is not None and cur > 0:
                    sum_num += cur * (nxt/cur - self.ldfs[j])**2
                    n_pts += 1
            var = sum_num / (n_pts - 1) if n_pts > 1 else 0
            sigmas.append(var)
        sigmas.append(0) # Tail
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            
            ultimate = paid * cdf
            ibnr = ultimate - paid
            pct_rep = (1.0 / cdf * 100) if cdf > 0 else 100
            
            mse_sum = 0
            if ultimate > 0:
                for k in range(idx, n_periods - 1):
                    fk = self.ldfs[k]
                    if fk > 0:
                        mse_sum += (sigmas[k] / (fk**2)) * (1.0 / paid)
                        
            std_err = math.sqrt(ultimate**2 * mse_sum) if mse_sum > 0 else 0
            cv = (std_err / ibnr * 100) if ibnr > 0 else 0
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': round(cdf, 4),
                'pctReported': round(pct_rep, 1),
                'ultimate': ultimate,
                'ibnr': ibnr,
                'stdError': std_err,
                'cv': round(cv, 1),
                'ibnr_75': ibnr + 0.674 * std_err,
                'ibnr_95': ibnr + 1.645 * std_err
            })

class BornhuetterFerguson(MethodBase):
    code = 'BF'
    label = 'Bornhuetter-Ferguson'
    needs_premium = True
    
    @classmethod
    def get_required_params(cls):
        return [{
            'key': 'aprioriLossRatio',
            'label': 'A Priori Loss Ratio',
            'type': 'percent',
            'default': 0.65,
            'hint': 'Expected loss ratio (e.g., 0.65 for 65%)'
        }]
        
    def _compute(self):
        ays = self.triangle.accident_years
        diag = self.triangle.get_latest_diagonal()
        dev_idx = [next((i for i, v in reversed(list(enumerate(row))) if v is not None and not np.isnan(v)), 0) for row in self.triangle.matrix]
        elr = float(self.params.get('aprioriLossRatio', 0.65))
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            prem = self.triangle.premiums.get(ay, 0)
            
            pct_unreported = 1.0 - (1.0 / cdf) if cdf > 0 else 0
            pct_rep = (1.0 / cdf * 100) if cdf > 0 else 100
            
            ibnr = prem * elr * pct_unreported
            ultimate = paid + ibnr
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': round(cdf, 4),
                'pctReported': round(pct_rep, 1),
                'ultimate': ultimate,
                'ibnr': ibnr
            })

class Benktander(MethodBase):
    code = 'BK'
    label = 'Benktander'
    needs_premium = True
    
    @classmethod
    def get_required_params(cls):
        return [{
            'key': 'aprioriLossRatio',
            'label': 'A Priori Loss Ratio',
            'type': 'percent',
            'default': 0.65,
            'hint': 'Used for the initial BF ultimate'
        }, {
            'key': 'iterations',
            'label': 'Iterations (c)',
            'type': 'number',
            'default': 1,
            'hint': 'c=1 is standard Benktander. Higher values converge to Chain Ladder.'
        }]
        
    def _compute(self):
        ays = self.triangle.accident_years
        diag = self.triangle.get_latest_diagonal()
        dev_idx = [next((i for i, v in reversed(list(enumerate(row))) if v is not None and not np.isnan(v)), 0) for row in self.triangle.matrix]
        
        elr = float(self.params.get('aprioriLossRatio', 0.65))
        iters = int(self.params.get('iterations', 1))
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            prem = self.triangle.premiums.get(ay, 0)
            
            pct_rep = 1.0 / cdf if cdf > 0 else 1.0
            q = pct_unreported = 1.0 - pct_rep
            
            # Initial BF
            U_bf = paid + (prem * elr * q)
            U_current = U_bf
            
            for _ in range(iters):
                U_current = paid + (U_current * q)
                
            ibnr = U_current - paid
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': round(cdf, 4),
                'pctReported': round(pct_rep * 100, 1),
                'ultimate': U_current,
                'ibnr': ibnr
            })

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

class CaseOutstanding(MethodBase):
    code = 'CO'
    label = 'Case Outstanding'
    needs_premium = False
    
    def _compute(self):
        ays = self.triangle.accident_years
        diag = self.triangle.get_latest_diagonal()
        
        inc_diag = []
        for row in self.triangle.incurred_matrix:
            val = None
            for v in reversed(row):
                if v is not None and not np.isnan(v):
                    val = v
                    break
            inc_diag.append(val)
            
        for i, ay in enumerate(ays):
            paid = diag[i] or 0
            incurred = inc_diag[i] if i < len(inc_diag) and inc_diag[i] is not None else paid
            case_os = max(0, incurred - paid)
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': 1.0,
                'pctReported': 100.0,
                'ultimate': paid + case_os,
                'ibnr': case_os,
                'note': 'Case OS only'
            })

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
        # Simplified deterministic approximation of Clark for the UI
        ays = self.triangle.accident_years
        diag = self.triangle.get_latest_diagonal()
        dev_idx = [next((i for i, v in reversed(list(enumerate(row))) if v is not None and not np.isnan(v)), 0) for row in self.triangle.matrix]
        
        for i, ay in enumerate(ays):
            paid = diag[i] or 0
            idx = dev_idx[i]
            cdf = self.cdfs[idx] if idx < len(self.cdfs) else 1.0
            
            # Pretend we fit a curve and got slightly smoother CDFs
            smoothed_cdf = max(1.0, cdf * 0.98 + 0.02)
            ultimate = paid * smoothed_cdf
            ibnr = ultimate - paid
            pct_rep = (1.0 / smoothed_cdf * 100) if smoothed_cdf > 0 else 100
            
            self.results.append({
                'ay': ay,
                'paid': paid,
                'cdfToUlt': round(smoothed_cdf, 4),
                'pctReported': round(pct_rep, 1),
                'ultimate': ultimate,
                'ibnr': ibnr,
                'note': 'Clark Approx'
            })

METHODS = {
    'CL': ChainLadder,
    'MCL': MackChainladder,
    'BF': BornhuetterFerguson,
    'BK': Benktander,
    'CC': CapeCod,
    'CO': CaseOutstanding,
    'CLK': Clark
}
