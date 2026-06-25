# Quick Fix Guide: Paid vs. Incurred Architecture

## Immediate Issues to Fix

### 1. NEGATIVE IBNR BUG (Highest Priority)

**Your results show:**
```
BF_INCURRED: IBNR = -$168K ← IMPOSSIBLE
CL_INCURRED: IBNR = -$164K ← IMPOSSIBLE
```

**Root Cause:** Formula error. Check your code:

```python
# ❌ WRONG (you likely have this):
ibnr = reported_claims - ultimate_claims
# This gives negative if ultimate > reported (which it should be)

# ✓ CORRECT:
ibnr = ultimate_claims - reported_claims
# This gives positive, as expected
```

**Verification:**
All of these must be true for every method result:
```python
assert ultimate >= reported, f"Ultimate {ultimate} < Reported {reported} (WRONG)"
assert ibnr >= 0, f"IBNR {ibnr} < 0 (WRONG)"
assert reserve >= 0, f"Reserve {reserve} < 0 (WRONG)"
assert abs((case_os + ibnr) - reserve) < 0.01, f"Reserve decomposition failed"
```

---

### 2. UI Architecture Problem (Medium Priority)

**Current setup:**
```
☑ Chain Ladder
  ☑ Paid    ☑ Incurred
```

**Why this is wrong:**
- Users see two options: pick paid OR incurred
- They think these are "two versions of Chain Ladder"
- Actuarially: paid and incurred are ONE method applied to different inputs
- Friedland: paid is only for diagnostics (Case O/S Development)

**How to fix:**

Option A (Recommended): Remove paid/incurred toggle from most methods
```
METHODS
  ☑ Chain Ladder [uses Incurred triangle]
  ☑ Mack Chain Ladder [uses Incurred triangle]
  ☑ Bornhuetter-Ferguson [uses Incurred triangle]
  ☑ Cape Cod [uses Incurred triangle]
  ☑ Clark Stochastic [uses Incurred triangle]
  ☑ Expected Loss Ratio
  ☑ Case Outstanding Development [DIAGNOSTIC ONLY]
```

Option B: Move paid/incurred to global choice
```
DATA SOURCE FOR ANALYSIS
  ● Use Incurred Triangle (Paid + Case O/S) [RECOMMENDED]
  ○ Use Paid Triangle Only (if case O/S is weak)
  
[Then run ALL selected methods on that one triangle]
```

---

### 3. Results Table: Too Many Rows (Low Priority, but Confusing)

**Current table has:**
```
BF_INCURRED
BF_PAID
CL_INCURRED
CL_PAID
CC_INCURRED
CC_PAID
... (12+ rows)
```

**Better table:**
```
Chain Ladder
Mack Chain Ladder
Bornhuetter-Ferguson
Cape Cod
Clark Stochastic
Expected Loss Ratio
```

**Why:**
- Easier to read (6 rows vs 12+)
- No confusion about which to pick
- Clearer that Case O/S is separate (diagnostic)

---

## Quick Code Fixes

### Fix 1: Correct IBNR Calculation

**In every method (benktander, bornhuetter_ferguson, cape_cod, chain_ladder, clark, etc.):**

```python
# CHANGE THIS:
ibnr = reported_claims - ultimate  # ❌ WRONG

# TO THIS:
ibnr = ultimate - reported_claims  # ✓ CORRECT

# VERIFY:
reserve = ultimate - paid_claims  # Alternative formula
assert abs((case_outstanding + ibnr) - reserve) < 0.01
```

### Fix 2: Verify Reserve Decomposition

After calculating ultimate for ANY method:
```python
# All four of these should be consistent:
reported = paid_claims + case_outstanding
ibnr = ultimate - reported
reserve = case_outstanding + ibnr
reserve_alt = ultimate - paid_claims

# Test:
assert abs(reserve - reserve_alt) < 0.01, "Reserve formulas don't match"
assert abs(ibnr - (reserve - case_outstanding)) < 0.01, "IBNR decomposition wrong"
```

### Fix 3: Add Maturity/Development Score

In your results table, add a column showing development stage:
```python
maturity_score = cdf * 100  # Shows % of claim reported at current age

# For Incurred Triangle:
for age in development_ages:
    cdf = 1 / ldf[age]
    maturity = cdf * 100
    # e.g., maturity = 81.8% means 81.8% reported, 18.2% to come (IBNR)
```

This helps validate your results:
```
If maturity = 81.8%, then IBNR should represent about 18.2% of ultimate
18.2% of $8.1M ≈ $1.47M
```

### Fix 4: Case Outstanding Calculation

Ensure you're calculating it correctly:

```python
case_outstanding = reported_claims - paid_claims

# Verify with actual case O/S from data (if available):
case_from_data = ... # from claims system
if abs(case_outstanding - case_from_data) > 0.05 * case_from_data:
    warning(f"Case O/S mismatch: {case_outstanding} vs {case_from_data}")
```

---

## Architecture Redesign (If Major Rewrite)

### Option A: Comparison Engine (Recommended)

```python
class ReservingComparison:
    def __init__(self, incurred_triangle, paid_triangle):
        self.incurred = incurred_triangle  # Used for all methods
        self.paid = paid_triangle          # Used only for diagnostic
        
    def run_comparison(self, methods_to_run):
        """
        Run multiple methods on the SAME triangle (incurred)
        Purpose: Compare which method is best for this data
        """
        results = {}
        for method_name in methods_to_run:
            if method_name == "Case Outstanding Development":
                # DIAGNOSTIC ONLY
                result = self._case_outstanding_diagnostic()
            else:
                # Standard method applied to incurred triangle
                method = self.get_method(method_name)
                result = method.calculate(self.incurred)
            results[method_name] = result
        return results
    
    def _case_outstanding_diagnostic(self):
        """
        Diagnostic tool: assess case outstanding adequacy
        Uses both paid and incurred separately
        Returns: recommendation (use incurred / adjust to paid)
        """
        case_trend = self.incurred - self.paid
        # Is case declining? → Strong reserves
        # Is case flat? → Weak reserves
        return {"assessment": "strong/weak", "recommendation": "use_incurred/adjust"}
```

### Option B: Sensitivity Engine (Alternative)

```python
class MethodSensitivity:
    def __init__(self, triangle_paid, triangle_incurred):
        self.paid = triangle_paid
        self.incurred = triangle_incurred
        
    def run_method_on_both_triangles(self, method_name):
        """
        Apply ONE method two ways
        Purpose: Sensitivity to triangle choice
        Note: Paid result is for diagnostic only
        """
        method = self.get_method(method_name)
        
        result_incurred = method.calculate(self.incurred)
        result_incurred["type"] = "STANDARD"
        
        result_paid = method.calculate(self.paid)
        result_paid["type"] = "DIAGNOSTIC (if case O/S is weak)"
        
        return {
            "standard": result_incurred,
            "diagnostic": result_paid
        }
```

**Current app:** Looks like Option A but implemented like Option B → confusing

**Recommendation:** Commit to Option A (cleaner for decision-making)

---

## Test Cases for Validation

### Test 1: Identity Checks

```python
def test_reserve_identities(method_result):
    """Every method must satisfy these identities"""
    ult = method_result['ultimate']
    rpt = method_result['reported']
    paid = method_result['paid']
    cos = method_result['case_outstanding']
    ibnr = method_result['ibnr']
    res = method_result['reserve']
    
    # Reported = Paid + Case
    assert abs(rpt - (paid + cos)) < 1, "Reported decomposition failed"
    
    # IBNR = Ultimate - Reported
    assert abs(ibnr - (ult - rpt)) < 1, "IBNR formula failed"
    
    # Reserve = Ultimate - Paid
    assert abs(res - (ult - paid)) < 1, "Reserve formula (1) failed"
    
    # Reserve = Case + IBNR
    assert abs(res - (cos + ibnr)) < 1, "Reserve formula (2) failed"
    
    # Monotonicity: Ultimate >= Reported >= Paid
    assert ult >= rpt >= 0, "Claim monotonicity failed"
    assert ult >= paid >= 0, "Claim monotonicity failed"
    
    # Non-negativity
    assert ibnr >= 0, "IBNR cannot be negative"
    assert res >= 0, "Reserve cannot be negative"
    assert cos >= 0, "Case O/S cannot be negative"
    
    print("✓ All reserve identities satisfied")
```

### Test 2: Comparability

```python
def test_incurred_results_comparable(results_dict):
    """All incurred-based results should be in same ballpark"""
    ultimates = [r['ultimate'] for r in results.values() 
                 if r['triangle_type'] == 'INCURRED']
    
    # All should be within 15% of median
    median = statistics.median(ultimates)
    for ult in ultimates:
        pct_diff = abs(ult - median) / median * 100
        if pct_diff > 15:
            warning(f"Method outlier: ${ult}M vs ${median}M (-{pct_diff}%)")
        else:
            print(f"✓ ${ult}M within range")
```

### Test 3: Maturity Consistency

```python
def test_maturity_validation(results_dict):
    """IBNR% should match (1 - CDF)"""
    for method, result in results.items():
        ultimate = result['ultimate']
        ibnr = result['ibnr']
        cdf = result.get('cdf')
        
        if cdf:
            expected_ibnr_pct = (1 - cdf) * 100
            actual_ibnr_pct = ibnr / ultimate * 100
            
            if abs(expected_ibnr_pct - actual_ibnr_pct) > 1:
                error(f"{method}: CDF says {expected_ibnr_pct}% IBNR, "
                      f"but IBNR is {actual_ibnr_pct}%")
            else:
                print(f"✓ {method} maturity consistent")
```

---

## Checklist Before Deploying

- [ ] **IBNR is always ≥ 0** for all methods
- [ ] **Reserve = Case O/S + IBNR** (identity holds)
- [ ] **Paid ≤ Reported ≤ Ultimate** (monotonicity holds)
- [ ] **Only one row per method** in comparison table (not paid/incurred variants)
- [ ] **Case Outstanding Development is labeled as DIAGNOSTIC** (not an estimate)
- [ ] **Incurred triangle is the default/standard** for all methods
- [ ] **Results table has clear columns:** Method, Reserve, IBNR, Ultimate, Loss Ratio
- [ ] **CV/Confidence intervals only shown for stochastic methods** (Mack, Clark)
- [ ] **Maturity score shown** (CDF × 100%, % of claims reported)
- [ ] **Test suite passes** (identities, comparability, maturity)
- [ ] **Documentation updated** (clarify paid/incurred in UI tooltips)

---

## Talking Points for Actuaries

When presenting this to your actuarial team:

**On the Negative IBNR bug:**
> "We discovered a formula error. IBNR should be Ultimate - Reported (not the reverse). We've corrected this across all methods."

**On the paid/incurred duplication:**
> "We're simplifying the UI. Paid vs. Incurred is a diagnostic choice for Case Outstanding Development, not a method variant. We've moved that analysis to a separate diagnostic panel."

**On the restructured table:**
> "Instead of 12 rows (6 methods × 2 triangles), we now show 6 method results applied to the standard triangle. This makes it clearer which method is best, not which triangle to pick."

**On Case O/S Development:**
> "This is a diagnostic tool, not an estimate. It tells us whether to trust the main estimates or adjust them. It doesn't produce an independent ultimate claim."

---

## Final Priority Order

1. **Urgent:** Fix negative IBNR (formula error)
2. **High:** Verify reserve identities for all methods
3. **High:** Remove paid/incurred toggle from comparison UI
4. **Medium:** Restructure results table (6 rows, not 12+)
5. **Medium:** Add maturity/CDF score to results
6. **Low:** Separate Case O/S diagnostic into its own panel
7. **Polish:** Add tooltips explaining paid vs. incurred choice

---

## References

- Friedland Chapter 7: Development Technique (paid vs. incurred, pages 84–130)
- Friedland Chapter 12: Case Outstanding Development (diagnostic use, pages 265–282)
- Standard actuarial practice: Incurred is default, paid is alternative
