// ================================================================
// methods.js — Reserving Method Classes (chainladder-python parity)
// Mirrors: casact/chainladder-python/chainladder/methods/
// ================================================================

// ── Base Class ────────────────────────────────────────────────────
class MethodBase {
  constructor() {
    this.triangle = null;
    this.selectedLDFs = null;
    this.cdfs = null;
    this.pctReported = null;
    this._fitted = false;
  }

  // Returns list of extra params this method needs from the user
  static getRequiredParams() { return []; }

  // Fit: computes LDFs and CDFs (most methods share this)
  fit(triangle, params = {}, customLDFs = null) {
    this.triangle = triangle;
    this.params = params;
    const ldfStats = triangle.computeLDFs();

    // Use custom (user-overridden) LDFs if provided, else volume-weighted
    this.selectedLDFs = customLDFs
      ? customLDFs
      : ldfStats.map(s => s.volumeWeighted ?? 1.0);

    this.ldfStats = ldfStats;
    this.cdfs = triangle.computeCDFs(this.selectedLDFs);
    this.pctReported = triangle.computePctReported(this.cdfs);
    this._compute(params);
    this._fitted = true;
    return this;
  }

  // Subclasses implement this
  _compute(params) { throw new Error('_compute() must be implemented'); }

  getUltimate() { return this._ultimate; }
  getIBNR() { return this._ibnr; }
  getLatestDiagonal() { return this.triangle.getLatestDiagonal(); }

  // Shared: formats results per AY
  getResults() {
    const ays = this.triangle.accidentYears;
    const diag = this.getLatestDiagonal();
    const devIdx = this.triangle.getCurrentDevIndex();
    return ays.map((ay, i) => ({
      ay,
      paid: diag[i],
      ultimate: this._ultimate[i],
      ibnr: this._ibnr[i],
      pctReported: this.pctReported ? (this.pctReported[devIdx[i]] * 100).toFixed(1) : null,
      cdfToUlt: this.cdfs ? this.cdfs[devIdx[i]]?.toFixed(4) : null,
    }));
  }

  getTotalIBNR() {
    return this._ibnr.reduce((s, v) => s + (v ?? 0), 0);
  }

  getTotalUltimate() {
    return this._ultimate.reduce((s, v) => s + (v ?? 0), 0);
  }
}

// ── 1. Chain Ladder (Deterministic) ──────────────────────────────
// Source: chainladder/methods/chainladder.py
// Ultimate = latest_diagonal × CDF_to_ultimate
class ChainLadder extends MethodBase {
  static label = 'Chain Ladder';
  static code  = 'CL';
  static description = 'Basic deterministic chain ladder. Projects ultimates using volume-weighted average age-to-age factors.';
  static longTailOk  = true;
  static needsPremium = false;

  static getRequiredParams() { return []; }

  _compute(params) {
    const diag   = this.getLatestDiagonal();
    const devIdx = this.triangle.getCurrentDevIndex();
    this._ultimate = diag.map((d, i) => d !== null ? d * this.cdfs[devIdx[i]] : null);
    this._ibnr     = diag.map((d, i) => this._ultimate[i] !== null ? this._ultimate[i] - d : null);
  }
}

// ── 2. Mack Chain Ladder (Stochastic) ────────────────────────────
// Source: chainladder/methods/mack.py
// Adds standard error and confidence intervals to CL
class MackChainladder extends MethodBase {
  static label = 'Mack Chain Ladder';
  static code  = 'MCL';
  static description = 'Stochastic extension of chain ladder. Produces point estimates AND standard errors / confidence intervals for each accident year.';
  static longTailOk  = true;
  static needsPremium = false;

  static getRequiredParams() { return []; }

  _compute(params) {
    const diag   = this.getLatestDiagonal();
    const devIdx = this.triangle.getCurrentDevIndex();
    const n      = this.triangle.accidentYears.length;
    const m      = this.triangle.devAges.length;

    // Chain Ladder ultimates
    this._ultimate = diag.map((d, i) => d !== null ? d * this.cdfs[devIdx[i]] : null);
    this._ibnr     = diag.map((d, i) => this._ultimate[i] !== null ? this._ultimate[i] - d : null);

    // Mack's process variance: σ²_j = variance of (f_ij / f_j - 1) × C_ij
    // Simplified: use LDF sigma² from triangle.computeLDFs()
    const sigmas = this.ldfStats.map(s => Math.sqrt(s.sigmaSquared ?? 0));

    // Standard error per AY (Mack 1993 formula - simplified)
    this._stdError = diag.map((d, i) => {
      if (d === null) return null;
      let variance = 0;
      const curDev = devIdx[i];
      // Sum variance contributions from each future development period
      for (let j = curDev; j < m - 1; j++) {
        const cdf_j = this.cdfs[j]; // CDF at period j
        const sigma_j = sigmas[j] ?? 0;
        if (cdf_j > 0 && d > 0) {
          // Mack's approximation
          const nj = this.ldfStats[j].n;
          // Variance component: sigma²_j / (f_j² × C_ij)
          const f_j = this.selectedLDFs[j];
          const sumC = this.triangle.matrix.slice(0, n - j - 1).reduce((s, row) => s + (row[j] ?? 0), 0);
          variance += (sigma_j ** 2 / (f_j ** 2)) * (1 / Math.max(d, 1) + (sumC > 0 ? 1 / sumC : 0));
        }
      }
      return this._ultimate[i] * Math.sqrt(variance);
    });

    this._cv = this._ultimate.map((u, i) =>
      u && this._stdError[i] ? (this._stdError[i] / u * 100).toFixed(1) : null
    );
  }

  getResults() {
    const base = super.getResults();
    return base.map((r, i) => ({
      ...r,
      stdError: this._stdError ? this._stdError[i] : null,
      cv: this._cv ? this._cv[i] : null,
      ibnr_75: this._ibnr[i] && this._stdError[i]
        ? this._ibnr[i] + 0.674 * this._stdError[i] : null, // ~75th pctile
      ibnr_95: this._ibnr[i] && this._stdError[i]
        ? this._ibnr[i] + 1.645 * this._stdError[i] : null, // ~95th pctile
    }));
  }
}

// ── 3. Bornhuetter-Ferguson ───────────────────────────────────────
// Source: chainladder/methods/bornferg.py
// Ultimate = Paid + (1 − q) × ExpectedUltimate
// where ExpectedUltimate = Premium × a_priori_ELR
class BornhuetterFerguson extends MethodBase {
  static label = 'Bornhuetter-Ferguson';
  static code  = 'BF';
  static description = 'Blends a priori expected losses (ELR × Premium) with observed paid. Ideal for immature accident years or volatile triangles.';
  static longTailOk  = true;
  static needsPremium = true;

  static getRequiredParams() {
    return [
      {
        key: 'aprioriELR',
        label: 'A Priori Expected Loss Ratio (ELR)',
        type: 'percent',
        hint: 'Your best estimate of the expected loss ratio before seeing the data. Typically from pricing or prior year analysis.',
        default: 65.0,
        min: 1, max: 999,
      }
    ];
  }

  _compute(params) {
    const diag    = this.getLatestDiagonal();
    const devIdx  = this.triangle.getCurrentDevIndex();
    const elr     = (params.aprioriELR ?? 65.0) / 100;
    const ays     = this.triangle.accidentYears;
    const premiums = this.triangle.premiums;

    this._ultimate = diag.map((d, i) => {
      if (d === null) return null;
      const q   = this.pctReported[devIdx[i]]; // % reported
      const prem = premiums[ays[i]] ?? 0;
      const expectedUlt = prem * elr;
      return d + (1 - q) * expectedUlt;
    });
    this._ibnr = diag.map((d, i) =>
      this._ultimate[i] !== null ? this._ultimate[i] - d : null
    );

    // Store for display
    this._elr = elr;
  }

  getResults() {
    const base = super.getResults();
    const ays = this.triangle.accidentYears;
    const premiums = this.triangle.premiums;
    return base.map((r, i) => ({
      ...r,
      expectedUlt: (premiums[ays[i]] ?? 0) * this._elr,
      elr: (this._elr * 100).toFixed(1) + '%',
    }));
  }
}

// ── 4. Benktander (Iterated BF) ───────────────────────────────────
// Source: chainladder/methods/bornferg.py (n_iters param)
// Uk = Paid + (1−q) × U(k−1), starting from U0 = Premium × ELR
class Benktander extends MethodBase {
  static label = 'Benktander';
  static code  = 'GB';
  static description = 'Iterative refinement of the BF method. Each iteration moves the estimate closer to Chain Ladder. Standard: 2 iterations (Gunnar Benktander).';
  static longTailOk  = true;
  static needsPremium = true;

  static getRequiredParams() {
    return [
      {
        key: 'aprioriELR',
        label: 'A Priori ELR',
        type: 'percent',
        hint: 'Expected loss ratio used as the starting point for iterations.',
        default: 65.0,
        min: 1, max: 999,
      },
      {
        key: 'nIters',
        label: 'Number of Iterations',
        type: 'integer',
        hint: '2 = standard Benktander. Higher values converge to Chain Ladder.',
        default: 2,
        min: 1, max: 20,
      }
    ];
  }

  _compute(params) {
    const diag    = this.getLatestDiagonal();
    const devIdx  = this.triangle.getCurrentDevIndex();
    const elr     = (params.aprioriELR ?? 65.0) / 100;
    const nIters  = parseInt(params.nIters ?? 2);
    const ays     = this.triangle.accidentYears;
    const premiums = this.triangle.premiums;

    this._ultimate = diag.map((d, i) => {
      if (d === null) return null;
      const q   = this.pctReported[devIdx[i]];
      const prem = premiums[ays[i]] ?? 0;
      let ult = prem * elr; // U0 = a priori
      for (let k = 0; k < nIters; k++) {
        ult = d + (1 - q) * ult; // Uk = Paid + (1-q) × U(k-1)
      }
      return ult;
    });
    this._ibnr = diag.map((d, i) =>
      this._ultimate[i] !== null ? this._ultimate[i] - d : null
    );
  }
}

// ── 5. Cape Cod ───────────────────────────────────────────────────
// Source: chainladder/methods/capecod.py
// Derives ELR from the data: ELR_CC = ΣPaid / Σ(Premium × q)
// Then applies BF with this ELR
class CapeCod extends MethodBase {
  static label = 'Cape Cod';
  static code  = 'CC';
  static description = 'Derives the ELR from the triangle itself (no a priori input needed). More objective than BF but requires premium data.';
  static longTailOk  = true;
  static needsPremium = true;

  static getRequiredParams() { return []; }

  _compute(params) {
    const diag    = this.getLatestDiagonal();
    const devIdx  = this.triangle.getCurrentDevIndex();
    const ays     = this.triangle.accidentYears;
    const premiums = this.triangle.premiums;

    // Compute Cape Cod ELR
    let sumPaid = 0, sumUsedPrem = 0;
    diag.forEach((d, i) => {
      const q    = this.pctReported[devIdx[i]];
      const prem = premiums[ays[i]] ?? 0;
      sumPaid    += d ?? 0;
      sumUsedPrem += prem * q;
    });
    this._capeCodELR = sumUsedPrem > 0 ? sumPaid / sumUsedPrem : 0;

    // Apply BF with derived ELR
    this._ultimate = diag.map((d, i) => {
      if (d === null) return null;
      const q   = this.pctReported[devIdx[i]];
      const prem = premiums[ays[i]] ?? 0;
      return d + (1 - q) * this._capeCodELR * prem;
    });
    this._ibnr = diag.map((d, i) =>
      this._ultimate[i] !== null ? this._ultimate[i] - d : null
    );
  }

  getResults() {
    const base = super.getResults();
    return base.map(r => ({
      ...r,
      capeCodELR: (this._capeCodELR * 100).toFixed(2) + '%',
    }));
  }

  getCapeCodELR() { return this._capeCodELR; }
}

// ── 6. Case Outstanding ───────────────────────────────────────────
// Uses case reserves (Incurred − Paid) + IBNR loading
// IBNR = CaseReserve × ibnrLoad + Paid × ulae%
class CaseOutstanding extends MethodBase {
  static label = 'Case Outstanding';
  static code  = 'CASE';
  static description = 'Uses case reserves as the primary IBNR driver, with an explicit IBNR load factor applied on top. Useful when case reserve adequacy is well understood.';
  static longTailOk  = false;
  static needsPremium = false;

  static getRequiredParams() {
    return [
      {
        key: 'ibnrLoad',
        label: 'IBNR Load Factor (on Case Reserves)',
        type: 'percent',
        hint: 'Factor applied to outstanding case reserves to derive IBNR. E.g. 15% means IBNR = 15% of case reserves.',
        default: 15.0,
        min: 0, max: 200,
      },
      {
        key: 'ulae',
        label: 'ULAE Factor (on Paid Losses)',
        type: 'percent',
        hint: 'Unallocated Loss Adjustment Expenses as % of paid losses. Usually 5–10%.',
        default: 5.0,
        min: 0, max: 50,
      }
    ];
  }

  _compute(params) {
    const paidDiag     = this.triangle.getLatestDiagonal();
    const n            = this.triangle.accidentYears.length;
    const ibnrLoad     = (params.ibnrLoad ?? 15.0) / 100;
    const ulae         = (params.ulae ?? 5.0) / 100;

    // Get incurred diagonal
    const incurredDiag = this.triangle.accidentYears.map((ay, i) => {
      const row = this.triangle.incurredMatrix?.[i] ?? [];
      for (let j = row.length - 1; j >= 0; j--) {
        if (row[j] !== null && !isNaN(row[j])) return row[j];
      }
      return paidDiag[i]; // fallback: use paid
    });

    this._caseReserves = paidDiag.map((p, i) => Math.max(0, (incurredDiag[i] ?? p) - (p ?? 0)));
    this._ultimate = paidDiag.map((p, i) => {
      if (p === null) return null;
      const ibnr = this._caseReserves[i] * ibnrLoad + p * ulae;
      return p + this._caseReserves[i] + ibnr;
    });
    this._ibnr = paidDiag.map((p, i) =>
      this._ultimate[i] !== null ? this._ultimate[i] - p : null
    );
  }

  getResults() {
    const base = super.getResults();
    return base.map((r, i) => ({
      ...r,
      caseReserve: this._caseReserves[i],
    }));
  }
}

// ── 7. Clark LDF (Parametric) ─────────────────────────────────────
// Source: chainladder/methods/clark.py
// Fits a loglogistic growth curve G(age; ω, θ) to % paid emergence
// G(age) = age^ω / (age^ω + θ^ω)
class Clark extends MethodBase {
  static label = 'Clark LDF';
  static code  = 'CLARK';
  static description = 'Parametric method using a loglogistic (or Weibull) growth curve. Smooths noisy emergence patterns. Useful for long-tail lines with scarce data.';
  static longTailOk  = true;
  static needsPremium = false;

  static getRequiredParams() {
    return [
      {
        key: 'growthCurve',
        label: 'Growth Curve',
        type: 'select',
        options: ['Loglogistic', 'Weibull'],
        hint: 'Loglogistic is symmetric; Weibull is skewed. Loglogistic is most common in practice.',
        default: 'Loglogistic',
      }
    ];
  }

  // Loglogistic: G(t) = t^ω / (t^ω + θ^ω)
  _loglogistic(t, omega, theta) {
    const tOmega = Math.pow(Math.max(t, 0.001), omega);
    const thetaOmega = Math.pow(theta, omega);
    return tOmega / (tOmega + thetaOmega);
  }

  // Weibull: G(t) = 1 − exp(−(t/θ)^ω)
  _weibull(t, omega, theta) {
    return 1 - Math.exp(-Math.pow(t / theta, omega));
  }

  // Grid search to fit omega and theta
  _fitParams(useLoglogistic) {
    const G = useLoglogistic ? this._loglogistic.bind(this) : this._weibull.bind(this);
    const observations = [];

    this.triangle.matrix.forEach((row, i) => {
      const ultimate = row.filter(v => v !== null).slice(-1)[0];
      if (!ultimate || ultimate === 0) return;
      this.triangle.devAges.forEach((age, j) => {
        if (row[j] !== null && !isNaN(row[j]) && row[j] > 0) {
          observations.push({ age, pct: row[j] / ultimate });
        }
      });
    });

    let bestOmega = 1.5, bestTheta = 48, bestSSE = Infinity;
    for (let omega = 0.3; omega <= 6; omega += 0.15) {
      for (let theta = 6; theta <= 200; theta += 4) {
        let sse = 0;
        observations.forEach(({ age, pct }) => {
          sse += (pct - G(age, omega, theta)) ** 2;
        });
        if (sse < bestSSE) { bestSSE = sse; bestOmega = omega; bestTheta = theta; }
      }
    }
    return { omega: bestOmega, theta: bestTheta, sse: bestSSE, G };
  }

  _compute(params) {
    const useLogi = (params.growthCurve ?? 'Loglogistic') === 'Loglogistic';
    const { omega, theta, G } = this._fitParams(useLogi);
    this._omega = omega;
    this._theta = theta;

    const diag   = this.getLatestDiagonal();
    const devIdx = this.triangle.getCurrentDevIndex();
    const devAges = this.triangle.devAges;

    this._ultimate = diag.map((d, i) => {
      if (d === null) return null;
      const currentAge = devAges[devIdx[i]];
      const pctAtCurrentAge = G(currentAge, omega, theta);
      return pctAtCurrentAge > 0 ? d / pctAtCurrentAge : d;
    });
    this._ibnr = diag.map((d, i) =>
      this._ultimate[i] !== null ? this._ultimate[i] - d : null
    );

    // Build Clark CDFs for display
    this._clarkCDFs = devAges.map(age => {
      const pct = G(age, omega, theta);
      return pct > 0 ? 1 / pct : 1;
    });
  }

  getParams() { return { omega: this._omega?.toFixed(3), theta: this._theta?.toFixed(1) }; }
}

// ── Method Registry ──────────────────────────────────────────────
const METHODS = {
  CL:    ChainLadder,
  MCL:   MackChainladder,
  BF:    BornhuetterFerguson,
  GB:    Benktander,
  CC:    CapeCod,
  CASE:  CaseOutstanding,
  CLARK: Clark,
};

// ── Recommendation Engine ─────────────────────────────────────────
function recommendMethod(triangle) {
  const summary = triangle.getSummary();
  const ldfStats = triangle.computeLDFs();
  const n = summary.accidentYears;
  const scores = {};
  const reasons = {};
  const warnings = [];

  // Initialize
  Object.keys(METHODS).forEach(k => { scores[k] = 0; reasons[k] = []; });

  // 1. Data maturity
  if (n >= 7) {
    scores.CL += 3; scores.MCL += 3;
    reasons.CL.push('Sufficient history (≥7 AYs) for stable chain ladder factors.');
    reasons.MCL.push('Good history to estimate variance parameters reliably.');
  } else if (n <= 3) {
    scores.BF += 3; scores.ELR += 2; scores.GB += 2;
    reasons.BF.push('Short history — a priori ELR gives stability where data is sparse.');
    warnings.push(`Only ${n} accident years — chain ladder LDFs may be unreliable.`);
  } else {
    scores.CL += 1; scores.BF += 1; scores.GB += 2;
    reasons.GB.push('Moderate history — Benktander offers a balanced blend of CL and BF.');
  }

  // 2. LDF stability (CoV)
  const unstable = ldfStats.filter(s => !s.isTail && s.cov > 0.15);
  if (unstable.length === 0) {
    scores.CL += 2; scores.MCL += 1;
    reasons.CL.push('LDFs are stable (CoV < 15% at all ages).');
  } else if (unstable.length >= 2) {
    scores.BF += 2; scores.GB += 1;
    reasons.BF.push(`${unstable.length} development periods have volatile factors (CoV > 15%). BF reduces sensitivity to noisy LDFs.`);
    warnings.push('High LDF volatility detected. Consider BF or Benktander.');
  }

  // 3. Premium data
  if (summary.hasPremium) {
    scores.CC += 2; scores.BF += 1; scores.GB += 1;
    reasons.CC.push('Premium data available — Cape Cod ELR can be derived objectively from the data.');
  } else {
    scores.CASE += 1;
    warnings.push('No premium data detected. BF and Cape Cod require premiums.');
  }

  // 4. New LOB
  if (summary.isNewLOB) {
    scores.BF += 2; scores.CLARK += 1;
    reasons.BF.push('New/short-tail LOB — a priori rates are more credible than sparse data.');
    warnings.push('New line of business detected. Chain Ladder may not be credible.');
  }

  // 5. Long tail
  if (summary.isLongTail) {
    scores.CLARK += 2; scores.MCL += 1;
    reasons.CLARK.push('Long-tail line benefits from parametric growth curve smoothing.');
  }

  // 6. Incurred data
  if (summary.hasCounts) {
    scores.CASE += 1;
    reasons.CASE.push('Claim count data available for case reserve analysis.');
  }

  // Pick top
  const ranked = Object.entries(scores)
    .sort((a, b) => b[1] - a[1])
    .map(([code, score]) => ({
      code, score,
      label: METHODS[code].label,
      description: METHODS[code].description,
      reasons: reasons[code],
      recommended: false,
    }));
  ranked[0].recommended = true;

  return { ranked, warnings, summary };
}
