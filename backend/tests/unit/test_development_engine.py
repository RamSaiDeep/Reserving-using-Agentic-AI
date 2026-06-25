import pytest
import numpy as np
import pandas as pd
from reserving.core.development_engine import DevelopmentEngine

@pytest.fixture
def company_data(sample_df):
    # Filter for company 13587
    df_company = sample_df[sample_df['GRCODE'] == 13587]
    # Mask data after valuation year 1997
    df_masked_company = df_company[df_company['DevelopmentYear'] <= 1997]
    
    paid_masked = df_masked_company.pivot_table(
        index='AccidentYear',
        columns='DevelopmentLag',
        values='CumPaidLoss_C',
        aggfunc='sum'
    )
    return paid_masked

@pytest.mark.unit
def test_ata_factors_calculation(company_data):
    paid_masked = company_data
    factors_nb = pd.DataFrame(index=paid_masked.index)
    for col in range(paid_masked.shape[1] - 1):
        current = paid_masked.iloc[:, col]
        nxt = paid_masked.iloc[:, col + 1]
        factors_nb[f"{col+1}->{col+2}"] = nxt / current
        
    factors_engine = DevelopmentEngine.calculate_ata_factors(paid_masked)
    np.testing.assert_allclose(factors_nb.values, factors_engine.values, rtol=1e-7, equal_nan=True)

@pytest.mark.unit
def test_ldf_averages(company_data):
    paid_masked = company_data
    factors_engine = DevelopmentEngine.calculate_ata_factors(paid_masked)
    
    # Calculate hand-crafted notebook averages
    factors_nb = pd.DataFrame(index=paid_masked.index)
    for col in range(paid_masked.shape[1] - 1):
        current = paid_masked.iloc[:, col]
        nxt = paid_masked.iloc[:, col + 1]
        factors_nb[f"{col+1}->{col+2}"] = nxt / current
        
    averages_nb = {}
    for col in factors_nb.columns:
        valid_factors = factors_nb[col].dropna().values
        simple = valid_factors.mean() if len(valid_factors) > 0 else 1.0
        geom = np.prod(valid_factors) ** (1 / len(valid_factors)) if len(valid_factors) > 0 else 1.0
        if len(valid_factors) >= 3:
            medial = np.sort(valid_factors)[1:-1].mean()
        else:
            medial = simple
        averages_nb[col] = {"Simple": simple, "Geometric": geom, "Medial": medial}
    averages_nb_df = pd.DataFrame(averages_nb)
    
    avg_simple = DevelopmentEngine.calculate_average_ldfs(factors_engine, method="simple")
    avg_geom = DevelopmentEngine.calculate_average_ldfs(factors_engine, method="geometric")
    avg_medial = DevelopmentEngine.calculate_average_ldfs(factors_engine, method="medial")
    
    for col in factors_nb.columns:
        assert np.isclose(averages_nb_df.loc["Simple", col], avg_simple[col])
        assert np.isclose(averages_nb_df.loc["Geometric", col], avg_geom[col])
        assert np.isclose(averages_nb_df.loc["Medial", col], avg_medial[col])

@pytest.mark.unit
def test_cdfs_calculation(company_data):
    paid_masked = company_data
    factors_engine = DevelopmentEngine.calculate_ata_factors(paid_masked)
    avg_simple = DevelopmentEngine.calculate_average_ldfs(factors_engine, method="simple")
    
    selected_ldfs_nb = avg_simple.copy()
    selected_ldfs_nb["Tail"] = 1.0
    
    cdfs_nb = []
    factors_list = selected_ldfs_nb.values
    for i in range(len(factors_list)):
        cdfs_nb.append(np.prod(factors_list[i:]))
    cdfs_nb = pd.Series(cdfs_nb)
    
    cdfs_engine = DevelopmentEngine.calculate_cdfs(avg_simple.values, tail_factor=1.0)
    np.testing.assert_allclose(cdfs_nb.values, cdfs_engine, rtol=1e-7)

@pytest.mark.unit
def test_ultimate_projection(company_data):
    paid_masked = company_data
    factors_engine = DevelopmentEngine.calculate_ata_factors(paid_masked)
    avg_simple = DevelopmentEngine.calculate_average_ldfs(factors_engine, method="simple")
    cdfs_engine = DevelopmentEngine.calculate_cdfs(avg_simple.values, tail_factor=1.0)
    
    cdfs_nb = pd.Series(cdfs_engine, index=paid_masked.columns)
    
    ultimates_nb = []
    diag_paid = []
    matching_cdfs = []
    
    for ay in paid_masked.index:
        row = paid_masked.loc[ay].dropna()
        latest_age = row.index[-1]
        latest_value = row.iloc[-1]
        cdf = cdfs_nb.loc[latest_age]
        
        ultimates_nb.append(latest_value * cdf)
        diag_paid.append(latest_value)
        matching_cdfs.append(cdf)
        
    ultimates_engine = DevelopmentEngine.project_ultimate(diag_paid, matching_cdfs)
    np.testing.assert_allclose(ultimates_nb, ultimates_engine, rtol=1e-7)
