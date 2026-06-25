# Analysis: Paid vs. Incurred Triangle Architecture Issue

## TL;DR - What's Wrong

You're running the **same method (Chain Ladder, BF, etc.) independently on both Paid AND Incurred triangles** and reporting both as separate estimates. This is conceptually broken because:

1. **The triangles measure DIFFERENT things** – not different scenarios
   - Paid triangle = Only cash paid, missing case reserves
   - Incurred triangle = Cash + adjuster reserves (complete picture)

2. **You can't independently evaluate a method twice on the same data**
   - It's not a "paid version vs. incurred version" of Chain Ladder
   - It's like running regression with X1 vs. X1+X2 and pretending they're different models

3. **Your results table is confusing actuaries** because:
   - Two "Chain Ladder" rows with different numbers (one paid, one incurred) suggests you have two estimates to choose between
   - Actually, you should have ONE (incurred), and paid is only for diagnosis

4. **Most importantly: You lose diagnostic power**
   - Case O/S Development analysis (the ONLY place paid/incurred matters) gets buried in comparison noise

---

## Foundation: What Paid and Incurred Actually Mean

### Paid Triangle
```
Paid[Accident Year, Age] = Cumulative cash paid to claimants
```

Example:
```
AY2020, Age 12 mo: $500K (cash out)
AY2020, Age 24 mo: $750K (cumulative cash out)
AY2020, Age 36 mo: $850K (cumulative cash out)
```

**What it does NOT include:**
- Case outstanding reserves on open claims
- Estimators' belief about what claims will eventually cost
- Only the money actually paid to date

### Incurred (Reported) Triangle
```
Incurred[Accident Year, Age] = Cumulative Paid + Case Outstanding at that age
```

Example for SAME accident year:
```
AY2020, Age 12 mo: $500K paid + $300K case = $800K incurred
AY2020, Age 24 mo: $750K paid + $150K case = $900K incurred
AY2020, Age 36 mo: $850K paid + $70K case = $920K incurred
```

**What it includes:**
- Everything paid to date
- PLUS what claim adjusters currently estimate for unpaid claims
- Better reflection of "true" claim development from a reserve perspective

### Key Insight
These are **not two independent datasets**. Incurred literally contains paid as a component:
```
Incurred = Paid + Case Outstanding
```

Therefore, running the **same Chain Ladder method** on both produces **fundamentally different development patterns** – not because the method is different, but because the inputs are different.

---

## What Friedland Says (Chapters 7, 12)

### Primary Development Method (for estimating unpaid claims)

**Friedland's Default (Chapter 7 - Development Technique):**
> "For most lines of insurance, actuaries rely on the **reported claims development triangle** (also called the incurred triangle) as the basis for the development technique."

**Why Incurred is Standard:**
1. Better reflects claim inflation and severity trends
2. Includes estimator judgment (case reserves)
3. Drives actual reserve decisions
4. Appropriate for long-tail lines (GL, WC, Medical Malpractice)

### When Paid Triangle Is Used

**Friedland Chapter 7, Paid Development:**
> "The **paid claims development** method is an alternative that uses cumulative paid claims instead of reported claims... Useful when case outstanding estimates are unreliable or when adjusters consistently over/under reserve."

**Important:** Paid is not an alternative estimate to report alongside incurred. It's a **diagnostic** to check if incurred is appropriate.

### The Right Way to Use Both Triangles

**Friedland Chapter 12 - Case Outstanding Development:**
This is where paid and incurred are analyzed **together, but separately**:

1. Build Paid triangle
2. Build Incurred triangle
3. Analyze case outstanding development: `Case O/S[age] = Incurred[age] - Paid[age]`
4. Question: Is case O/S getting smaller (strong reserves) or staying flat (weak reserves)?
5. Decision: If weak case O/S → Switch to Paid triangle with estimated final case O/S
6. If strong case O/S → Use Incurred triangle with confidence

**This is diagnostic, not dual reporting.**

---

## What Your UI Currently Does (WRONG)

Looking at your "Configure Reserving Assumptions" screen:

```
✓ Chain Ladder
   ✓ Paid     ✓ Incurred
   
✓ Mack Chain Ladder
   ✓ Paid     ✓ Incurred
   
✓ Bornhuetter-Ferguson
   ✓ Paid     ☐ Incurred    [ELR input]
   
✓ Cape Cod
   ✓ Paid     ☐ Incurred
```

**The problem:**
- You allow users to check BOTH paid and incurred independently
- You then calculate and display both in the comparison table
- This creates 12+ methods (each method × 2 triangle types)
- Your results table has rows like:
  - `BF_INCURRED` → IBNR: -$168K
  - `BF_PAID` → IBNR: +$21K
  - `CL_INCURRED` → IBNR: -$164K
  - `CL_PAID` → IBNR: +$142K

**What this implies to a user:**
> "I have four different Chain Ladder estimates. Should I use the paid one or the incurred one?"

**What it should imply:**
> "I have ONE Chain Ladder estimate (incurred). The paid version is just a diagnostic check."

---

## What Your Results Actually Show (And Why It's Confusing)

From your table:

| Method Code | Method Name | IBNR | Ultimate | Loss Ratio |
|---|---|---|---|---|
| BF_INCURRED | Bornhuetter-Ferguson (Incurred) | -$168K | $7.88M | 66.7% |
| BF_PAID | Bornhuetter-Ferguson (Paid) | +$21K | $8.07M | 68.3% |
| CL_INCURRED | Chain Ladder (Incurred) | -$164K | $7.89M | 66.8% |
| CL_PAID | Chain Ladder (Paid) | +$142K | $8.19M | 69.4% |

**The confusion:**
1. Why is INCURRED showing **negative IBNR**? (-$168K, -$164K)
   - This suggests Ultimate < Reported Claims (impossible)
   - Indicates a calculation error in your backward work

2. Why do Paid and Incurred differ so much?
   - $7.88M vs $8.07M for BF
   - $7.89M vs $8.19M for CL
   - This is expected given different inputs, but you're treating them as alternatives

3. Loss Ratios vary: 66.7% vs 68.3% for BF
   - Users will wonder: "Which is correct?"
   - Answer: Only the incurred (66.7%) is meaningful

---

## How to Fix This: Right Architecture

### Option A: Single Incurred Triangle (Recommended for Comparison Engine)

**For your comparison dashboard:**

1. **Build ONE Incurred (Reported) Triangle** at evaluation time
2. **Run all methods on that triangle:**
   - Chain Ladder (Incurred)
   - Mack Chain Ladder (Incurred)
   - Bornhuetter-Ferguson (Incurred, with ELR input)
   - Cape Cod (Incurred, with ELR and decay)
   - Clark Stochastic (Incurred)
   - Expected Loss Ratio (standalone)
   - Case Outstanding (diagnostic only, see below)

3. **Report results as a clean table:**
   ```
   Method          | Reserve | IBNR | Ultimate | LR    | Maturity
   ─────────────────────────────────────────────────────────────
   Chain Ladder    | $1.2M   | $0.9M | $8.1M   | 68.2% | 78.5%
   Mack CL         | $1.2M   | $0.9M | $8.1M   | 68.2% | 78.5%
   BF (ELR 67%)    | $1.15M  | $0.85M | $7.95M  | 67.2% | 79.3%
   Cape Cod        | $1.18M  | $0.88M | $8.0M   | 67.8% | 79.1%
   ...
   ```

**Rationale:**
- One ultimate estimate per method (not two)
- Focuses on method choice, not triangle choice
- Cleaner comparison table
- Actuaries know how to read this

### Option B: Diagnostic Tool (Case O/S Development)

**In a SEPARATE section** (not comparison table):

```
DIAGNOSTIC: Case Outstanding Adequacy Assessment

Paid Development Triangle:
  AY2020: Paid[12m] = $500K → Paid[24m] = $750K → Paid[36m] = $850K
  
Incurred Triangle:
  AY2020: Incurred[12m] = $800K → Incurred[24m] = $900K → Incurred[36m] = $920K
  
Case Outstanding Over Time:
  AY2020: Case O/S[12m] = $300K (37.5% of incurred)
  AY2020: Case O/S[24m] = $150K (16.7% of incurred) ← DECLINING
  AY2020: Case O/S[36m] = $70K  (7.6% of incurred)  ← DECLINING

Assessment: STRONG case outstanding
→ Case reserves are adequate and declining appropriately
→ Use INCURRED triangle (paid + case) for primary estimates
→ Confidence in incurred-based methods is HIGH
```

**Purpose:** Inform the actuarial judgment, not provide alternative estimates.

---

## Corrected Method Logic (Per Friedland)

### When to Use Incurred Triangle (Standard)

✓ **Chain Ladder (Incurred)**
- Most common approach
- Uses: Reported Claims = Paid + Case Outstanding
- LDF pattern: $800K → $900K → $920K
- Best when: Case outstanding is reliable

✓ **Bornhuetter-Ferguson (Incurred)**
- ELR blended with incurred development
- Uses: Incurred triangle + Expected Loss Ratio
- Weights blend by CDF
- Best when: Immature years + reliable ELR

✓ **Cape Cod (Incurred)**
- Multi-year exposure-weighted LR adjustment
- Uses: Incurred triangle + earned premium across years
- Refines ELR iteratively
- Best when: Consistent underwriting, stable mix

✓ **Mack Chain Ladder (Incurred)**
- Chain ladder + uncertainty quantification
- Uses: Incurred triangle for point estimate + variance
- Reports: CV (coefficient of variation), confidence intervals
- Best when: Need reserve uncertainty ranges

✓ **Clark Stochastic (Incurred)**
- Smooth curve fitting to development
- Uses: Incurred triangle + distribution (Weibull/Log-Logistic)
- Better tail estimation
- Best when: Long-tail lines, smooth patterns needed

---

### When Paid Triangle Is Relevant

❌ **NOT for independent estimates** – only diagnostic

✓ **Case Outstanding Development (Paid + Incurred)**
- Purpose: Assess if case reserves are adequate
- Calculates: Case O/S trends over time
- Guides: Whether to trust incurred development or adjust it
- Output: Recommendation (use incurred vs. adjust to paid+estimated case)

**Example decision logic:**
```python
if case_outstanding_is_strong():
    # Case reserves are appropriate, declining over time
    ultimate = chain_ladder(incurred_triangle)
elif case_outstanding_is_weak():
    # Case reserves are NOT declining; may be under-reserving
    ultimate_paid = chain_ladder(paid_triangle)
    final_case_estimate = judgment_based_estimate()
    ultimate = ultimate_paid + final_case_estimate
```

---

## Specific Issues in Your Results Table

### Issue 1: Negative IBNR on Incurred Methods

**Your results show:**
```
BF_INCURRED: IBNR = -$168K, Ultimate = $7.88M
CL_INCURRED: IBNR = -$164K, Ultimate = $7.89M
```

**This is WRONG.** IBNR cannot be negative:
```
IBNR = Ultimate - Reported Claims
```

If IBNR is negative, it means:
```
Ultimate < Reported Claims
```

Which is impossible — the ultimate cost can never be less than what's already been reported.

**Root cause:** Your incurred triangle values are too high OR your LDF/ultimate calculations are too low.

**Check:** Are you confusing the formula?
- ✗ WRONG: `IBNR = Reported - Ultimate` (backwards)
- ✓ CORRECT: `IBNR = Ultimate - Reported`

### Issue 2: Case O/S Column Missing Insight

Your table shows:
```
RESERVE/CASE RATIO: 0.99, 1.01, 0.98, 1.05
```

But doesn't separate:
- **Case Outstanding** (known, fixed at eval date)
- **IBNR** (future development, varies by method)

The reserve/case ratio is confusing because:
- Reserve = Case + IBNR
- If IBNR is wrong (or negative), the ratio is meaningless

### Issue 3: Loss Ratio Variation

```
ELR_INCURRED: 67.5%, Loss Ratio = 67.5% ✓ (correct, by design)
ELR_PAID:     67.4%, Loss Ratio = 67.4% 

CL_INCURRED:  66.8%, Loss Ratio
CL_PAID:      69.4%, Loss Ratio
```

The variation between paid and incurred is expected, but **reporting both suggests they're both valid options**. They're not.

---

## Recommended Changes to Your App

### 1. Restructure Configuration UI

**Currently:**
```
☑ Chain Ladder
  ☑ Paid    ☑ Incurred
  
☑ BF
  ☑ Paid    ☑ Incurred
```

**Better:**
```
DATA SOURCE
  Radio button: ● Incurred Triangle (recommended)
                ○ Paid Triangle (if case O/S is weak)
                
METHODS TO COMPARE
  ☑ Chain Ladder
  ☑ Mack Chain Ladder
  ☑ Bornhuetter-Ferguson
  ☑ Cape Cod
  ☑ Clark Stochastic
  ☑ Expected Loss Ratio
  
DIAGNOSTICS (separate from methods)
  ☑ Case Outstanding Development (optional, for audit)
```

**Rationale:**
- One triangle choice (not per-method)
- Methods are listed without paid/incurred variants
- Case O/S analysis is clearly separate/optional

### 2. Restructure Results Table

**Currently (wrong):**
```
METHOD_CODE    | METHOD_NAME              | STATUS | IBNR    | ULTIMATE
BF_INCURRED    | BF (Incurred)            | OK     | -$168K  | $7.88M
BF_PAID        | BF (Paid)                | OK     | +$21K   | $8.07M
```

**Better (correct):**
```
METHOD                    | RESERVE  | IBNR    | ULTIMATE | LR    | CV    | MATURITY
──────────────────────────────────────────────────────────────────────────────
Chain Ladder              | $1.20M   | $0.90M  | $8.10M   | 68.2% | 4.2%  | 79.2%
Mack Chain Ladder         | $1.20M   | $0.90M  | $8.10M   | 68.2% | 4.2%  | 79.2%
Bornhuetter-Ferguson      | $1.15M   | $0.85M  | $7.95M   | 67.2% | —     | 80.1%
Cape Cod                  | $1.18M   | $0.88M  | $8.00M   | 67.8% | —     | 79.6%
Clark Stochastic (Weibull)| $1.19M   | $0.89M  | $8.09M   | 68.1% | 4.1%  | 79.4%
Expected Loss Ratio       | $1.22M   | $0.92M  | $8.22M   | 69.5% | —     | 77.5%
```

**Key differences:**
- One row per method (not paid/incurred variant)
- CV shown only for stochastic methods (Mack, Clark)
- Maturity score (from CDF) shows development stage
- No confusion about which to use

### 3. Optional: Diagnostic Panel

If you want to show case O/S analysis:

```
DIAGNOSTIC REPORT: Case Outstanding Adequacy

┌─ Case Outstanding Analysis (Separate Triangle Assessment) ────────────────┐
│ Purpose: Assess whether case reserves are adequate or need adjustment     │
│                                                                             │
│ Paid Development:    $500K → $750K → $850K → $920K (projected)           │
│ Incurred Development: $800K → $900K → $920K → $925K (projected)          │
│                                                                             │
│ Case O/S Trend:      $300K (37.5%) → $150K (16.7%) → $70K (7.6%)        │
│ Assessment:          STRONG (declining appropriately)                      │
│                                                                             │
│ Recommendation:      Use incurred triangle estimates above with confidence │
│                      No adjustments needed to case outstanding values     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Summary Table: What Methods Should Use What Triangle

| Method | Triangle | Why | Friedland Chapter |
|--------|----------|-----|-------------------|
| Chain Ladder | Incurred (default) | Reflects true development | 7 |
| Chain Ladder | Paid (alternative) | When case O/S unreliable | 7 |
| Mack CL | Incurred (default) | Variance around development | 7 |
| Mack CL | Paid (alternative) | Variance around payments | 7 |
| BF | Incurred | Blend CDF + reported | 9 |
| BF | Paid (rare) | Blend CDF + paid (unusual) | 9 |
| Cape Cod | Incurred | Exposure-weighted multi-year | 10 |
| Expected LR | Neither (Premium-based) | ELR × Premium, no triangles | 8 |
| Clark | Incurred (default) | Smooth development curve | 7 (advanced) |
| Case O/S Dev | **Both (paired)** | Diagnostic: assess adequacy | 12 |

**Red Rule:** If you're running the same method on paid AND incurred independently and reporting both, you're doing it wrong.

---

## Questions to Ask Yourself

1. **Why would a user need both BF_INCURRED and BF_PAID?**
   - To choose between them? (Wrong — incurred is standard)
   - As a sensitivity check? (Could be, but then label it clearly as diagnostic)
   - As two independent models? (Conceptually broken)

2. **What does "IBNR = -$164K" mean?**
   - It's mathematically impossible
   - Points to formula error in your backward work

3. **Why do you calculate Case O/S Development?**
   - To inform whether to trust the incurred estimates
   - To adjust them if needed
   - NOT to report as an independent estimate

4. **Can a user pick "Paid Triangle" for all methods?**
   - Some methods (BF, ELR, Cape Cod) were designed for incurred
   - Paid triangle changes the meaning substantially
   - Should either: lock to incurred, or clearly warn when using paid

---

## Fixing the Backwork

Based on your results showing negative IBNR, check:

```python
# WRONG (you may be doing this):
ibnr = reported - ultimate  # backwards!
ultimate = reported + ibnr  # circular

# CORRECT:
ibnr = ultimate - reported
reserve = ultimate - paid_claims
# Verify: reserve == case_outstanding + ibnr
```

For each method, the ultimate should satisfy:
```python
assert ultimate >= reported, "Ultimate must be >= reported"
assert ibnr == ultimate - reported, "IBNR = Ultimate - Reported"
assert reserve == ultimate - paid, "Reserve = Ultimate - Paid"
```

---

## Key Takeaway

**You have built a comparison engine, not a sensitivity engine.**

A comparison engine shows: "Here are 6 different methods, applied the same way, which gives the best estimate?"

A sensitivity engine shows: "Here is 1 method, applied different ways (paid vs. incurred), what's the range?"

You're mixing them. Either:

**Option A (Recommended):** Keep it a comparison engine → One triangle (incurred), multiple methods
**Option B:** Rebuild as sensitivity → One method, multiple triangles + case O/S diagnostics

Your current hybrid (multiple methods × multiple triangles) creates confusion because it looks like comparison but acts like sensitivity.

---

## References

Friedland, *Estimating Unpaid Claims Using Basic Techniques*, CAS 2010:
- **Chapter 7**: Development Technique (paid vs. incurred discussion)
- **Chapter 12**: Case Outstanding Development Technique (diagnostic use of paid/incurred pair)
- **Pages 84–130, 265–282**
