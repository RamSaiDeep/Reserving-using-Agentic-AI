import pytest
import numpy as np
from reserving.methods import METHODS

@pytest.mark.unit
@pytest.mark.parametrize("method_code", list(METHODS.keys()))
def test_method_direct_fit(sample_triangle, method_code):
    t = sample_triangle
    method_cls = METHODS[method_code]
    method = method_cls()
    
    # Define common configuration parameters
    params = {
        "elr": 65.0,
        "approach": "approach1",
        "inflationRate": 3.0,
        "aPrioriSource": "paid",
        "tail_factor": 1.0,
    }
    
    # Custom LDFs matching development ages
    custom_ldfs = [1.0] * len(t.dev_ages)
    
    # Fit the model
    method.fit(t, params, custom_ldfs)
    
    # Assert result structure is populated
    results = method.get_results()
    assert isinstance(results, list)
    assert len(results) == len(t.accident_years)
    
    for r in results:
        assert "ay" in r
        assert "ultimate" in r
        assert "ibnr" in r
        assert isinstance(r["ultimate"], (int, float, np.integer, np.floating))
        assert isinstance(r["ibnr"], (int, float, np.integer, np.floating))
        
    assert isinstance(method.get_total_ibnr(), (int, float, np.integer, np.floating))
    assert isinstance(method.get_total_ultimate(), (int, float, np.integer, np.floating))
