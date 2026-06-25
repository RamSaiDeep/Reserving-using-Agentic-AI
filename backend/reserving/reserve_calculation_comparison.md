# Actuarial Reserve Calculation Comparison Report

This report documents how ultimate claims, reserves, and IBNR are currently calculated across all 9 reserving methods, summarizes clamping behaviors, and details inconsistencies identified across the codebase.

---

## 1. Calculation Details by Reserving Method

| Method Code | Method Name | Ultimate Calculation ($U$) | Reserve Calculation ($R$) | IBNR Calculation ($I$) | Clamping Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CL** | Chain Ladder | $Paid \times CDF$ | *None* (calculated in standardizer) | $U - Paid$ | None inside method. Clamped to reported in standardizer. |
| **MCL** | Mack Chain Ladder | Projected CL ultimate: $Paid \times CDF$ | *None* (calculated in standardizer) | $U - Paid$ | Clamped to incurred diagonal: if $U < Inc$, $U = Inc$. |
| **BF** | Bornhuetter-Ferguson | $(U_{apriori} \times \%Unreported) + (Claims_{diag} \times \%Reported)$ | *None* (calculated in standardizer) | $U - Claims_{diag}$ | Clamped to incurred diagonal: if $U < Inc$, $U = Inc$. |
| **CC** | Cape Cod | $EarnedPremium \times CapeCodELR$ | *None* (calculated in standardizer) | $U - Claims_{diag}$ | Clamped to incurred diagonal: if $U < Inc$, $U = Inc$. |
| **BK** | Benktander | $(U_{iterated} \times \%Unreported) + (Claims_{diag} \times \%Reported)$ | *None* (calculated in standardizer) | $U - Claims_{diag}$ | Clamped to incurred diagonal: if $U < Inc$, $U = Inc$. |
| **CO** | Case Outstanding | $Paid + (CaseOS \times CaseCDF)$ | $CaseOS \times CaseCDF$ | $U - Incurred$ | None inside method. Clamped to reported in standardizer. |
| **CLK** | Clark Stochastic | $Paid \times SmoothedCDF$ | *None* (calculated in standardizer) | $U - Paid$ | Clamped to incurred diagonal: if $U < Inc$, $U = Inc$. |
| **ELR** | Expected Loss Ratio | $EarnedPremium \times ELR_{apriori}$ | *None* (calculated in standardizer) | $U - Paid$ | Clamped to incurred diagonal: if $U < Inc$, $U = Inc$. |
| **FS** | Frequency-Severity | Depends on approach: count/sev dev, frequency inflation, or disposal paid | *None* (calculated in standardizer) | $U - Paid$ | Clamped to incurred diagonal: if $U < Inc$, $U = Inc$. |

*Note: $Claims_{diag}$ refers to the diagonal of the active source triangle (either Paid or Incurred).*

---

## 2. Inconsistencies & Architecture Gaps Found

### A. Conceptual Collision in the Definition of "IBNR"
There is a major inconsistency in how the term `ibnr` is defined and computed:
1.  **IBNR = Ultimate - Paid (Reserve):** 
    In `ChainLadder`, `MackChainladder`, `ExpectedLossRatio`, `Clark`, and `FrequencySeverity`, the code computes IBNR in the method results as:
    `ibnr = ultimate - paid`
    This mathematically represents the **Total Reserve** (claims unpaid to date), not IBNR.
2.  **IBNR = Ultimate - Active Diagonal:** 
    In `BornhuetterFerguson`, `CapeCod`, and `Benktander`, IBNR is calculated as:
    `ibnr = ultimate - claims_val`
    *   If run on Paid data: this equals $Ultimate - Paid$ (Total Reserve).
    *   If run on Incurred data: this equals $Ultimate - Incurred$ (True IBNR).
3.  **IBNR = Ultimate - Incurred (True IBNR):** 
    In `CaseOutstanding`, the code computes `ibnr = ultimate - incurred` (where `incurred` is the Incurred diagonal).
4.  **Standardizer Override:** 
    Regardless of what the concrete method calculates as `ibnr`, `standardizer.py` overrides the field and computes:
    *   `ibnr_ay = max(0.0, u_ay - r_ay)` (where `r_ay` is the Incurred/Reported diagonal).
    *   `reserve_ay = u_ay - p_ay` (where `p_ay` is the Paid diagonal).
    
This means that although the individual methods produce a field named `ibnr` that often actually holds the *Total Reserve*, the API contract and frontend receive the standardized definition where `ibnr` is strictly **Ultimate - Incurred** and `reserve` is strictly **Ultimate - Paid**.

### B. Redundant Clamping Logic
Clamping the ultimate projection to be at least the reported/incurred value is implemented in two places for almost all methods:
1.  Inside the individual methods `_compute` methods (e.g. `BF`, `CC`, `BK`, `MCL`, `CLK`, `ELR`, `FS`).
2.  Inside `standardizer.py` (lines 72-74):
    ```python
    if u_ay < r_ay:
        u_ay = r_ay
    ```
This redundancy should eventually be consolidated into a single validation helper once approved.

### C. Active Diagonal Source vs Incurred Diagonal Clamping
When methods are run on the Paid triangle, they search for `incurred_matrix` to retrieve the incurred diagonal for clamping. If `incurred_matrix` is not present, they fall back to the Paid diagonal. This logic is copy-pasted across all methods and standardizer:
```python
if hasattr(self.triangle, 'incurred_matrix') and self.triangle.incurred_matrix:
    for row in self.triangle.incurred_matrix:
        val = next((v for v in reversed(row) if v is not None and not np.isnan(v)), 0.0)
        inc_diag.append(val)
else:
    inc_diag = list(diag)
```
This has been refactored in Phase 3 to use the centralized `get_incurred_diagonal()` helper, removing this duplication.
