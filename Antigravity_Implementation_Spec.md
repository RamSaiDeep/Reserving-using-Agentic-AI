# Antigravity Implementation Guide - Reserving Methods
## From Friedland "Estimating Unpaid Claims Using Basic Techniques" (CAS, 2010)

---

## 1. BENKTANDER.PY (Bornhuetter-Ferguson)

### Method Name
`benktander_reserve()` or similar

### Inputs
- `reported_claims`: Array of cumulative reported claims at latest evaluation date
- `ulf`: Array of loss development factors (from chain ladder)
- `expected_ultimate`: Array of expected ultimate claims (ELR × Premium)
- `case_outstanding`: Array of case outstanding (component of reported)
- `paid_claims`: Array of cumulative paid claims

### Outputs
**Must Return**:
1. `reserve`: Final reserve amount (by accident year)
2. `ibnr`: IBNR amount (by accident year)
3. `case_outstanding`: Case outstanding passed through (by accident year)
4. `ultimate`: Projected ultimate claims (by accident year)

### Correct Calculation

```python
# Benktander uses same blending as Bornhuetter-Ferguson
# Ultimate = (Percent Unreported × Expected Ultimate) + (Percent Reported × Reported)

cdf = 1 / ulf  # Cumulative Development Factor
percent_unreported = cdf
percent_reported = 1 - cdf

ultimate = (percent_unreported * expected_ultimate) + (percent_reported * reported_claims)
ibnr = ultimate - reported_claims
reserve = ultimate - paid_claims

# Verify: case_outstanding should be component of reported_claims
# reserve should equal case_outstanding + ibnr
```

### Key Points
- Benktander = Bornhuetter-Ferguson in most implementations
- CDF acts as credibility weight
- Blend between ELR (via expected_ultimate) and CL (via reported_claims)
- Works at current development age, not looking back

### Friedland Reference
Chapter 9, Pages 152-173

---

## 2. BORNHUETTER_FERGUSON.PY

### Method Name
`bornhuetter_ferguson_reserve()` or similar

### Inputs
- `reported_claims`: Cumulative reported claims at latest evaluation date
- `ulf`: Loss development factor at current development age
- `expected_ultimate`: Expected ultimate claims (ELR × Earned Premium)
- `case_outstanding`: Case outstanding at evaluation date
- `paid_claims`: Cumulative paid claims at evaluation date

### Outputs
**Must Return**:
1. `reserve`: Final reserve (case + IBNR)
2. `ibnr`: Future development component
3. `case_outstanding`: Case outstanding value
4. `ultimate`: Projected ultimate

### Correct Calculation

```python
# Bornhuetter-Ferguson blending
cdf = 1 / ulf
percent_unreported = cdf
percent_reported = 1 - cdf

# This is the core BF formula
ultimate = (percent_unreported * expected_ultimate) + (percent_reported * reported_claims)

# Decompose into components
ibnr = ultimate - reported_claims
reserve = ultimate - paid_claims

# Verify relationships:
# reserve = case_outstanding + ibnr
# reported_claims = paid_claims + case_outstanding
```

### Key Points
- **Most important method** - widely used by actuaries
- Credibility weight = CDF (proportion unreported)
  - Early ages: High CDF → ELR dominates (appropriate for young claims)
  - Mature ages: Low CDF → Reported dominates (appropriate for mature claims)
- Always produces reasonable middle-ground between Chain Ladder and ELR
- Independent of case outstanding adequacy

### Sensitivity Analysis
Test with different LULFs (tail factors) to see impact on CDF.

### Friedland Reference
Chapter 9, Pages 152-173

---

## 3. CAPE_COD.PY

### Method Name
`cape_cod_reserve()` or similar

### Inputs
- `reported_claims`: Array of cumulative reported claims (all accident years at current age)
- `earned_premium`: Array of earned premium (all accident years)
- `ulf`: Array of loss development factors (by accident year or one factor)
- `initial_expected_lr`: Initial estimate of loss ratio (e.g., 0.65)

### Outputs
**Must Return**:
1. `adjusted_expected_lr`: The calculated loss ratio (refined estimate)
2. `expected_ultimate`: Array of expected ultimate by year
3. `reserve`: Array of final reserve by accident year
4. `ibnr`: Array of IBNR by accident year
5. `ultimate`: Array of projected ultimate by accident year

### Correct Calculation

```python
# Step 1: Calculate expected ultimate using initial LR
expected_ultimate_basic = initial_expected_lr * earned_premium

# Step 2: Calculate reported as % of expected ultimate
pct_reported = reported_claims / expected_ultimate_basic

# Step 3: Calculate adjusted LR (exposure-credibility weighted)
adjusted_expected_lr = sum(reported_claims) / sum(earned_premium * initial_expected_lr)

# Step 4: Recalculate ultimate with adjusted LR
expected_ultimate = adjusted_expected_lr * earned_premium

# Step 5: Calculate components
ibnr = expected_ultimate - reported_claims
reserve = expected_ultimate - paid_claims

# Optional: Iterate Steps 2-4 until convergence
```

### Key Points
- Refines loss ratio by comparing actual reported to expected across ALL years
- Exposure-credibility weighting (unlike ELR which is single-year judgment)
- Useful when underwriting guidance is consistent across years
- More stable loss ratio than pure ELR if applied across years

### Iteration
Can iterate Steps 3-4 until adjusted_lr converges (typically 2-3 iterations).

### Friedland Reference
Chapter 10, Pages 174-191

---

## 4. CASE_OUTSTANDING.PY

### Method Name
`case_outstanding_development_reserve()` or similar

### Inputs
- `cumulative_paid`: Cumulative paid claims by accident year and age
- `case_outstanding`: Case outstanding by accident year and age
- `claim_counts`: Reported claim counts by accident year and age
- `paid_ulf`: Loss development factors for PAID claims
- `reported_ulf`: Loss development factors for REPORTED (incurred) claims

### Outputs
**Must Return**:
1. `ultimate_paid`: Projected ultimate paid claims
2. `ultimate_case_outstanding`: Projected ultimate case outstanding
3. `ultimate`: Ultimate claims (paid + case)
4. `reserve`: Final reserve
5. `ibnr`: IBNR component
6. `case_outstanding`: Case component

### Correct Calculation

```python
# Method 1: Separate analysis of Paid vs Case
reported_claims = cumulative_paid + case_outstanding

# Option A: If case outstanding is WEAK (under-reserving pattern)
# Use paid development + estimated final case
ultimate_paid = cumulative_paid * paid_ulf
projected_final_case = cumulative_paid * (final_case_to_paid_ratio)  # judgment
ultimate = ultimate_paid + projected_final_case

# Option B: If case outstanding is STRONG (improving adequacy)
# Use reported (incurred) development
ultimate = reported_claims * reported_ulf

# Either way:
ibnr = ultimate - reported_claims
reserve = ultimate - cumulative_paid
case_outstanding = ultimate - ultimate_paid  # residual
```

### Key Points
- **Diagnostic first**: Use to assess whether case O/S is strong or weak
- Strong case O/S: Case reserves increase as claim matures → Use reported development
- Weak case O/S: Case reserves don't improve → Use paid development + estimated final case
- Requires TWO development triangles (paid and case separately)
- Claim counts can help validate projected case outstanding

### Claim Count Validation
```python
# Estimate ultimate case per claim
ultimate_case_per_claim = ultimate_case_outstanding / ultimate_claim_counts

# Does this make sense compared to current case per claim?
current_case_per_claim = case_outstanding / open_claim_counts
```

### Friedland Reference
Chapter 12, Pages 265-282

---

## 5. CHAIN_LADDER.PY

### Method Name
`chain_ladder_reserve()` or similar

### Inputs
- `development_triangle`: 2D array [accident_years, development_ages]
  - Contains cumulative reported claims (paid + case outstanding)
- `paid_development_triangle`: Optional, for paid-only analysis
- `case_outstanding_triangle`: Optional, for case-only analysis
- `tail_factor`: Assumed LDF beyond observed data (default 1.005-1.010)
- `selection_method`: 'simple_average', 'weighted_average', 'exclude_extremes', 'manual'
- `selected_ldfs`: If manual selection, array of chosen LDFs

### Outputs
**Must Return**:
1. `ultimate`: Projected ultimate claims (by accident year)
2. `ibnr`: IBNR (by accident year)
3. `case_outstanding`: Case outstanding (by accident year)
4. `reserve`: Final reserve (by accident year)
5. `factors`: Age-to-age factors calculated
6. `ldfs`: Loss development factors calculated
7. `cdfs`: Cumulative development factors
8. `ulf`: ULIMATELY needed LDF at current age (for BF blending)

### Correct Calculation

```python
# Step 1: Calculate age-to-age factors
for each development age:
    af[age] = reported[age] / reported[age-1]

# Step 2: Select average factors (apply judgment)
selected_af[age] = choice of:
    - simple average of af[age] across years
    - weighted average: sum(reported[prior] * af[i]) / sum(reported[prior])
    - exclude top and bottom outlier
    - manual selection based on trends

# Step 3: Calculate LDF (working backward from tail)
ldf[ultimate_age] = selected_af[ultimate] * tail_factor
for age in reverse from (ultimate-1) to current_age:
    ldf[age] = selected_af[age] * ldf[age+1]

# Step 4: Calculate CDF
cdf[age] = 1 / ldf[age]

# Step 5: Project ultimate
ultimate = reported[current_age] * ldf[current_age]

# Step 6: Calculate components
ibnr = ultimate - reported
reserve = ultimate - paid
case_outstanding = reported - paid  # or use actual if available
```

### Key Selections

**1. Paid vs. Incurred**:
- Use PAID if adjusters consistently over/under reserve
- Use INCURRED (reported) if case outstanding is reliable
- Default: Use INCURRED for most lines

**2. Average Method**:
- Simple average: Stable, predictable lines
- Weighted average: Lines with changing premium volume
- Exclude extremes: Lines with occasional anomalies
- Manual: When trends are evident

**3. Tail Factor**:
- Default: 1.005-1.010 for most lines
- For long-tail (GL, WC): Use external benchmarks (1.005-1.050)
- For short-tail: Use 1.000 if development is complete
- Test sensitivity (±2-3% tail factor range)

### Validation
```python
# Compare to prior year projection
prior_year_ult = prior_year_projection
actual_paid_development = actual_paid_year - paid_year_minus_1
prior_year_ibnr = prior_year_projection - prior_year_reported

# This diagnostic helps refine LDF selection
```

### Friedland Reference
Chapter 7, Pages 84-130

---

## 6. CLARK.PY

### Method Name
`clarks_reserve()` or similar

### Inputs
- `development_triangle`: Cumulative reported claims [accident_years, development_ages]
- `development_ages`: Array of age values (e.g., [12, 24, 36, ...])
- `distribution_type`: 'lognormal', 'weibull', 'inverse_power_law'
- `initial_ulf`: Optional, initial estimate to refine

### Outputs
**Must Return**:
1. `parameters`: Fitted distribution parameters (logmean, logstd) or (shape, scale)
2. `fitted_cdf`: Cumulative distribution function values by age
3. `fitted_ldf`: LDFs from fitted distribution
4. `ultimate`: Projected ultimate claims
5. `ibnr`: IBNR
6. `case_outstanding`: Case outstanding
7. `reserve`: Final reserve
8. `tail_ldf`: Tail factor derived from distribution

### Correct Calculation (Lognormal Example)

```python
# Step 1: Get chain ladder LDF and ultimate estimate
initial_ult = reported * initial_ulf  # from chain ladder

# Step 2: Calculate % reported at each age
pct_reported = reported / initial_ult

# Step 3: Fit lognormal distribution to % reported
# Lognormal CDF: F(x) = Φ((log(x) - μ) / σ)
# where Φ is standard normal CDF

from scipy.stats import lognorm
params = lognorm.fit(development_ages, pct_reported)
logmean = params[1]
logstd = params[2]

# Step 4: Generate smooth fitted CDF
fitted_cdf = lognorm.cdf(development_ages, logstd, loc=0, scale=exp(logmean))

# Step 5: Calculate smooth LDFs
fitted_ldf = 1 / fitted_cdf

# Step 6: Extend tail using distribution
tail_age = last_observed_age + k
tail_cdf = lognorm.cdf(tail_age, logstd, loc=0, scale=exp(logmean))
tail_ldf = 1 / tail_cdf

# Step 7: Project ultimate using fitted LDF at current age
ultimate = reported[current_age] * fitted_ldf[current_age]

# Step 8: Calculate components
ibnr = ultimate - reported
reserve = ultimate - paid
```

### Key Points
- Smooths jagged LDF patterns from chain ladder
- Better tail estimation than linear extrapolation
- Mathematically defensible (fits actual development data)
- More complex than chain ladder but valuable for long-tail lines

### Distribution Selection
- **Lognormal**: Most flexible, good for most insurance lines
- **Weibull**: Alternative if development is asymmetric
- **Inverse Power Law**: Simple, good for certain patterns

### Validation
```python
# Compare smooth LDFs to chain ladder LDFs
# Should be similar in middle ages, smoother overall
# Tail should be reasonable (typically 1.005-1.020)
```

### Friedland Reference
Chapter 7, Pages 84-130 (advanced topic, may reference Clark papers)

---

## 7. EXPECTED_LOSS_RATIO.PY

### Method Name
`expected_loss_ratio_reserve()` or similar

### Inputs
- `earned_premium`: Earned premium for accident year
- `expected_loss_ratio`: Judgment-based expected loss ratio (e.g., 0.65)
- `reported_claims`: Cumulative reported claims at valuation date
- `paid_claims`: Cumulative paid claims at valuation date
- `case_outstanding`: Case outstanding at valuation date

### Outputs
**Must Return**:
1. `ultimate`: Expected ultimate claims
2. `ibnr`: IBNR
3. `reserve`: Final reserve
4. `case_outstanding`: Case outstanding (passed through)
5. `loss_ratio`: Actual loss ratio based on ultimate

### Correct Calculation

```python
# Step 1: Estimate expected loss ratio (JUDGMENT)
# Consider:
# - Prior year actual loss ratios
# - Underwriting guidance / pricing intent
# - Inflation trends (trend factor)
# - Frequency changes (count change)
# - Severity changes (per-claim increase)
# - Mix of business changes
# - Reinsurance cessions
# - External benchmarks (ISO, industry)

expected_loss_ratio = base_underwriting_lr \
    * inflation_factor \
    * frequency_trend \
    * severity_trend \
    * mix_adjustment \
    / reinsurance_cession_pct

# Step 2: Calculate expected ultimate
ultimate = expected_loss_ratio * earned_premium

# Step 3: Calculate IBNR
ibnr = ultimate - reported_claims

# Step 4: Calculate reserve
reserve = ultimate - paid_claims

# Verify:
actual_loss_ratio = ultimate / earned_premium
```

### Key Judgment Points

```python
# Example adjustment factors:
inflation_factor = 1.05  # 5% inflation
frequency_trend = 1.00   # Flat frequency
severity_trend = 1.03    # 3% severity increase
mix_adjustment = 1.00    # No mix shift
cession_pct = 0.00       # No reinsurance

# Or more sophisticated:
if line == 'GL':
    # GL typically experiencing social inflation
    severity_trend = 1.08  # 8% annual
    frequency_trend = 0.98  # Slightly declining frequency

elif line == 'WC':
    # WC may have legislative changes
    severity_trend = 1.04
    frequency_trend = 0.95  # Safety improvements
    
# Then apply to historical experience
```

### Sensitivity Analysis
Test ±1% to ±3% change in ELR to see impact.

### When to Use
- Immature accident years with little development history
- Known major environmental changes
- Validation/sanity check against other methods
- Catastrophe lines with high volatility

### Friedland Reference
Chapter 8, Pages 131-151

---

## 8. MACK_CHAIN_LADDER.PY

### Method Name
`mack_chain_ladder_reserve()` or similar

### Inputs
- `development_triangle`: Cumulative reported claims [accident_years, development_ages]
- `paid_development_triangle`: Optional, separate paid analysis
- Inputs same as Chain Ladder plus variance/confidence inputs

### Outputs
**Must Return** (everything from Chain Ladder plus):
1. `ultimate`: Projected ultimate claims
2. `ibnr`: IBNR
3. `reserve`: Final reserve
4. `case_outstanding`: Case outstanding
5. `process_variance`: Process variance of ultimate
6. `parameter_variance`: Parameter variance (estimation uncertainty)
7. `total_variance`: Sum of process + parameter variance
8. `standard_error`: Square root of variance
9. `coefficient_of_variation`: SE / Ultimate (as %)
10. `confidence_intervals`: Dict of percentile ranges

### Correct Calculation

```python
# Step 1-6: Standard Chain Ladder calculation
ultimate, ibnr, reserve = chain_ladder(...)

# Step 2: Calculate variance of age-to-age factors
# For each transition age:
variance_af = []
for age in development_ages[:-1]:
    af_values = [develop_triangle[year, age+1] / develop_triangle[year, age] 
                 for year in range(num_years)]
    mean_af = average(af_values)
    var = sum((af - mean_af)^2 * develop_triangle[year, age]) / (n-1)
    variance_af.append(var)

# Step 3: Calculate process variance
# Mack formula (simplified):
process_var = ultimate^2 * sum(variance_af / (af^2 * prior_paid^2))

# Step 4: Calculate parameter variance
# More complex, involves covariance of AF estimates
parameter_var = ... # See technical papers

# Step 5: Total variance
total_variance = process_variance + parameter_variance
standard_error = sqrt(total_variance)
cv = standard_error / ultimate

# Step 6: Calculate confidence intervals
percentiles = [25, 50, 75, 95]
confidence_intervals = {}
for p in percentiles:
    z_score = norm.ppf(p/100)
    confidence_intervals[f'{p}pct'] = ultimate + z_score * standard_error
```

### Key Outputs Interpretation

```python
# Example output:
ultimate = 1000000
standard_error = 50000
coefficient_of_variation = 0.05  # 5%

# Interpretation:
# There is 68% probability (±1 SE) that ultimate will be $950k - $1.05m
# There is 95% probability (±1.96 SE) that ultimate will be $902k - $1.098m

# For reserve calculation:
# Regulatory minimum (75th percentile): ultimate + 0.674 * SE
# Conservative estimate (95th percentile): ultimate + 1.645 * SE
```

### Key Assumptions (Mack)
1. No structural changes in development patterns
2. Independence across accident years
3. Model is correct specification
4. Variance not influenced by mean (homoscedasticity)

### When Assumptions Fail
- Known trend in development: Pre-adjust LDFs
- Known catastrophe year: Exclude or adjust
- Changing underwriting: Use subset of years

### Friedland Reference
Chapter 7, Pages 84-130 (Mack is extension; see technical appendix or Mack's papers)

---

## Quick Reference: Which Method Returns What

### ALWAYS Required:
```python
{
    'ultimate': numeric or array,           # Projected ultimate claims
    'reserve': numeric or array,            # Final reserve (case + IBNR)
    'ibnr': numeric or array,              # Future development component
    'case_outstanding': numeric or array,   # Known claims not yet paid
}
```

### Method-Specific Extras:

| Method | Extra Outputs |
|--------|---------------|
| Chain Ladder | `factors`, `ldfs`, `cdfs`, `ulf` |
| ELR | `expected_loss_ratio`, `loss_ratio` (actual) |
| BF | `expected_ultimate`, `cdf`, `percent_unreported` |
| Cape Cod | `adjusted_expected_lr`, `expected_ultimate` |
| Case O/S Dev | `ultimate_paid`, `ultimate_case_outstanding` |
| Clark | `parameters`, `fitted_ldf`, `distribution_type` |
| Benktander | `expected_ultimate`, `cdf` (same as BF) |
| Mack | `standard_error`, `coefficient_of_variation`, `confidence_intervals` |

---

## Validation Checks for Antigravity

### For Every Method:
```python
# Check 1: Relationships hold
assert reserve = case_outstanding + ibnr, "Reserve decomposition failed"
assert ibnr = ultimate - reported_claims, "IBNR calculation failed"
assert reserve = ultimate - paid_claims, "Reserve calculation failed"

# Check 2: Reasonableness
assert ultimate >= reported_claims, "Ultimate less than reported"
assert ibnr >= 0, "IBNR should be non-negative"
assert case_outstanding >= 0, "Case O/S should be non-negative"

# Check 3: Consistency
assert all values are positive, "No negative amounts"
assert reserve increases for immature years, "Development pattern reasonable"

# Check 4: Against inputs
assert reported_claims = paid_claims + case_outstanding, "Reported decomposition"
```

### For Chain Ladder Specifically:
```python
assert ulf > 1.0, "LDF should be > 1 (more to come)"
assert cdf < 1.0, "CDF should be < 1 (not 100% reported)"
assert cdf increases with age, "Development should progress"
```

### For BF/Benktander:
```python
assert ultimate between pure_chain_ladder and pure_elr, "Blending failed"
assert when cdf high: ultimate close to elr_ultimate, "High unreported weight"
assert when cdf low: ultimate close to reported, "Low unreported weight"
```

---

## Correcting the Backwork

When reviewing Antigravity output, check:

1. **Reserve Formula**: 
   - ✓ Ultimate - Paid Claims
   - ✓ Case O/S + IBNR
   - ✗ NOT Reserve - Case O/S (that's IBNR)

2. **IBNR Formula**:
   - ✓ Ultimate - Reported Claims
   - ✓ Reserve - Case O/S
   - ✗ NOT Ultimate / Reported Claims (that's ratio, not IBNR)

3. **Ultimate Formula** (varies by method):
   - ✓ Chain Ladder: Reported × LDF
   - ✓ ELR: Loss Ratio × Premium
   - ✓ BF: (CDF × ELR × Prem) + ((1-CDF) × Reported)
   - ✗ NOT Paid × LDF (missing case O/S component in most lines)

4. **Case Outstanding**:
   - ✓ Reported - Paid
   - ✓ Input from claims system (if using actual values)
   - ✗ NOT Reserve - IBNR (backwards relationship)

---

## Final Checklist for Code Validation

- [ ] All methods return `ultimate`, `reserve`, `ibnr`, `case_outstanding`
- [ ] Reserve = Case O/S + IBNR (identity holds)
- [ ] Reported = Paid + Case O/S (identity holds)
- [ ] IBNR = Ultimate - Reported (identity holds)
- [ ] Reserve = Ultimate - Paid (identity holds)
- [ ] All values are >= 0
- [ ] Ultimate >= Reported (maturity principle)
- [ ] Sensitivity analysis shows reasonable ranges
- [ ] Friedland references match implementation
- [ ] Test with known inputs to verify outputs

---

## References
Friedland, Jacqueline. *Estimating Unpaid Claims Using Basic Techniques*. Casualty Actuarial Society, 2010, Version 3.
- Chapter 7: Development Technique (Chain Ladder)
- Chapter 8: Expected Claims Technique
- Chapter 9: Bornhuetter-Ferguson Technique
- Chapter 10: Cape Cod Technique
- Chapter 11: Frequency-Severity Techniques
- Chapter 12: Case Outstanding Development Technique
