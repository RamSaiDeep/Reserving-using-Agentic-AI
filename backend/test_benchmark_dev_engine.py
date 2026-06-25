import os
import sys
import numpy as np
import pandas as pd

# Add backend directory to sys.path so we can import reserving
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from reserving.core.development_engine import DevelopmentEngine
from reserving.core.averages import volume_weighted_average, simple_average, geometric_average, medial_average
from reserving.core.cdfs import calculate_cdfs
from reserving.core.reserves import calculate_unpaid_claim_estimate, calculate_case_outstanding, calculate_ibnr

def main():
    print("======================================================================")
    # 1. Load Data
    csv_path = r"c:\Reserving-using-Agentic-AI\data\df_masked.csv"
    df = pd.read_csv(csv_path)
    
    # Filter for company 13587
    df_company = df[df['GRCODE'] == 13587]
    
    # Build cumulative paid triangle
    paid_pivot = df_company.pivot_table(
        index='AccidentYear',
        columns='DevelopmentLag',
        values='CumPaidLoss_C',
        aggfunc='sum'
    )
    
    # Mask data after valuation year 1997
    df_masked_company = df_company[df_company['DevelopmentYear'] <= 1997]
    
    paid_masked = df_masked_company.pivot_table(
        index='AccidentYear',
        columns='DevelopmentLag',
        values='CumPaidLoss_C',
        aggfunc='sum'
    )
    
    incurred_masked = df_masked_company.pivot_table(
        index='AccidentYear',
        columns='DevelopmentLag',
        values='IncurLoss_C',
        aggfunc='sum'
    )
    
    print("Cumulative Paid Triangle Built. Shape:", paid_masked.shape)
    
    # 2. ATA Calculation Benchmark
    print("\n--- BENCHMARK 1: ATA Factors Calculation ---")
    factors_nb = pd.DataFrame(index=paid_masked.index)
    for col in range(paid_masked.shape[1] - 1):
        current = paid_masked.iloc[:, col]
        nxt = paid_masked.iloc[:, col + 1]
        factors_nb[f"{col+1}->{col+2}"] = nxt / current
        
    factors_engine = DevelopmentEngine.calculate_ata_factors(paid_masked)
    
    # Assert they are equal
    np.testing.assert_allclose(factors_nb.values, factors_engine.values, rtol=1e-7, equal_nan=True)
    print("Success: ATA Factors calculation is identical to the notebook.")
    
    # 3. LDF Averages Benchmark
    print("\n--- BENCHMARK 2: LDF Averages ---")
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
    
    # Assert values match
    for col in factors_nb.columns:
        assert np.isclose(averages_nb_df.loc["Simple", col], avg_simple[col])
        assert np.isclose(averages_nb_df.loc["Geometric", col], avg_geom[col])
        assert np.isclose(averages_nb_df.loc["Medial", col], avg_medial[col])
        
    print("Success: LDF Averages (Simple, Geometric, Medial) match the notebook exactly.")
    
    # 4. CDFs Benchmark
    print("\n--- BENCHMARK 3: CDFs Calculation ---")
    selected_ldfs_nb = averages_nb_df.loc["Simple"].copy()
    selected_ldfs_nb["Tail"] = 1.0
    
    cdfs_nb = []
    factors_list = selected_ldfs_nb.values
    for i in range(len(factors_list)):
        cdfs_nb.append(np.prod(factors_list[i:]))
    cdfs_nb = pd.Series(cdfs_nb)
    
    cdfs_engine = DevelopmentEngine.calculate_cdfs(averages_nb_df.loc["Simple"].values, tail_factor=1.0)
    
    np.testing.assert_allclose(cdfs_nb.values, cdfs_engine, rtol=1e-7)
    print("Success: CDFs calculations match the notebook exactly.")
    
    # 5. Ultimate Projection Benchmark
    print("\n--- BENCHMARK 4: Ultimate Projection ---")
    cdfs_nb.index = paid_masked.columns
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
    print("Success: Ultimate Projections match the notebook exactly.")
    print("======================================================================")

# Execute main at module import time so it runs during pytest collection
main()
