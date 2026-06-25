import pytest
from reserving.core.triangle import Triangle

@pytest.mark.unit
def test_triangle_properties(sample_triangle):
    t = sample_triangle
    assert t._format is not None
    assert len(t.accident_years) > 0
    assert min(t.accident_years) <= max(t.accident_years)
    assert len(t.dev_ages) > 0
    
    summary = t.get_summary()
    assert summary['totalPaid'] > 0
    assert summary['hasPremium'] is True
    
    ldfs = t.compute_ldfs()
    assert len(ldfs) > 0
    assert 'volumeWeighted' in ldfs[0]
