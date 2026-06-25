# Advanced Actuarial Diagnostics Framework

This document describes the mathematical formulation, interpretation, and method suitability rules for the advanced actuarial diagnostics framework.

---

## 1. Reporting Pattern Diagnostics

### Mathematical Basis
The reporting pattern diagnostic fits three continuous growth curves to the cumulative development progression $G(t_j) = 1 / CDF(t_j)$, representing the percentage of losses developed at development age $t_j$ (in months):

1. **Log-Logistic Curve**:
   $$G(t) = \frac{t^b}{a + t^b}$$
   *Linearized for OLS*: $\ln\left(\frac{G(t)}{1 - G(t)}\right) = b \ln(t) - \ln(a)$
   
2. **Weibull Curve**:
   $$G(t) = 1 - e^{-a \cdot t^b}$$
   *Linearized for OLS*: $\ln(-\ln(1 - G(t))) = \ln(a) + b \ln(t)$
   
3. **Exponential Curve**:
   $$G(t) = 1 - e^{-(a \cdot t + c)}$$
   *Linearized for OLS*: $\ln(1 - G(t)) = -a \cdot t - c$

We perform linear regression using Ordinary Least Squares (OLS) on the transformed variables (clamping $G(t)$ to $[0.0001, 0.9999]$ to prevent mathematical limits). For each curve, we calculate the Coefficient of Determination ($R^2$), Root Mean Squared Error (RMSE), and Mean Absolute Error (MAE):
$$R^2 = 1 - \frac{\sum (G_j - \hat{G}_j)^2}{\sum (G_j - \bar{G})^2}$$
$$\text{RMSE} = \sqrt{\frac{\sum (G_j - \hat{G}_j)^2}{N}}$$

The curve with the highest $R^2$ is selected as the **best fitting curve**.

### Interpretation & Deviations
For each accident year $i$, we project its Chain Ladder ultimate $Ult_i$ and calculate actual developed percentages $G_{i, j} = C_{i, j} / Ult_i$. We compute $RMSE_i$ between these ratios and the best-fitting curve values $\hat{G}_j$.
* **Significant Deviation**: Flagged if $RMSE_i > 0.05$ (meaning on average, development differs by more than 5% of ultimate from the expected curve).
* **Reporting Consistency**: Categorized based on the average $RMSE_i$ across all years:
  - $< 0.02$: **Highly Consistent**
  - $0.02$ to $0.05$: **Consistent**
  - $0.05$ to $0.10$: **Moderately Consistent**
  - $> 0.10$: **Inconsistent**

---

## 2. LDF Stability Analysis

### Mathematical Basis
For each development period transition $j \to j+1$, we compute the individual age-to-age factors $f_{i, j} = C_{i, j+1} / C_{i, j}$. We calculate the column-level simple average $sa_j$, standard deviation $std_j$, and the Coefficient of Variation ($CoV_j$):
$$CoV_j = \frac{std_j}{sa_j}$$

We compute the average CoV across all columns (excluding the tail).

### Interpretation & Thresholds
* **Unstable Period**: Any age transition $j \to j+1$ where $CoV_j > 0.12$.
* **Chain Ladder Suitability**:
  - **Highly Stable** (average $CoV < 0.05$): Chain Ladder assumptions are highly reasonable.
  - **Moderate Volatility** ($0.05 \le \text{average } CoV \le 0.12$): CL is reasonable with caution.
  - **Unstable** (average $CoV > 0.12$): CL assumptions are violated; development methods are not recommended.

---

## 3. Calendar Year Effects

### Mathematical Basis
To detect inflation and operational shifts, we evaluate deviations along calendar diagonals. For each cell $(i, j)$ where a link ratio $f_{i, j}$ exists, we calculate the relative deviation $d_{i, j}$ from the simple average $sa_j$:
$$d_{i, j} = \frac{f_{i, j}}{sa_j}$$

The calendar year of this transition is:
$$CY = AY_i + \frac{Lag_{j+1}}{12} - 1$$

We group deviations by $CY$, compute the average diagonal deviation $D_{CY}$ for each calendar year, and run a linear regression:
$$D_{CY} = \text{slope} \cdot CY + \text{intercept}$$

We calculate the $R^2$ of this regression.

### Interpretation & Thresholds
* **Calendar Year Trend**: If $|\text{slope}| > 0.005$ and $R^2 > 0.3$, a multi-year calendar trend is detected (e.g. inflation or settlement changes).
* **Calendar Year Anomaly**: Any single calendar year $CY$ where the average deviation differs from 1.0 by more than 5% ($|D_{CY} - 1.0| > 0.05$).

---

## 4. Tail Factor Diagnostics

### Mathematical Basis
We evaluate the sensitivity of reserves to the selected tail factor $T$ by recalculating CDFs and ultimates under three scenarios:
1. **No Tail**: $T = 1.0$ (no development after the oldest age).
2. **Selected**: $T = T_{selected}$.
3. **High Tail**: $T_{high} = \max(T_{selected} + 0.05, 1.0 + (T_{selected} - 1.0) \times 1.5)$.

We compute:
* Percentage change in ultimate between High Tail and Selected:
  $$\text{Sensitivity}_{high\_vs\_selected} = \frac{Ultimate_{high} - Ultimate_{selected}}{Ultimate_{selected}} \times 100$$
* Percentage change in ultimate between Selected and No Tail:
  $$\text{Sensitivity}_{selected\_vs\_no\_tail} = \frac{Ultimate_{selected} - Ultimate_{no\_tail}}{Ultimate_{no\_tail}} \times 100$$

### Interpretation & Materiality
* **High Materiality**: $\text{Sensitivity}_{high} > 5.0\%$ or $\text{Sensitivity}_{no\_tail} > 10.0\%$. Indicates significant tail uncertainty where small changes in the tail multiplier drastically shift ultimate claims.
* **Moderate Materiality**: $\text{Sensitivity}_{high} > 2.0\%$ or $\text{Sensitivity}_{no\_tail} > 4.0\%$.
* **Low Materiality**: Otherwise.

---

## 5. Outlier Detection

### Mathematical Basis
For each development column $j$, we compute the z-score of each cell factor $f_{i, j}$ relative to the column mean $\mu_j$ and standard deviation $\sigma_j$:
$$Z_{i, j} = \frac{f_{i, j} - \mu_j}{\sigma_j} \quad (\sigma_j > 0)$$

If $\sigma_j = 0$, we flag cells where $|f_{i, j} - \mu_j| / \mu_j > 0.15$ and $|f_{i, j} - \mu_j| > 0.05$ as outliers.

### Interpretation & Thresholds
Outliers are classified into severities based on $|Z_{i, j}|$:
* **Critical**: $|Z_{i, j}| > 3.0$
* **High**: $|Z_{i, j}| > 2.5$
* **Medium**: $|Z_{i, j}| > 1.8$

For each accident year, we compute an Outlier Score:
$$\text{Outlier Score}_{AY} = 10 \cdot N_{critical} + 5 \cdot N_{high} + 2 \cdot N_{medium}$$

Accident years are ranked by outlier score to identify anomalous historical periods.

---

## 6. Method Suitability scoring

The framework deterministically scores each reserving method (out of 100) based on diagnostic results:

| Method | Baseline | Penalties | Bonuses |
| :--- | :--- | :--- | :--- |
| **CL** (Chain Ladder) | 80 | - Volatility ($CoV \times 150$)<br>- Tail sensitivity (-15)<br>- Outliers (up to -30)<br>- Calendar trends (-25)<br>- Inconsistent pattern (-15) | + Low Volatility (+10) |
| **MCL** (Mack CL) | 80 | - Volatility ($CoV \times 180$)<br>- Tail sensitivity (-15)<br>- Outliers (up to -30)<br>- Calendar trends (-25)<br>- Inconsistent pattern (-15) | + Low Volatility (+10) |
| **BF** (Bornhuetter-Ferguson) | 80 (0 if no premium) | - Volatility ($CoV \times 50$)<br>- Outliers (up to -10)<br>- Calendar trends (-10) | + High Tail (+5)<br>- Immature (+10)<br>- Outliers present (+10)<br>- CY trends present (+10) |
| **CC** (Cape Cod) | 80 (0 if no premium) | - Volatility ($CoV \times 50$)<br>- Outliers (up to -10)<br>- Calendar trends (-10) | + High Tail (+5)<br>- Immature (+10)<br>- CY trends present (+10) |
| **BK** (Benktander) | 80 (0 if no premium) | - Volatility ($CoV \times 100$)<br>- Tail sensitivity (-10)<br>- Outliers (up to -15)<br>- Calendar trends (-15) | - Immature (+5) |
| **CLK** (Clark Stochastic) | 80 | - Volatility ($CoV \times 80$)<br>- Outliers (up to -20)<br>- Calendar trends (-15)<br>- Poor curve fit ($R^2 < 0.60$: -15) | + Good curve fit ($R^2 > 0.90$: +15) |
| **CO** (Case Outstanding) | 80 | - Calendar trends (-5) | None |
| **ELR** (Expected Loss Ratio) | 80 (0 if no premium) | None | + High Tail (+10)<br>+ Immature (+10)<br>+ Inconsistent pattern (+10) |

The suitability module outputs scores and arguments (pros and cons), providing raw, objective evidence to ground the Multi-Agent recommendation layer.
