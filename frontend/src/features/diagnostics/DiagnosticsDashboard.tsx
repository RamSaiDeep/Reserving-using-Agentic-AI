'use client';
import React, { useMemo } from 'react';
import { fmt, fmtShort } from '@/lib/utils';

interface CellOutlier {
  ay: number;
  lag: number;
  value: number;
  median: number;
  ratio: number;
  severity: 'Critical' | 'High' | 'Moderate' | 'Low';
  reason: string;
}

interface DiagnosticsData {
  reporting_pattern?: {
    best_fit_curve: string;
    fit_metrics?: { r2: number; rmse: number };
    reporting_consistency?: string;
    significant_deviations?: number[];
  };
  ldf_stability?: {
    cov_by_age?: Record<string, number> | number[];
    average_cov?: number;
    unstable_periods?: string[];
    cl_suitable_indicator?: string;
    cl_assumptions_reasonable?: boolean;
  };
  calendar_effects?: {
    calendar_years?: number[];
    slope?: number;
    r_squared?: number;
    trend_detected?: boolean;
    anomalies?: string[];
  };
  tail_analysis?: {
    selected_tail?: number;
    high_tail?: number;
    tail_uncertainty_materiality?: 'High' | 'Moderate' | 'Low';
  };
  outliers?: {
    cell_outliers?: CellOutlier[];
    accident_year_ranking?: { ay: number; score: number }[];
  };
  suitability?: {
    scores?: Record<string, number>;
    pros?: Record<string, string[]>;
    cons?: Record<string, string[]>;
  };
}

interface DiagnosticsDashboardProps {
  diagnostics: DiagnosticsData | null;
  isLoading?: boolean;
}

export default function DiagnosticsDashboard({ diagnostics, isLoading = false }: DiagnosticsDashboardProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 space-y-4">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-accent"></div>
        <p className="text-sm font-mono text-text-sub">Loading advanced actuarial diagnostics...</p>
      </div>
    );
  }

  if (!diagnostics || Object.keys(diagnostics).length === 0) {
    return (
      <div className="flex flex-col items-center justify-center border border-dashed border-border rounded-xl h-64 text-center p-6 bg-bg-1">
        <p className="text-sm text-text-sub font-mono font-bold">No diagnostics data available.</p>
        <p className="text-xs text-text-muted mt-1 leading-normal max-w-sm">
          Run the reserving pipeline or upload a dataset to calculate deterministic diagnostics and suitability scores.
        </p>
      </div>
    );
  }

  const {
    reporting_pattern: rep = {} as NonNullable<DiagnosticsData['reporting_pattern']>,
    ldf_stability: stab = {} as NonNullable<DiagnosticsData['ldf_stability']>,
    calendar_effects: cal = {} as NonNullable<DiagnosticsData['calendar_effects']>,
    tail_analysis: tail = {} as NonNullable<DiagnosticsData['tail_analysis']>,
    outliers: out = {} as NonNullable<DiagnosticsData['outliers']>,
    suitability: suit = {} as NonNullable<DiagnosticsData['suitability']>
  } = diagnostics || {};


  return (
    <div className="space-y-6 text-left font-sans">
      <div>
        <h2 className="text-xl font-bold text-text-main">Actuarial Diagnostics Dashboard</h2>
        <p className="text-xs text-text-sub mt-0.5">Statistical assessments and mathematical model suitability scores.</p>
      </div>

      {/* Grid of Key Diagnostics Indicators */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {/* LDF Stability */}
        <div className="bg-bg-1 border border-border rounded-xl p-4 flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">LDF Stability</span>
            <h4 className="text-sm font-bold text-text-main mt-1">
              {stab.cl_suitable_indicator || "Unknown"}
            </h4>
          </div>
          <div className="mt-4 text-[11px] text-text-sub">
            Avg CoV: <span className="font-mono font-bold text-accent">{stab?.average_cov != null ? Number(stab.average_cov).toFixed(3) : "0.000"}</span>
          </div>
        </div>

        {/* Curve Fitting */}
        <div className="bg-bg-1 border border-border rounded-xl p-4 flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">Pattern Curve</span>
            <h4 className="text-sm font-bold text-text-main mt-1 capitalize">
              {rep.best_fit_curve || "None"}
            </h4>
          </div>
          <div className="mt-4 text-[11px] text-text-sub">
            R²: <span className="font-mono font-bold text-accent">{rep?.fit_metrics?.r2 != null ? Number(rep.fit_metrics.r2).toFixed(3) : "N/A"}</span>
          </div>
        </div>

        {/* Calendar Effect */}
        <div className="bg-bg-1 border border-border rounded-xl p-4 flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">Calendar Trend</span>
            <h4 className="text-sm font-bold text-text-main mt-1">
              {cal.trend_detected ? "DETECTED" : "STABLE"}
            </h4>
          </div>
          <div className="mt-4 text-[11px] text-text-sub">
            Slope: <span className="font-mono font-bold text-accent">{cal?.slope != null ? Number(cal.slope).toFixed(4) : "0.0000"}</span>
          </div>
        </div>

        {/* Tail Materiality */}
        <div className="bg-bg-1 border border-border rounded-xl p-4 flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">Tail Materiality</span>
            <h4 className="text-sm font-bold mt-1 tracking-wide uppercase">
              <span className={
                tail.tail_uncertainty_materiality === 'High' ? 'text-accent-red font-extrabold' :
                tail.tail_uncertainty_materiality === 'Moderate' ? 'text-accent-amber font-extrabold' : 'text-accent-green font-extrabold'
              }>
                {tail.tail_uncertainty_materiality || "Low"}
              </span>
            </h4>
          </div>
          <div className="mt-4 text-[11px] text-text-sub">
            Selected vs High: <span className="font-mono text-accent">{tail?.selected_tail != null ? Number(tail.selected_tail).toFixed(3) : "1.000"}</span> vs <span className="font-mono text-text-muted">{tail?.high_tail != null ? Number(tail.high_tail).toFixed(3) : "1.000"}</span>
          </div>
        </div>

        {/* Outlier Count */}
        <div className="bg-bg-1 border border-border rounded-xl p-4 flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">Data Outliers</span>
            <h4 className="text-sm font-bold text-text-main mt-1">
              {out.cell_outliers?.length || 0} Cell{out.cell_outliers?.length === 1 ? '' : 's'}
            </h4>
          </div>
          <div className="mt-4 text-[11px] text-text-sub">
            Anomalies: <span className="font-bold text-accent-amber">{out.cell_outliers?.filter(c => c.severity === 'Critical' || c.severity === 'High').length || 0} Urgent</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Method Suitability Scores */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-bg-1 border border-border rounded-xl p-5 shadow-sm">
            <h3 className="text-xs font-bold text-text-main uppercase tracking-wider mb-4 border-b border-border pb-2">
              Model Suitability Scores
            </h3>
            <div className="space-y-4">
              {suit.scores && Object.entries(suit.scores).map(([method, score]) => {
                const prosList = suit.pros?.[method] || [];
                const consList = suit.cons?.[method] || [];
                return (
                  <div key={method} className="border-b border-border last:border-none pb-4 last:pb-0">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-accent text-sm w-12">{method}</span>
                        <span className="text-xs font-semibold text-text-main">
                          {method === 'CL' ? 'Chain Ladder' :
                           method === 'MCL' ? 'Mack Chain Ladder' :
                           method === 'BF' ? 'Bornhuetter-Ferguson' :
                           method === 'BK' ? 'Benktander' :
                           method === 'CC' ? 'Cape Cod' :
                           method === 'CO' ? 'Case Outstanding' :
                           method === 'CLK' ? 'Clark Stochastic' :
                           method === 'ELR' ? 'Expected Loss Ratio' : 'Frequency-Severity'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-text-sub">{score} / 100</span>
                      </div>
                    </div>
                    {/* Suitability score bar */}
                    <div className="h-1.5 bg-bg-2 rounded-full mb-3">
                      <div
                        className="h-full bg-accent rounded-full transition-all duration-500"
                        style={{ width: `${score}%` }}
                      />
                    </div>
                    {/* Pros and Cons */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[11px] leading-relaxed mt-2 pl-14">
                      {prosList.length > 0 && (
                        <div>
                          <span className="text-accent-green font-bold block mb-1">✓ Advantages:</span>
                          <ul className="list-disc pl-4 text-text-sub space-y-0.5">
                            {prosList.map((p, i) => <li key={i}>{p}</li>)}
                          </ul>
                        </div>
                      )}
                      {consList.length > 0 && (
                        <div>
                          <span className="text-accent-red font-bold block mb-1">✗ Limitations:</span>
                          <ul className="list-disc pl-4 text-text-sub space-y-0.5">
                            {consList.map((c, i) => <li key={i}>{c}</li>)}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Detailed Diagnostics Lists */}
        <div className="flex flex-col gap-6">
          {/* Outliers Table */}
          <div className="bg-bg-1 border border-border rounded-xl p-5 shadow-sm flex-1">
            <h3 className="text-xs font-bold text-text-main uppercase tracking-wider mb-3 border-b border-border pb-2">
              Detected Anomalies & Outliers
            </h3>
            {out.cell_outliers && out.cell_outliers.length > 0 ? (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {out.cell_outliers.map((c, i) => {
                  const ay = c.ay ?? (c as any).accident_year;
                  const lag = c.lag ?? (c as any).from_age;
                  const val = c.value ?? (c as any).factor;
                  const med = c.median ?? (c as any).expected_factor;
                  const ratio = c.ratio !== undefined ? c.ratio : (val != null && med != null && med !== 0 ? val / med : 1.0);
                  const severity = (c.severity as any) === 'Medium' ? 'Moderate' : (c.severity || 'Low');
                  const reason = c.reason || `Age-to-age factor ${val != null ? Number(val).toFixed(4) : "—"} deviates from average of ${med != null ? Number(med).toFixed(4) : "—"}.`;

                  return (
                    <div key={i} className="border border-border rounded-lg p-3 bg-bg-2 relative">
                      <span className={`absolute top-2.5 right-2.5 text-[8.5px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${
                        severity === 'Critical' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                        severity === 'High' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                        'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                      }`}>
                        {severity}
                      </span>
                      <div className="text-[10px] font-mono text-text-muted mb-1">
                        AY {ay} | Dev Lag {lag}
                      </div>
                      <div className="text-[11.5px] font-semibold text-text-main">
                        Value: <span className="font-mono text-accent">{val != null ? Number(val).toFixed(4) : '—'}</span>
                      </div>
                      <div className="text-[10px] text-text-sub mt-1 leading-normal">
                        {reason} (Ratio: {ratio != null && !isNaN(Number(ratio)) ? Number(ratio).toFixed(2) : '1.00'}x median)
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-[11px] text-text-muted font-mono h-32 flex items-center justify-center">
                No statistical anomalies identified in claim development.
              </p>
            )}
          </div>

          {/* Statistical Assumptions Summary */}
          <div className="bg-bg-1 border border-border rounded-xl p-5 shadow-sm">
            <h3 className="text-xs font-bold text-text-main uppercase tracking-wider mb-3 border-b border-border pb-2">
              Actuarial Stability Log
            </h3>
            <ul className="text-[11px] leading-relaxed text-text-sub space-y-2">
              {stab.cl_assumptions_reasonable ? (
                <li className="flex items-start gap-2">
                  <span className="text-accent-green font-bold">✓</span>
                  <span>Chain Ladder assumptions are statistically reasonable for this dataset.</span>
                </li>
              ) : (
                <li className="flex items-start gap-2">
                  <span className="text-accent-red font-bold">✗</span>
                  <span>Chain Ladder assumptions may be violated due to LDF instability.</span>
                </li>
              )}
              {cal.trend_detected && (
                <li className="flex items-start gap-2 text-accent-amber">
                  <span className="font-bold">⚠️</span>
                  <span>Detected calendar year inflation effect (Slope: {cal?.slope != null ? Number(cal.slope).toFixed(4) : "0.0000"}).</span>
                </li>
              )}
              {rep.significant_deviations && rep.significant_deviations.length > 0 && (
                <li className="flex items-start gap-2">
                  <span className="text-accent font-bold">•</span>
                  <span>Significant reporting pattern shifts in Accident Years: {rep.significant_deviations.join(', ')}.</span>
                </li>
              )}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
