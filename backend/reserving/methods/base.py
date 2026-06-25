import numpy as np
import math

class MethodBase:
    code = 'BASE'
    label = 'Base Method'
    needs_premium = False
    requires_paid_triangle = False
    requires_incurred_triangle = False
    supports_source_selection = True
    
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
        self.matrix = None
        
    def fit(self, triangle, params, custom_ldfs, matrix=None):
        self.triangle = triangle
        self.params = params
        self.ldfs = custom_ldfs
        from reserving.core.development_engine import DevelopmentEngine
        if len(custom_ldfs) > 0:
            self.cdfs = list(DevelopmentEngine.calculate_cdfs(custom_ldfs[:-1], tail_factor=custom_ldfs[-1]))
        else:
            self.cdfs = []
        self.results = []
        self.matrix = matrix if matrix is not None else triangle.matrix
        self._compute()
        
    def _compute(self):
        raise NotImplementedError()
        
    def get_results(self):
        return self.results
        
    def get_total_ibnr(self):
        return sum(r.get('ibnr', 0) for r in self.results)
        
    def get_total_ultimate(self):
        return sum(r.get('ultimate', 0) for r in self.results)

    def get_latest_diagonal(self, matrix=None):
        """
        Extracts the latest non-null claims diagonal values from a given matrix.
        Defaults to the currently active matrix.
        """
        m = matrix if matrix is not None else self.matrix
        if m is None:
            return []
        return [next((v for v in reversed(row) if v is not None and not np.isnan(v)), 0.0) for row in m]

    def get_development_indices(self, matrix=None):
        """
        Extracts the index of the latest non-null development period for each row in a matrix.
        """
        m = matrix if matrix is not None else self.matrix
        if m is None:
            return []
        return [next((i for i, v in reversed(list(enumerate(row))) if v is not None and not np.isnan(v)), 0) for row in m]

    def get_incurred_diagonal(self):
        """
        Extracts the latest non-null diagonal values from the incurred matrix if available.
        Otherwise falls back to the active matrix (paid diagonal).
        """
        if hasattr(self.triangle, 'incurred_matrix') and self.triangle.incurred_matrix is not None and len(self.triangle.incurred_matrix) > 0:
            return self.get_latest_diagonal(self.triangle.incurred_matrix)
        return self.get_latest_diagonal(self.matrix)
