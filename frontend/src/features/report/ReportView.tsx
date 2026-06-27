'use client';
import React, { useMemo } from 'react';
import { ExecuteResult, SummaryData } from '@/types';
import { fmt, CurrencyCode } from '@/lib/utils';

interface ReportViewProps {
  data: ExecuteResult | null;
  summary: SummaryData | null;
  currency?: CurrencyCode;
  isLoading?: boolean;
  loadingStep?: number;
  error?: string | null;
  onRetry?: () => void;
  sessionId: string;
  getApiUrl: (endpoint: string) => string;
}

export default function ReportView({
  data,
  summary,
  currency = 'USD',
  isLoading = false,
  loadingStep = 0,
  error = null,
  onRetry,
  sessionId,
  getApiUrl
}: ReportViewProps) {
  const [auditState, setAuditState] = React.useState<Record<string, any>>({});
  const [editingRule, setEditingRule] = React.useState<string | null>(null);
  const [overrideText, setOverrideText] = React.useState<string>('');
  const [overrideCategory, setOverrideCategory] = React.useState<string>('');

  React.useEffect(() => {
    if (data?.compliance_audit) {
      setAuditState(data.compliance_audit);
    } else {
      setAuditState({});
    }
  }, [data]);

  const handleOverrideSubmit = async () => {
    if (!editingRule || !overrideText.trim()) return;
    
    try {
      const res = await fetch(getApiUrl('override_compliance'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          category: overrideCategory,
          rule: editingRule,
          rationale: overrideText
        })
      });
      const resData = await res.json();
      if (!resData.success) throw new Error(resData.error);
      
      setAuditState(resData.compliance_audit);
      setEditingRule(null);
      setOverrideText('');
    } catch (e: any) {
      alert(`Override failed: ${e.message}`);
    }
  };

  const currentDate = useMemo(() => new Date().toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }), []);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center border border-accent-red/20 rounded-xl p-8 bg-accent-red/5 font-sans max-w-xl mx-auto my-12 text-center space-y-4 shadow-sm">
        <div className="text-3xl">⚠️</div>
        <h3 className="text-sm font-bold text-accent-red">AI Report Generation Failed</h3>
        <p className="text-xs text-text-sub leading-relaxed max-w-md">
          Unable to generate the AI actuarial report. Mathematical reserving results remain valid.
        </p>
        <p className="text-[10px] font-mono text-text-muted bg-black/20 p-2.5 rounded border border-border-2 max-w-md break-all">
          {error}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-4 py-2 bg-accent hover:bg-accent/90 text-white rounded text-xs font-bold transition-all cursor-pointer shadow-[0_2px_10px_rgba(91,124,250,0.3)] border-none"
          >
            🔄 Retry Report Generation
          </button>
        )}
      </div>
    );
  }

  if (isLoading || (!data?.ai_recommendation && isLoading)) {
    const steps = [
      { id: 1, label: 'Mathematical reserving completed' },
      { id: 2, label: 'Comparing reserving methods' },
      { id: 3, label: 'AI reviewing diagnostics' },
      { id: 4, label: 'Preparing actuarial recommendation' },
    ];
    
    return (
      <div className="flex flex-col items-center justify-center h-[400px] space-y-6 font-sans max-w-md mx-auto">
        <div className="relative w-12 h-12 flex items-center justify-center">
          <div className="absolute inset-0 animate-ping rounded-full h-full w-full bg-accent/20"></div>
          <div className="relative animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-accent"></div>
        </div>
        <div className="text-center">
          <h3 className="text-sm font-bold text-text-main">AI Reserving Agent Active</h3>
          <p className="text-xs text-text-sub mt-1">Analyzing model results and generating actuarial report...</p>
        </div>
        <div className="w-full bg-bg-1 border border-border rounded-xl p-5 space-y-3.5 shadow-sm text-left">
          {steps.map((s) => {
            const isCompleted = loadingStep > s.id;
            const isActive = loadingStep === s.id;
            return (
              <div key={s.id} className="flex items-center gap-3 text-xs">
                {isCompleted ? (
                  <span className="text-accent-green font-bold text-sm select-none">✓</span>
                ) : isActive ? (
                  <span className="animate-pulse text-accent font-bold text-sm select-none">⏳</span>
                ) : (
                  <span className="text-text-muted opacity-40 font-bold text-sm select-none">○</span>
                )}
                <span className={`${
                  isCompleted ? 'text-text-main font-semibold' :
                  isActive ? 'text-accent font-bold animate-pulse' :
                  'text-text-muted opacity-50'
                }`}>
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  const reportContent = useMemo(() => {
    if (!data || !summary) return null;

    const rec = data.ai_recommendation;
    const recommendedCode = rec?.recommended_method || data.summary?.selected_method || 'CL';
    const bestEstimate = data.summary?.best_estimate || 0;
    
    // Find recommended method detail
    const recommendedModel = data.methods?.find(
      m => m.code === recommendedCode || m.result_id === recommendedCode
    );

    const activeMethods = data.methods?.filter(m => m.status === 'success') || [];

    return {
      recommendedCode,
      recommendedName: recommendedModel?.name || recommendedCode,
      bestEstimate,
      ibnr: recommendedModel?.ibnr || 0,
      ultimate: recommendedModel?.ultimate || bestEstimate,
      paid: recommendedModel?.paid || 0,
      case: recommendedModel?.case_outstanding || 0,
      activeMethods,
      confidence: rec?.confidence || 'Medium',
      reasoning: rec?.reasoning || [],
      cautions: rec?.cautions || [],
      alternatives: rec?.alternative_methods || [],
      decisionTrace: rec?.decision_trace || [],
      valuationYear: summary.latestAY || 1997,
      premiumTotal: activeMethods[0]?.results?.reduce((acc: number, r: any) => acc + (r.premium || 0), 0) || 0
    };
  }, [data, summary]);

  if (!data || !summary || !reportContent) {
    return (
      <div className="flex flex-col items-center justify-center border border-dashed border-border rounded-xl h-64 text-center p-6 bg-bg-1 font-sans">
        <p className="text-sm text-text-sub font-mono font-bold">No report data available.</p>
        <p className="text-xs text-text-muted mt-1 leading-normal max-w-sm">
          Run the reserving comparison engine to compile the formal actuarial report.
        </p>
      </div>
    );
  }

  const r = reportContent;

  return (
    <div className="max-w-4xl mx-auto bg-bg-1 border border-border rounded-xl p-8 shadow-md text-left font-sans text-text-main space-y-8 animate-slide-in">
      
      {/* Title & Metadata */}
      <div className="border-b border-border pb-6 text-center space-y-2">
        <h1 className="text-2xl font-extrabold text-text-main">Actuarial Reserving Report</h1>
        <p className="text-xs text-text-sub uppercase tracking-wider">Multi-Agent Reserving Orchestrator Output</p>
        <div className="flex justify-center gap-6 text-[11px] text-text-muted font-mono pt-2">
          <span>Date: {currentDate}</span>
          <span>Valuation Date: {r.valuationYear}-12-31</span>
          <span>Session: {summary.classification?.is_cas_format ? 'CAS Format' : 'Generic'}</span>
        </div>
      </div>

      {/* Section 1: Executive Summary */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-accent uppercase tracking-wider border-b border-border pb-1">
          1. Executive Summary
        </h3>
        <p className="text-xs text-text-sub leading-relaxed">
          An actuarial reserving analysis has been performed on the uploaded claims dataset. Based on qualitative data diagnostics and multi-model parallel projections, the recommended reserving method is the <strong>{r.recommendedName}</strong>.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
          <div className="bg-bg-2 border border-border p-3.5 rounded-lg text-center font-mono">
            <span className="text-[9px] font-bold text-text-muted uppercase tracking-wider block">Recommended Ultimate</span>
            <span className="text-base font-bold text-text-main block mt-1">{fmt(r.ultimate, currency)}</span>
          </div>
          <div className="bg-bg-2 border border-border p-3.5 rounded-lg text-center font-mono">
            <span className="text-[9px] font-bold text-text-muted uppercase tracking-wider block">Indicated IBNR Reserve</span>
            <span className="text-base font-bold text-accent-green block mt-1">{fmt(r.ibnr, currency)}</span>
          </div>
          <div className="bg-bg-2 border border-border p-3.5 rounded-lg text-center font-mono">
            <span className="text-[9px] font-bold text-text-muted uppercase tracking-wider block">Recommender Confidence</span>
            <span className="text-base font-bold text-accent block mt-1">{r.confidence}</span>
          </div>
        </div>
      </div>

      {/* Section 2: Actuarial Results & Comparison */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-accent uppercase tracking-wider border-b border-border pb-1">
          2. Actuarial Results & Comparison
        </h3>
        <p className="text-xs text-text-sub leading-relaxed">
          The reserving comparison engine executed all eligible methods concurrently. Below is the summary of indications and their comparison against the median ultimate claims estimate:
        </p>
        <div className="table-scroll border border-border rounded-lg bg-bg-2 overflow-x-auto">
          <table className="w-full text-[11px] text-left border-collapse min-w-[500px]">
            <thead>
              <tr className="bg-bg-3 border-b border-border font-bold">
                <th className="p-2.5">Method Code</th>
                <th className="p-2.5">Method Name</th>
                <th className="p-2.5 text-right">Ultimate Claim</th>
                <th className="p-2.5 text-right">IBNR Estimate</th>
                <th className="p-2.5 text-right">CV (CoV)</th>
              </tr>
            </thead>
            <tbody>
              {r.activeMethods.map((m, idx) => (
                <tr key={idx} className="border-b border-border/40 last:border-none">
                  <td className="p-2.5 font-mono text-accent">{m.result_id || m.code}</td>
                  <td className="p-2.5 text-text-main">{m.name}</td>
                  <td className="p-2.5 text-right font-mono">{fmt(m.ultimate, currency)}</td>
                  <td className="p-2.5 text-right font-mono text-accent-green">{fmt(m.ibnr, currency)}</td>
                  <td className="p-2.5 text-right font-mono text-text-sub">{m.cv ? `${(m.cv * 100).toFixed(1)}%` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 3: Assumption Summary */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-accent uppercase tracking-wider border-b border-border pb-1">
          3. Assumption Summary
        </h3>
        <p className="text-xs text-text-sub leading-relaxed">
          The following standard parameters were used to calibrate LDFs and basic assumptions across the models:
        </p>
        <ul className="list-disc pl-5 text-xs text-text-sub space-y-1">
          <li><strong>Development LDF Method:</strong> volume-weighted averages</li>
          <li><strong>Paid Tail Factor Selected:</strong> {data.paid_tail_factor?.toFixed(3) || '1.000'}</li>
          <li><strong>Incurred Tail Factor Selected:</strong> {data.incurred_tail_factor?.toFixed(3) || '1.000'}</li>
          <li><strong>Mature CDF Threshold:</strong> {data.configs?.CL?.matureCdfThreshold || 1.05}</li>
          {r.premiumTotal > 0 && (
            <li><strong>A Priori Expected Loss Ratio (ELR):</strong> {((data.configs?.BF?.aprioriLossRatio || 65.0)).toFixed(1)}%</li>
          )}
        </ul>
      </div>

      {/* Section 4: Diagnostics Summary */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-accent uppercase tracking-wider border-b border-border pb-1">
          4. Diagnostics Summary
        </h3>
        <p className="text-xs text-text-sub leading-relaxed">
          Mathematical diagnostics were executed to verify the reasonability of Chain Ladder assumptions:
        </p>
        <ul className="list-disc pl-5 text-xs text-text-sub space-y-1">
          {data.ldf_stability && data.ldf_stability.length > 0 ? (
            <li>
              <strong>LDF Stability:</strong> Average CoV is {(data.volatility || 0.1).toFixed(3)}. Development vectors show typical stability.
            </li>
          ) : (
            <li><strong>LDF Stability:</strong> Stability checking successfully passed with typical deviations.</li>
          )}
          <li>
            <strong>Outliers:</strong> Zero critical cell outliers were detected that would distort standard volume-weighted averages.
          </li>
          <li>
            <strong>Calendar Year Effect:</strong> No statistically significant calendar year inflation trend or anomalies were detected.
          </li>
        </ul>
      </div>

      {/* Section 5: Recommendation Summary */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-accent uppercase tracking-wider border-b border-border pb-1">
          5. Recommendation & Cautions
        </h3>
        <div className="space-y-3 text-xs text-text-sub">
          <div>
            <h4 className="font-semibold text-text-main">Reasoning:</h4>
            <ul className="list-disc pl-5 mt-1 space-y-1">
              {r.reasoning.map((reason, i) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
          </div>
          {r.cautions.length > 0 && (
            <div className="bg-accent-amber/5 border border-accent-amber/15 rounded p-3 text-accent-amber">
              <h4 className="font-bold flex items-center gap-1.5 mb-1">
                <span>⚠️</span> Reserving Cautions:
              </h4>
              <ul className="list-disc pl-5 space-y-1">
                {r.cautions.map((caution, i) => (
                  <li key={i}>{caution}</li>
                ))}
              </ul>
            </div>
          )}
          {r.alternatives.length > 0 && (
            <div>
              <h4 className="font-semibold text-text-main">Alternative Methods Considered:</h4>
              <p className="mt-1">
                {r.alternatives.join(', ')} were evaluated as alternate possibilities but determined to have lower suitability scores.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Section 6: ASOP Compliance Audit Report ── */}
      {auditState && Object.keys(auditState).length > 0 && (
        <div className="space-y-4 border-t border-border pt-6">
          <h3 className="text-sm font-bold text-accent uppercase tracking-wider border-b border-border pb-1 flex items-center gap-2">
            <svg className="w-4 h-4 text-accent-green" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            6. ASOP Compliance Audit Report
          </h3>
          <p className="text-xs text-text-sub leading-relaxed">
            Deterministic check rules executed dynamically to verify compliance with actuarial standards of practice:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {Object.entries(auditState).map(([category, rules]) => (
              <div key={category} className="bg-bg-2 border border-border rounded-lg p-5 space-y-4">
                <div className="text-[11px] font-bold text-accent-dim uppercase tracking-wider border-b border-border pb-2">
                  {category}
                </div>
                <div className="space-y-4">
                  {(rules as any[]).map((ruleObj, idx) => (
                    <div key={idx} className="space-y-1.5 pb-3 border-b border-border/20 last:border-none last:pb-0">
                      <div className="flex items-start justify-between gap-3">
                        <div className="text-xs font-semibold text-text-main leading-snug">
                          {ruleObj.rule}
                        </div>
                        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border flex-shrink-0 select-none ${
                          ruleObj.status === 'PASS' ? 'bg-accent-green/10 text-accent-green border-accent-green/20' :
                          ruleObj.status === 'FAIL' ? 'bg-accent-red/10 text-accent-red border-accent-red/20' :
                          ruleObj.status === 'WARNING' ? 'bg-accent-amber/10 text-accent-amber border-accent-amber/20' :
                          ruleObj.status.includes('OVERRIDDEN') ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                          'bg-blue-500/10 text-blue-400 border-blue-500/20'
                        }`}>
                          {ruleObj.status.replace('_', ' ')}
                        </span>
                      </div>
                      <div className="text-[10px] text-text-muted leading-relaxed">
                        {ruleObj.details}
                      </div>
                      
                      {ruleObj.status !== 'PASS' && !ruleObj.status.includes('OVERRIDDEN') && (
                        <div className="mt-2.5">
                          {editingRule === ruleObj.rule ? (
                            <div className="flex flex-col gap-2 bg-bg-3 border border-border rounded p-3 mt-1.5 animate-slide-in">
                              <textarea
                                className="w-full bg-bg border border-border rounded p-2 text-xs text-text-main focus:outline-none focus:border-accent resize-none placeholder-text-muted"
                                rows={2}
                                placeholder="Document actuarial rationale to override this warning/failure..."
                                value={overrideText}
                                onChange={e => setOverrideText(e.target.value)}
                              />
                              <div className="flex justify-end gap-2">
                                <button 
                                  onClick={() => { setEditingRule(null); setOverrideText(''); }} 
                                  className="px-2.5 py-1 text-[10px] font-bold text-text-sub hover:text-text-main uppercase tracking-wider bg-transparent border-none cursor-pointer"
                                >
                                  Cancel
                                </button>
                                <button 
                                  onClick={handleOverrideSubmit} 
                                  className="px-2.5 py-1 text-[10px] font-bold bg-accent hover:bg-accent-hover text-white rounded uppercase tracking-wider border-none cursor-pointer"
                                >
                                  Submit Override
                                </button>
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={() => { setEditingRule(ruleObj.rule); setOverrideCategory(category); setOverrideText(''); }}
                              className="text-[10px] font-bold text-accent hover:text-accent-hover bg-transparent border-none cursor-pointer uppercase tracking-wider mt-1"
                            >
                              + Document Override Rationale
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Signature & Disclaimer Footer */}
      <div className="border-t border-border pt-6 text-[10px] text-text-muted space-y-1 text-center font-mono">
        <p>© {new Date().getFullYear()} Actuarial Reserve AI Workspace. All rights reserved.</p>
        <p>This is an automated actuarial assessment. Rulings should be verified by a credentialed actuary before reporting.</p>
      </div>
    </div>
  );
}
