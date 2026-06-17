// ================================================================
// triangle.js — Robust Triangle Data Structure + CSV Auto-Detector
// Handles wide, long, and ambiguous formats
// ================================================================

class Triangle {
  constructor() {
    this.accidentYears  = [];
    this.devAges        = [];   // in months: [12, 24, 36, ...]
    this.matrix         = [];   // matrix[i][j] = value or null
    this.dataType       = 'paid';
    this.premiums       = {};
    this.exposures      = {};
    this.counts         = {};
    this._format        = null;
    this._rawData       = {};
    this._parseLog      = [];   // diagnostic messages
  }

  // ── Main entry point ───────────────────────────────────────────
  static fromCSV(csvText) {
    const t = new Triangle();

    // 1. Detect separator
    const lines = csvText.trim().split(/\r?\n/).filter(l => l.trim().length > 0);
    if (lines.length < 2) throw new Error('CSV needs at least a header row and one data row.');

    // Guess separator by counting occurrences in header line
    const counts = { ',': 0, '\t': 0, ';': 0 };
    for (const ch of lines[0]) if (counts[ch] !== undefined) counts[ch]++;
    const sep = Object.entries(counts).sort((a,b) => b[1]-a[1])[0][0];

    // 2. Parse header
    const rawHeader = lines[0].split(sep).map(h => h.trim().replace(/^["']|["']$/g, ''));
    const header    = rawHeader.map(h => h.toLowerCase().trim());

    // 3. Parse data rows (skip fully empty rows)
    const rows = lines.slice(1)
      .filter(l => l.replace(/[,\t;"\s]/g,'').length > 0)
      .map(line => {
        const vals = line.split(sep).map(v => v.trim().replace(/^["']|["']$/g,''));
        const obj = {};
        rawHeader.forEach((h, i) => { obj[rawHeader[i]] = vals[i] || ''; });
        header.forEach((h, i)    => { obj[h]            = vals[i] || ''; });
        return obj;
      });

    if (rows.length === 0) throw new Error('No data rows found in CSV.');

    // 4. Detect format
    const FORMAT = t._detectFormat(header, rows);
    t._format = FORMAT;
    t._parseLog.push(`Detected format: ${FORMAT}`);
    t._parseLog.push(`Columns found: ${rawHeader.join(', ')}`);

    if (FORMAT === 'long') {
      t._parseLong(header, rows);
    } else {
      t._parseWide(header, rawHeader, rows);
    }

    t._buildMatrix();

    if (t.accidentYears.length === 0) {
      throw new Error(
        `Could not extract accident years from this CSV.\n\n` +
        `Columns found: ${rawHeader.join(', ')}\n\n` +
        `Expected either:\n` +
        `• Wide format: first column = accident year, remaining = development periods (12, 24, 36…)\n` +
        `• Long format: columns named accident_year/ay, dev_age/dev, paid/loss`
      );
    }

    return t;
  }

  // ── Format detection ───────────────────────────────────────────
  _detectFormat(header, rows) {
    // Long format check using flexible substring matching
    const hasDev  = header.some(h => ['dev','age','lag','period'].some(c => h.includes(c)));
    const hasAY   = header.some(h => ['accident','ay','origin','year'].some(c => h.includes(c)) && !h.includes('development'));
    const hasLoss = header.some(h => ['paid','loss','incurred','reported'].some(c => h.includes(c)));

    if (hasDev && hasAY && hasLoss) return 'long';

    // Wide format: majority of non-first columns are numeric dev ages
    const nonFirstHeaders = header.slice(1);
    const numericCols = nonFirstHeaders.filter(h => /^[\d]+$/.test(h.replace(/[m,months,mths]/gi,'')));
    if (numericCols.length >= 2) return 'wide';

    // If rows have many numeric values per row, likely wide
    const sampleRow = Object.values(rows[0]);
    const numericVals = sampleRow.filter((v, i) => i > 0 && /^[\d,\.]+$/.test(v)).length;
    if (numericVals >= 2) return 'wide';

    // If we have an AY-like first column and many columns, try wide
    return 'wide';
  }

  // ── LONG format parser ─────────────────────────────────────────
  _parseLong(header, rows) {
    // Flexible substring matching for columns
    const ayCol   = this._bestCol(header, ['accidentyear', 'accident_year','ay','origin','year']);
    const devCol  = this._bestCol(header, ['developmentlag', 'devlag', 'dev_age','dev','lag','age','period']);
    const paidCol = this._bestCol(header, ['cumpaidloss', 'paid','loss']);
    const incCol  = this._bestCol(header, ['incurloss', 'incurred','reported']);
    const cntCol  = this._bestCol(header, ['count','claims','freq']);
    const premCol = this._bestCol(header, ['earnedpremnet', 'earnedprem', 'premium','ep']);
    const expCol  = this._bestCol(header, ['exposure','units']);

    if (!ayCol || !devCol) {
      throw new Error(`Long format detected but could not find accident_year/dev_age columns. Found: ${header.join(', ')}`);
    }

    this._parseLog.push(`Long format columns → AY:${ayCol}, Dev:${devCol}, Paid:${paidCol}, Inc:${incCol}`);

    const aySet  = new Set();
    const devSet = new Set();

    rows.forEach(r => {
      const ay  = this._parseInt(r[ayCol]);
      const dev = this._parseInt(r[devCol]);
      if (ay === null || dev === null) return;
      if (ay < 1900 || ay > 2100) return; // sanity check year
      aySet.add(ay);
      devSet.add(dev);

      const key = `${ay}|${dev}`;
      this._rawData[key] = {
        paid:     paidCol ? this._num(r[paidCol]) : null,
        incurred: incCol  ? this._num(r[incCol])  : null,
        count:    cntCol  ? this._num(r[cntCol])  : null,
      };

      if (premCol && r[premCol]) { const v = this._num(r[premCol]); if (v) this.premiums[ay] = v; }
      if (expCol  && r[expCol])  { const v = this._num(r[expCol]);  if (v) this.exposures[ay] = v; }
    });

    this.accidentYears = [...aySet].sort((a,b)=>a-b);
    let devAges = [...devSet].sort((a,b)=>a-b);

    // Normalize: if max dev age ≤ 20, treat as period numbers → multiply by 12
    if (devAges.length > 0 && Math.max(...devAges) <= 20) {
      const remapped = {};
      devAges = devAges.map(d => d * 12);
      Object.keys(this._rawData).forEach(key => {
        const [ay, dev] = key.split('|');
        remapped[`${ay}|${parseInt(dev)*12}`] = this._rawData[key];
      });
      this._rawData = remapped;
    }
    this.devAges  = devAges;
    this.dataType = paidCol ? 'paid' : (incCol ? 'incurred' : 'paid');
  }

  // ── WIDE format parser ─────────────────────────────────────────
  _parseWide(header, rawHeader, rows) {
    // Find the accident year column
    const ayIdx = this._bestColIdx(header, [
      'accident_year','ay','origin','year','accident year','loss_year',
      'origin_year','ay_year','underwriting_year'
    ]);

    // If no explicit AY column found, assume column 0 is AY
    const resolvedAyIdx = ayIdx !== -1 ? ayIdx : 0;
    const ayCol = header[resolvedAyIdx];
    this._parseLog.push(`Wide format AY column: "${rawHeader[resolvedAyIdx]}" at index ${resolvedAyIdx}`);

    // All other columns are development periods
    const devColIndices = [];
    const devAges = [];

    header.forEach((h, i) => {
      if (i === resolvedAyIdx) return;
      const stripped = h.replace(/[^0-9]/g, '');
      const n = parseInt(stripped);
      if (!isNaN(n) && n > 0) {
        devColIndices.push(i);
        devAges.push(n);
      }
    });

    if (devAges.length === 0) {
      // Try treating ALL non-AY columns as sequential dev periods
      header.forEach((h, i) => {
        if (i === resolvedAyIdx) return;
        devColIndices.push(i);
        devAges.push((devAges.length + 1) * 12); // 12, 24, 36...
      });
      this._parseLog.push('No numeric dev age columns found — assigning sequential months');
    }

    // Normalize dev ages to months
    const maxAge = Math.max(...devAges);
    const normalizedAges = maxAge <= 20 ? devAges.map(d => d * 12) : devAges;
    this.devAges = [...new Set(normalizedAges)].sort((a,b)=>a-b);

    const aySet = new Set();
    let premCol = null, expCol = null;

    // Check for optional premium/exposure columns by name
    const maybePremIdx  = this._bestColIdx(header, ['premium','ep','earned_premium']);
    const maybeExpIdx   = this._bestColIdx(header, ['exposure','exposures','units']);

    rows.forEach(r => {
      const rawAY = r[header[resolvedAyIdx]] ?? r[rawHeader[resolvedAyIdx]];
      const ay = this._parseInt(rawAY);
      if (ay === null || ay < 1900 || ay > 2100) return;
      aySet.add(ay);

      devColIndices.forEach((colIdx, j) => {
        const colName = header[colIdx];
        const rawColName = rawHeader[colIdx];
        const val = this._num(r[colName] ?? r[rawColName]);
        if (val !== null && !isNaN(val)) {
          const age = normalizedAges[j];
          this._rawData[`${ay}|${age}`] = { paid: val, incurred: null, count: null };
        }
      });

      if (maybePremIdx !== -1) {
        const v = this._num(r[header[maybePremIdx]] ?? r[rawHeader[maybePremIdx]]);
        if (v) this.premiums[ay] = v;
      }
      if (maybeExpIdx !== -1) {
        const v = this._num(r[header[maybeExpIdx]] ?? r[rawHeader[maybeExpIdx]]);
        if (v) this.exposures[ay] = v;
      }
    });

    this.accidentYears = [...aySet].sort((a,b)=>a-b);
    this.dataType = 'paid';
    this._parseLog.push(`Parsed ${this.accidentYears.length} AYs, ${this.devAges.length} dev periods`);
  }

  // ── Build triangle matrix ──────────────────────────────────────
  _buildMatrix() {
    this.matrix = this.accidentYears.map(ay =>
      this.devAges.map(dev => {
        const cell = this._rawData[`${ay}|${dev}`];
        if (!cell) return null;
        const v = cell.paid;
        return (v !== null && !isNaN(v)) ? v : null;
      })
    );

    this.incurredMatrix = this.accidentYears.map(ay =>
      this.devAges.map(dev => {
        const cell = this._rawData[`${ay}|${dev}`];
        return cell?.incurred ?? null;
      })
    );

    this.accidentYears.forEach(ay => {
      // Try to get count from last known dev period
      for (let j = this.devAges.length - 1; j >= 0; j--) {
        const cell = this._rawData[`${ay}|${this.devAges[j]}`];
        if (cell?.count != null) { this.counts[ay] = cell.count; break; }
      }
    });
  }

  // ── Latest diagonal ────────────────────────────────────────────
  getLatestDiagonal() {
    return this.matrix.map(row => {
      for (let j = row.length - 1; j >= 0; j--) {
        if (row[j] !== null && !isNaN(row[j])) return row[j];
      }
      return null;
    });
  }

  // ── Current dev index per AY ───────────────────────────────────
  getCurrentDevIndex() {
    return this.matrix.map(row => {
      for (let j = row.length - 1; j >= 0; j--) {
        if (row[j] !== null && !isNaN(row[j])) return j;
      }
      return 0;
    });
  }

  // ── Compute LDFs with multiple average types ───────────────────
  computeLDFs() {
    const n = this.devAges.length;
    const ldfs = [];

    for (let j = 0; j < n - 1; j++) {
      let sumNumer = 0, sumDenom = 0;
      const colFactors = [];

      this.matrix.forEach(row => {
        const cur = row[j];
        const nxt = row[j + 1];
        if (cur != null && nxt != null && !isNaN(cur) && !isNaN(nxt) && cur > 0) {
          sumNumer += nxt;
          sumDenom += cur;
          colFactors.push({ from: cur, to: nxt, factor: nxt / cur });
        }
      });

      const n_pts = colFactors.length;
      const factors = colFactors.map(f => f.factor);
      const vw  = sumDenom > 0 ? sumNumer / sumDenom : null;
      const sa  = n_pts > 0 ? factors.reduce((a,b)=>a+b,0) / n_pts : null;
      const mean = sa;
      const variance = n_pts > 1
        ? factors.reduce((a,f)=>a+(f-mean)**2, 0) / (n_pts-1) : 0;
      const std = Math.sqrt(variance);
      const cov = mean > 0 ? std/mean : 0;

      // Weighted by recency (last 3 years, last 5 years)
      const last3 = colFactors.slice(-3);
      const last5 = colFactors.slice(-5);
      const wa3 = last3.length > 0
        ? last3.reduce((s,f)=>s+f.to,0) / last3.reduce((s,f)=>s+f.from,0) : null;
      const wa5 = last5.length > 0
        ? last5.reduce((s,f)=>s+f.to,0) / last5.reduce((s,f)=>s+f.from,0) : null;

      ldfs.push({
        fromAge: this.devAges[j],
        toAge:   this.devAges[j + 1],
        volumeWeighted: vw,
        straightAvg:    sa,
        weighted3yr:    wa3,
        weighted5yr:    wa5,
        individualFactors: factors,
        std, cov,
        sigmaSquared: variance,
        n: n_pts,
        isTail: false,
      });
    }

    // Tail factor = 1.000
    ldfs.push({
      fromAge: this.devAges[n - 1],
      toAge:   'Ultimate',
      volumeWeighted: 1.0,
      straightAvg:    1.0,
      weighted3yr:    1.0,
      weighted5yr:    1.0,
      individualFactors: [],
      std: 0, cov: 0, sigmaSquared: 0, n: 0,
      isTail: true,
    });

    return ldfs;
  }

  // ── CDFs from LDFs ─────────────────────────────────────────────
  computeCDFs(ldfs) {
    const n = ldfs.length;
    const cdfs = new Array(n).fill(1.0);
    cdfs[n-1] = ldfs[n-1];
    for (let j = n-2; j >= 0; j--) cdfs[j] = ldfs[j] * cdfs[j+1];
    return cdfs;
  }

  computePctReported(cdfs) {
    return cdfs.map(c => c > 0 ? 1.0/c : 0);
  }

  // ── Summary stats ──────────────────────────────────────────────
  getSummary() {
    const n    = this.accidentYears.length;
    const m    = this.devAges.length;
    const diag = this.getLatestDiagonal();
    const totalPaid = diag.reduce((s,v)=>s+(v||0), 0);

    const filled   = this.matrix.flat().filter(v => v !== null).length;
    const upperTri = Math.min(n*(n+1)/2, n*m);
    const completeness = upperTri > 0 ? (filled / upperTri * 100).toFixed(1) : '0.0';

    return {
      accidentYears: n,
      devPeriods:    m,
      oldestAY:      this.accidentYears[0],
      latestAY:      this.accidentYears[n-1],
      maxDevAge:     m > 0 ? Math.max(...this.devAges) : 0,
      totalPaid,
      completeness,
      isNewLOB:      n <= 3,
      isLongTail:    m > 7,
      hasPremium:    Object.keys(this.premiums).length > 0,
      hasExposure:   Object.keys(this.exposures).length > 0,
      hasCounts:     Object.values(this.counts).some(v => v != null),
      format:        this._format,
      dataType:      this.dataType,
      parseLog:      this._parseLog,
    };
  }

  // ── Helpers ────────────────────────────────────────────────────
  _bestCol(header, candidates) {
    // 1. Exact match
    for (const c of candidates) {
      const match = header.find(h => h === c);
      if (match) return match;
    }
    // 2. Substring match
    for (const c of candidates) {
      const match = header.find(h => h.includes(c));
      if (match) return match;
    }
    return null;
  }

  _bestColIdx(header, candidates) {
    for (const c of candidates) {
      const idx = header.indexOf(c);
      if (idx !== -1) return idx;
    }
    // Partial match
    for (const c of candidates) {
      const idx = header.findIndex(h => h.includes(c));
      if (idx !== -1) return idx;
    }
    return -1;
  }

  _parseInt(val) {
    if (val == null || val === '') return null;
    const n = parseInt(String(val).replace(/[^0-9]/g,''));
    return isNaN(n) ? null : n;
  }

  _num(val) {
    if (val == null || val === '' || val === '-' || val === 'NA' || val === 'N/A') return null;
    const n = parseFloat(String(val).replace(/[$,%\s,]/g,'').replace(/\((.+)\)/, '-$1'));
    return isNaN(n) ? null : n;
  }
}
