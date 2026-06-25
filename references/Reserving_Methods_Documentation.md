# Actuarial Reserving Methods Documentation
## Based on Friedland "Estimating Unpaid Claims Using Basic Techniques" (CAS, 2010, Version 3)

---

## Core Definitions (Chapter 1)

**Ultimate Claims**: Total dollar value after all claims are settled and closed without reopened claims.

**Reported Claims**: Sum of cumulative paid claims and case outstanding at a particular point in time.
```
Reported Claims = Cumulative Paid Claims + Case Outstanding
```

**IBNR (Broad Definition)**: Five components:
1. Case outstanding on known claims
2. Provision for future development on known claims
3. Estimate for reopened claims
4. Provision for claims incurred but not reported (pure IBNR)
5. Provision for claims in transit

**Reserve**: Amount booked in financial statement (carried reserve).

**Unpaid Claim Estimate**: Actuary's estimate of obligation for future payment from past events.

**Key Formula**:
```
Total Unpaid Claim Estimate = Case Outstanding + IBNR (broad definition)
IBNR (broad) = Ultimate Claims - Reported Claims
Reserve = Case Outstanding + IBNR (broad)
Reserve = Ultimate Claims - Cumulative Paid Claims
```

---

## 1. CHAIN LADDER METHOD (Chapter 7)

### Purpose
Project ultimate claims by applying historical age-to-age development factors to the most recent loss data.

### Key Components
- **Loss Development Triangle**: Organized by accident year (rows) and development age (columns)
- **Age-to-Age Factors (AF)**: Ratio of losses at one age to losses at prior age
- **Loss Development Factors (LDF)**: Cumulative products from tail factor back to age 0 (ultimate)
- **Cumulative Development Factor (CDF)**: Inverse of LDF; shows proportion of ultimate already reported

### Step-by-Step Process

#### Step 1: Build Development Triangle
- Rows = Accident Years
- Columns = Development Ages (12 months, 24 months, 36 months, etc.)
- Cells = Cumulative Reported Claims (Paid Claims + Case Outstanding)

#### Step 2: Calculate Age-to-Age Factors
For each development age column:
```
Age-to-Age Factor(age) = Reported Claims(current age) / Reported Claims(prior age)
```
Example: If 12-month reported = 100, 24-month reported = 140
```
AF(24) = 140 / 100 = 1.40
```

#### Step 3: Select Average Age-to-Age Factors
Methods:
- **Simple Average**: Sum all AFs / count (use for stable lines)
- **Weighted Average**: Sum(prior year reported × AF) / Sum(prior year reported) (use for changing environments)
- **Exclude Extremes**: Remove highest/lowest outliers
- **Selected LDF**: Actuary judgment based on trends and external benchmarks

#### Step 4: Calculate Loss Development Factors (LDF)
Working backward from tail:
```
LDF(age) = Selected AF(age) × LDF(next age)
LDF(ultimate age) = Selected AF(ultimate) × Tail Factor
```
Example (12-month to ultimate):
```
If AF(24) = 1.40, AF(36) = 1.10, AF(ultimate) = 1.02, Tail = 1.005
LDF(ultimate) = 1.02 × 1.005 = 1.0251
LDF(36) = 1.10 × 1.0251 = 1.1276
LDF(24) = 1.40 × 1.1276 = 1.5786
LDF(12) = AF(12) × LDF(24)
```

#### Step 5: Calculate CDF (Cumulative Development Factor)
```
CDF(age) = 1 / LDF(age)
```
Shows what % of ultimate is already reported at each age.

#### Step 6: Project Ultimate Claims
For most recent accident year (newest data):
```
Ultimate Claims = Most Recent Reported Claims × LDF(current age)
```

#### Step 7: Calculate IBNR and Reserve

**Pure IBNR** (future development on reported claims):
```
IBNR = Ultimate Claims - Most Recent Reported Claims
```

**Total Unpaid (Reserve)**:
```
Reserve = Ultimate Claims - Cumulative Paid Claims
   OR
Reserve = Case Outstanding + IBNR
```

#### Step 8: Sensitivity Analysis
Test impact of:
- Different tail factors (e.g., 1.000, 1.005, 1.010)
- Excluding recent years (if anomalous)
- Different averaging methods
- Trend adjustments for known changes

### Key Considerations (from Friedland)

**Paid vs. Incurred Selection**:
- Use **Paid Development**: More objective, less subjective adjuster opinion; but subject to payment timing volatility
- Use **Incurred Development**: Better reflects claim inflation and severity; but subject to case outstanding adequacy

**LDF Adjustment**:
- Apply adjustment factors for known tort reform, social inflation, or legislative changes
- Consider external benchmarks (ISO, industry data)
- Use judgment for last several ages if credible data is limited

**Tail Factor Selection**:
- Critical for long-tail lines (GL, WC)
- Use actuarial judgment or external benchmarks
- Consider development patterns in early years and external market data

---

## 2. EXPECTED LOSS RATIO (ELR) METHOD (Chapter 8)

### Purpose
Estimate ultimate claims using an expected loss ratio applied to earned premium.

### Key Components
- **Expected Loss Ratio (ELR)**: Expected claims / Earned Premium (judgment-based)
- **Earned Premium**: Premium earned during the accident period
- **Reported Claims**: Already known and reported
- **Ultimate Claims**: ELR × Earned Premium

### Step-by-Step Process

#### Step 1: Gather Data
- Earned Premium for accident year
- Reported Claims (cumulative paid + case outstanding)
- Historical Loss Ratios (actual claims / earned premium)
- Benchmark loss ratios (industry data, prior years, underwriting guidance)

#### Step 2: Estimate Expected Loss Ratio
Consider:
- **Prior Year Ratios**: What was the actual loss ratio in prior years?
- **Underwriting Guidance**: What loss ratio was priced/expected?
- **Environmental Changes**: Inflation, tort reform, legislative changes, social inflation
- **Product Mix**: Has the mix of business shifted?
- **Frequency & Severity Trends**: Are claims getting more frequent or severe?
- **External Benchmarks**: ISO, industry averages, competitor data

**Selection Judgment Points**:
```
ELR = (Underwriting guidance LR) 
    × (Inflation adjustment factor)
    × (Frequency trend)
    × (Severity trend)
    × (Mix adjustment)
    / (Reinsurance cession %)
```

#### Step 3: Calculate Ultimate Claims
```
Ultimate Claims = ELR × Earned Premium
```

#### Step 4: Calculate IBNR
```
IBNR = Ultimate Claims - Reported Claims
```

#### Step 5: Calculate Reserve
```
Reserve = Ultimate Claims - Cumulative Paid Claims
   OR
Reserve = Case Outstanding + IBNR
```

#### Step 6: Sensitivity Analysis
Test impact of:
- **ELR Slider**: ±0.5%, ±1.0%, ±2.0% of base ELR
- **Premium Adjustments**: Earned vs. written, reinsurance cessions
- **Comparison to Chain Ladder**: Reconcile differences

### Key Considerations (from Friedland)

**Advantages**:
- Independent of case outstanding adequacy
- Useful for immature accident years (insufficient paid/development history)
- Leverages underwriting judgment and expected loss experience

**Disadvantages**:
- Highly dependent on accuracy of ELR selection
- May not reflect actual experience if environment has changed
- Less credible than development methods for mature years

**Best Use**:
- Immature accident years with limited development
- Lines with significant catastrophe variability
- Validation against Chain Ladder estimates

---

## 3. BORNHUETTER-FERGUSON METHOD (Chapter 9)

### Purpose
Blend Chain Ladder and ELR methods using percent unreported (CDF) as credibility weight.

### Key Principle
Credibility = Percent Unreported (based on CDF from Chain Ladder)
```
Ultimate = (Percent Unreported × ELR Ultimate) + (Percent Reported × Reported Claims)
         = (CDF × ELR × Premium) + ((1 - CDF) × Reported Claims)
```

The CDF (cumulative development factor) acts as the credibility weighting.

### Step-by-Step Process

#### Step 1: Calculate LDF and CDF from Chain Ladder
(See Chain Ladder Steps 1-5)
```
CDF = 1 / LDF
Percent Unreported = CDF
Percent Reported = 1 - CDF
```

#### Step 2: Estimate ELR
(See ELR Step 2)

#### Step 3: Calculate ELR Ultimate
```
ELR Ultimate = ELR × Earned Premium
```

#### Step 4: Calculate BF Ultimate Claims
```
BF Ultimate = (Percent Unreported × ELR Ultimate) + (Percent Reported × Reported Claims)
            = (CDF × ELR Ultimate) + ((1 - CDF) × Reported Claims)
```

#### Step 5: Calculate IBNR
```
IBNR = BF Ultimate - Reported Claims
```

#### Step 6: Calculate Reserve
```
Reserve = BF Ultimate - Cumulative Paid Claims
   OR
Reserve = Case Outstanding + IBNR
```

#### Step 7: Triangulate Results
Compare to:
- **Pure Chain Ladder**: If BF is significantly different, investigate why
- **Pure ELR**: BF should be between CL and ELR
- **Reasonableness**: Does BF ultimate make sense given environment?

### Key Considerations (from Friedland)

**Credibility Blending**:
- Early development ages: High unreported %, so ELR dominates (appropriate for immature years)
- Mature development ages: Low unreported %, so reported claims dominate (appropriate for mature years)
- Automatic balance between methods based on development stage

**Percent Unreported Selection**:
- Use CDF from Chain Ladder LDF at current evaluation age
- Adjust if case outstanding practice has changed significantly
- Can be adjusted to reflect known structural changes

**When to Use**:
- Preferred method for many actuaries
- Balances objectivity of Chain Ladder with judgment of ELR
- Works well across all development ages
- Recommended by Friedland for most situations

---

## 4. CAPE COD METHOD (Chapter 10)

### Purpose
Estimate ultimate claims using iteratively derived loss ratio applied to exposures across all years.

### Key Difference from ELR
- Uses **exposure-weighted** average historical loss ratio
- Applies to all accident years, not just current year
- Updates ELR as experience emerges across accident years

### Step-by-Step Process

#### Step 1: Calculate Expected Loss Ratio (Initial Estimate)
Use external benchmark, prior underwriting guidance, or industry data as starting point.

#### Step 2: Calculate Loss Development Factors
(From Chain Ladder method; see Chain Ladder Steps 1-5)

#### Step 3: Build Cape Cod Triangle
For each accident year and development age:
```
Expected Ultimate (basic) = Expected LR × Earned Premium(year)
```

#### Step 4: Calculate Reported Claims as % of Expected Ultimate
```
% Reported(year, age) = Reported Claims(year, age) / Expected Ultimate(year)
```

#### Step 5: Calculate Adjusted Expected Loss Ratio
Average the reported % across all years (weighted by premium or other exposure):
```
Adjusted ELR = Total Reported Claims / Total (Earned Premium × Expected LR)
```

#### Step 6: Recalculate Expected Ultimate with Adjusted ELR
```
Expected Ultimate(year) = Adjusted ELR × Earned Premium(year)
```

#### Step 7: Calculate IBNR
```
IBNR(year) = Expected Ultimate(year) - Reported Claims(year)
```

#### Step 8: Calculate Reserve
```
Reserve(year) = Expected Ultimate(year) - Cumulative Paid(year)
```

#### Step 9: Iterate (Optional)
Repeat Steps 4-6 to refine ELR estimate until convergence.

### Key Considerations (from Friedland)

**vs. ELR Method**:
- Cape Cod is **exposure-credibility adjusted** using actual experience across years
- Produces more consistent loss ratio across years than pure ELR
- Better for portfolios with consistent underwriting guidance

**vs. Bornhuetter-Ferguson**:
- Cape Cod blends all years with exposure weighting
- BF uses development-age credibility (CDF)
- Cape Cod may be preferred if loss ratio consistency is key

**When to Use**:
- Consistent pricing and underwriting across years
- Mature portfolio with predictable development patterns
- When external loss ratio benchmarks are reliable

---

## 5. CASE OUTSTANDING DEVELOPMENT TECHNIQUE (Chapter 12)

### Purpose
Analyze and project case outstanding separately to assess adequacy and improve IBNR estimates.

### Key Components
- **Case Outstanding**: Claim adjuster reserves on known claims
- **Reported Claims**: Paid + Case Outstanding
- **Development on Known Claims**: Gap between reported claims at one age and later age (IBNER)

### Step-by-Step Process

#### Step 1: Build Separate Triangles
Create **two separate development triangles**:
1. **Paid Claims Triangle**: Cumulative paid claims only
2. **Case Outstanding Triangle**: Case outstanding reserves at each age

#### Step 2: Calculate Reported Claims by Combining
```
Reported Claims = Cumulative Paid + Case Outstanding
```

#### Step 3: Analyze Case Outstanding Development
For each accident year:
```
Case O/S at 24 mo / Case O/S at 12 mo = Case development ratio
```

Questions to investigate:
- Is case outstanding increasing, decreasing, or stable?
- Are adjusters under- or over-reserving?
- Has case setting practice changed?

#### Step 4: Project Ultimate Paid Claims (Chain Ladder on Paid)
```
Ultimate Paid = Latest Paid Claims × LDF(Paid Development)
```

#### Step 5: Estimate Final Case Outstanding
Using case development patterns and claimed counts:
```
Projected Final Case O/S = Latest Case O/S × Assumed Case Ratio
   OR
Projected Final Case O/S = Expected Claims per Claim Count × Open Claim Counts
```

#### Step 6: Calculate Ultimate Claims
```
Ultimate Claims = Ultimate Paid Claims + Projected Final Case O/S
```

#### Step 7: Calculate IBNR and Reserve
```
IBNR = Ultimate Claims - Reported Claims
Reserve = Ultimate Claims - Cumulative Paid Claims
```

### Key Considerations (from Friedland)

**Strength of Case Outstanding**:
- **Strong Case O/S**: Case reserves increase as claims mature (adequacy improves)
  - Use reported claims (incurred) development
  - Suggests case adjusters are conservative and accurate
  
- **Weak Case O/S**: Case reserves decrease or remain flat (may indicate under-reserving)
  - May need adjustment to case outstanding estimates
  - Use paid claims development with estimated final case O/S

**Reopened Claims**:
- If case outstanding pattern shows increases after expected closure, may indicate reopens
- Include reopened claim estimates in ultimate case outstanding

**When to Use**:
- Diagnostic tool to assess case adequacy
- Modify other methods (CL, BF, CC) based on findings
- Required analysis for many jurisdictions

---

## 6. EXPECTED CLAIMS TECHNIQUE (Frequency-Severity) (Chapter 11)

### Purpose
Estimate ultimate claims by projecting claim counts and average severity separately.

### Key Principle
```
Ultimate Claims = Projected Claim Counts × Projected Average Severity
```

### Step-by-Step Process

#### Step 1: Build Claim Count Development Triangle
- Rows: Accident years
- Columns: Development ages
- Cells: Cumulative reported claim counts (open + closed)

#### Step 2: Project Ultimate Claim Counts
Apply development factors to claim counts:
```
Ultimate Claim Counts = Latest Reported Counts × Count LDF
   OR
Ultimate Claim Counts = Reported Counts / Count CDF
```

Count LDFs typically plateau earlier than loss LDFs.

#### Step 3: Build Average Severity Development Triangle
```
Average Severity(year, age) = Reported Claims(year, age) / Reported Counts(year, age)
```

#### Step 4: Project Average Severity
Methods:
- **Trend Analysis**: Apply inflation/severity trend to latest average severity
- **Mature Age Severity**: Use average severity at mature development age
- **Exponential Growth**: Model severity growth curve

#### Step 5: Calculate Ultimate Claims
```
Ultimate Claims = Ultimate Claim Counts × Projected Average Severity
```

#### Step 6: Calculate IBNR and Reserve
```
IBNR = Ultimate Claims - Reported Claims
Reserve = Ultimate Claims - Cumulative Paid Claims
```

### Key Considerations (from Friedland)

**Advantages**:
- Isolates frequency and severity components
- Useful for understanding environmental changes
- Can identify trends in claim counts vs. severity separately

**Disadvantages**:
- Requires claim count data (not always available)
- Sensitive to count data quality and disposal practices
- May be less stable than aggregate loss development

**When to Use**:
- When claim count data is reliable and available
- To diagnose whether changes are driven by frequency or severity
- Validation of aggregate development methods

---

## 7. CLARKS' LDF METHOD (Extensions to Chain Ladder)

### Purpose
Alternative parameterized development model for smoothing LDFs and projecting tail.

### Key Concept
Rather than calculating discrete age-to-age factors, Clarks' method:
- Fits a cumulative distribution function to the development pattern
- Creates smooth, mathematically continuous LDFs
- Better estimates of tail factors (beyond observed data)

### Step-by-Step Process

#### Step 1: Gather Development Data
- Same loss development triangle as Chain Ladder
- Ensure sufficient development history

#### Step 2: Calculate % of Ultimate for Each Age
```
% Reported(age) = Reported Claims(age) / Ultimate Claims (from chain ladder)
```

#### Step 3: Fit Distribution to Development Pattern
Common models:
- **Lognormal**: Good for most lines, flexible tail
- **Weibull**: Alternative parameterization
- **Inverse Power Law**: Simple tail modeling

#### Step 4: Estimate Parameters
Use statistical fitting (maximum likelihood) to estimate:
- **Logmean (μ)** or **Shape parameter**: Controls development speed
- **Logstd (σ)** or **Scale parameter**: Controls dispersion

#### Step 5: Calculate Smooth LDFs
From fitted distribution:
```
LDF(age) = Ultimate / % Reported(age)
CDF(age) = % Reported(age) = F(age; μ, σ)
```

#### Step 6: Extend Tail
Use fitted distribution to project beyond observed ages:
```
LDF(tail age) = Ultimate / F(tail age; μ, σ)
```

#### Step 7: Calculate Ultimate and IBNR
```
Ultimate Claims = Reported Claims × LDF(current age)
IBNR = Ultimate Claims - Reported Claims
```

### Key Considerations

**Advantages**:
- Smooth development pattern avoids choppy LDFs
- Mathematically defensible tail estimation
- Works well for long-tail lines

**Disadvantages**:
- Requires statistical fitting (more complex)
- May under-weight recent development shifts
- Less transparent than traditional chain ladder

**When to Use**:
- Long-tail lines requiring tail estimation
- When discrete LDFs are volatile
- As validation/comparison to traditional chain ladder

---

## 8. MACK CHAIN LADDER (Stochastic Chain Ladder)

### Purpose
Chain Ladder method with uncertainty analysis (confidence intervals).

### Key Enhancement
Produces not just point estimate but also **standard error** and **confidence intervals** around the reserve estimate.

### Step-by-Step Process

#### Step 1-6: Standard Chain Ladder
(See Chain Ladder Steps 1-6 to calculate point estimate and LDFs)

#### Step 7: Calculate Variance of Development
For each age-to-age factor:
```
Variance(AF) = Sum[(AF(i) - Mean AF)² × Prior Year Reported(i)] / (n - 1)
```

#### Step 8: Calculate Variance of Ultimate Estimate
```
SE²(Ultimate) = Ultimate² × Sum[Variance(AF) / (AF² × Latest Reported²)]
```

(Formula varies by development age; see technical sources for full derivation)

#### Step 9: Calculate Confidence Intervals
```
95% Confidence Interval = Ultimate ± 1.96 × SE(Ultimate)
```

Can also calculate:
- **Coefficient of Variation (CV)**: SE / Ultimate
- **Range of Reasonably Possible Outcomes**: 50th percentile to 95th percentile

### Key Considerations (from ASOP 43)

**Important Notes**:
- Mack assumes no structural changes in development patterns
- Assumes independence across accident years
- Confidence intervals assume model is correct

**When to Use**:
- Quantifying uncertainty in reserves
- Regulatory requirements (e.g., 75th percentile reserves)
- Evaluating range of reasonable estimates

---

## Summary Comparison Table

| **Method** | **Key Inputs** | **Best For** | **IBNR Formula** | **Key Judgment** |
|---|---|---|---|---|
| **Chain Ladder** | Reported Claims Triangle | Most lines; mature years | ULT - Reported | LDF selection, tail factor |
| **ELR** | Premium, Expected Loss Ratio | Immature years | ELR × Prem - Reported | ELR selection |
| **Bornhuetter-Ferguson** | CDF, ELR, Premium | Balanced approach | (CDF × ELR × Prem) + ((1-CDF) × Rep) | ELR, CDF weighting |
| **Cape Cod** | Multi-year premium/claims | Stable underwriting | (Adjusted ELR × Prem) - Reported | ELR iteration |
| **Case O/S Development** | Paid + Case O/S Triangles | Case adequacy assessment | (ULT Paid) + (Proj Final Case) - Reported | Case reserving patterns |
| **Frequency-Severity** | Claim counts + severity | Diagnostic, component analysis | (ULT Counts × Avg Sev) - Reported | Count & severity trends |
| **Clarks** | Reported Claims + Distribution fit | Tail estimation, smooth LDFs | ULT - Reported | Distribution selection |
| **Mack** | Reported Claims + Variance | Uncertainty quantification | Same as Chain Ladder | SE calculation, credibility |

---

## Key Formulas Reference

### Common to All Methods:

```
Ultimate Claims = Projected future total claim cost (all years settled, all claims closed)

Reported Claims = Cumulative Paid Claims + Case Outstanding
               = Sum of claims already paid + Estimator reserves on open claims

Reserve (Carried Reserve) = Ultimate Claims - Cumulative Paid Claims
                          = Case Outstanding + IBNR (broad)

Pure IBNR = Ultimate Claims - Reported Claims
          = Future development on reported claims + Pure IBNR (unreported) + Reopens

Reserve = Cumulative Paid + (Ultimate - Cumulative Paid)
        = Cumulative Paid + Reserve
```

### By Method:

**Chain Ladder:**
```
Ultimate = Reported(latest age) × LDF(current age)
LDF = Product of selected age-to-age factors from current age to ultimate
CDF = 1 / LDF
```

**ELR:**
```
Ultimate = Expected Loss Ratio × Earned Premium
```

**Bornhuetter-Ferguson:**
```
Ultimate = (CDF × ELR × Premium) + ((1 - CDF) × Reported)
```

**Cape Cod:**
```
Adjusted ELR = Total Reported / Total (Premium × Initial ELR)
Ultimate = Adjusted ELR × Premium
```

**Case O/S Development:**
```
Ultimate = Ultimate Paid + Projected Final Case O/S
Ultimate Paid = Paid(latest) × LDF(Paid development)
```

---

## References
Friedland, Jacqueline. *Estimating Unpaid Claims Using Basic Techniques*. Casualty Actuarial Society, 2010, Version 3. Chapters 7-12.
