'use client';
import React, { useState, useEffect, useMemo } from 'react';
import { ExecuteResult, MethodResultItem } from '@/types';
import { fmt, fmtShort, CurrencyCode } from '@/lib/utils';
import MethodTable from './MethodTable';
import ReserveCharts from './ReserveCharts';

interface ComparisonDashboardProps {
  data: ExecuteResult;
  currency?: CurrencyCode;
  onBack: () => void;
  sessionId: string;
  getApiUrl: (endpoint: string) => string;
}

const PROCESS_EXPLANATIONS: Record<string, string> = {
  "CL":  "Chain Ladder projects ultimate claims by multiplying the latest paid/incurred diagonal by Cumulative Development Factors (CDFs) derived from historical age-to-age LDFs. IBNR = Ultimate − Paid/Incurred.",
  "MCL": "Mack Chain Ladder calculates identical ultimates to CL but additionally computes sigma-squared variance for each column, producing standard errors and confidence intervals (75th/95th percentile) around the IBNR estimate.",
  "BF":  "Bornhuetter-Ferguson splits the IBNR into (a) expected unreported claims = Expected Ultimate × (1 − 1/CDF), plus (b) actual paid/incurred to date. Expected Ultimate = Premium × A Priori ELR.",
  "CC":  "Cape Cod derives the ELR automatically from actual data: ELR = Σ(Reported Claims) / Σ(Used-Up Premium). Used-Up Premium = Earned Premium × % Reported (1/CDF). IBNR is then computed identically to BF.",
  "BK":  "Benktander iteratively refines the BF estimate: BF Ultimate is fed back as the new A Priori, and IBNR is recomputed. Each iteration shifts credibility from BF toward Chain Ladder proportional to % reported.",
  "CO":  "Case Outstanding method sets IBNR = total case reserves currently held by adjusters. It assumes zero future newly-reported claims. Reserve = Incurred − Paid = Case Reserves.",
  "CLK": "Clark Stochastic fits a continuous growth curve (Log-Logistic or Weibull) to the paid triangle using maximum likelihood. Stabilised CDFs from the curve are applied to project ultimates with a distribution of outcomes.",
  "ELR": "Expected Loss Ratio projects future losses as Premium × Expected Loss Ratio. It does not use development factors for missing years, acting as a stable baseline indicator.",
  "FS":  "Frequency-Severity Method projects claim counts and average claim severities separately using historical disposal patterns and severity trends to calculate reserves."
};

export default function ComparisonDashboard({ data, currency = 'USD', onBack, sessionId, getApiUrl }: ComparisonDashboardProps) {
  const [mounted, setMounted] = useState(false);
  const [selectedDetailCode, setSelectedDetailCode] = useState<string>('');
  const [modelReports, setModelReports] = useState<Record<string, string>>({});
  const [generatingReportFor, setGeneratingReportFor] = useState<string | null>(null);

  const generateDeepDiveReport = async (methodCode: string) => {
    setGeneratingReportFor(methodCode);
    try {
      const res = await fetch(getApiUrl('generate_model_report'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, method_code: methodCode })
      });
      const resData = await res.json();
      if (!resData.success) throw new Error(resData.error);
      
      setModelReports(prev => ({ ...prev, [methodCode]: resData.report }));
    } catch (e: any) {
      alert(`Report generation failed: ${e.message}`);
    } finally {
      setGeneratingReportFor(null);
    }
  };

  const renderMarkdown = (text: string) => {
    if (!text) return '';
    let html = text
      .replace(/### (.*?)(?:\n|$)/g, '<h4 class="text-xs font-bold text-text-main mt-4 mb-2">$1</h4>')
      .replace(/## (.*?)(?:\n|$)/g, '<h3 class="text-sm font-bold text-accent mt-5 mb-2">$1</h3>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n\n/g, '</p><p class="mt-2">')
      .replace(/\n- (.*?)(?:\n|$)/g, '<li class="ml-4 list-disc">$1</li>')
      .replace(/\n\d+\. (.*?)(?:\n|$)/g, '<li class="ml-4 list-decimal">$1</li>')
      .replace(/\n/g, '<br />');
    return `<p>${html}</p>`;
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  // Sync selected method detail viewer with AI recommendation on load
  useEffect(() => {
    if (data.ai_recommendation?.recommended_method) {
      setSelectedDetailCode(data.ai_recommendation.recommended_method);
    } else {
      const firstSuccess = data.methods?.find(m => m.status === 'success');
      if (firstSuccess) {
        setSelectedDetailCode(firstSuccess.result_id || firstSuccess.code || firstSuccess.method || '');
      }
    }
  }, [data]);

  const activeMethods = useMemo(() => {
    if (!data.methods) return [];
    return data.methods.filter(m => m.status === 'success' && (m.result_id || m.code) !== 'CO') as MethodResultItem[];
  }, [data.methods]);

  const reservingMethods = useMemo(() => {
    if (!data.methods) return [];
    return data.methods.filter(m => (m.result_id || m.code) !== 'CO');
  }, [data.methods]);

  const caseOutstandingDetail = useMemo(() => {
    if (!data.methods) return undefined;
    return data.methods.find(m => (m.result_id || m.code) === 'CO' && m.status === 'success');
  }, [data.methods]);

  const coDiagnostic = useMemo(() => {
    if (!caseOutstandingDetail || !caseOutstandingDetail.results) return null;
    
    const results = caseOutstandingDetail.results;
    if (results.length === 0) return null;
    
    const immatureResults = results.filter(r => r.cdfToUlt > 1.0);
    const resultsToUse = immatureResults.length > 0 ? immatureResults : results;
    const avgCaseCdf = resultsToUse.reduce((acc, r) => acc + (r.cdfToUlt || 1.0), 0) / resultsToUse.length;
    
    const assessment = avgCaseCdf < 1.10 ? "STRONG" : "WEAK";
    const recommendation = assessment === "STRONG"
      ? "Case reserves are highly stable (average Case CDF is close to 1.0). Incurred-based methods (CL Incurred, BF, CC) are recommended as they incorporate adjuster case estimates without risk of significant development distortions."
      : "Case reserves show significant potential for future development (average Case CDF is elevated). Paid-based methods (CL Paid, Clark) or Bornhuetter-Ferguson with Paid LDFs are recommended to bypass case reserve instability.";
      
    return {
      avgCaseCdf,
      assessment,
      recommendation,
      results
    };
  }, [caseOutstandingDetail]);

  const ultimateStats = useMemo(() => {
    if (activeMethods.length === 0) return { min: 0, max: 0, median: 0 };
    const ultimates = activeMethods.map(m => m.ultimate || 0).sort((a, b) => a - b);
    const mid = Math.floor(ultimates.length / 2);
    const median = ultimates.length % 2 !== 0 ? ultimates[mid] : (ultimates[mid - 1] + ultimates[mid]) / 2;
    return {
      min: ultimates[0],
      max: ultimates[ultimates.length - 1],
      median
    };
  }, [activeMethods]);

  const selectedMethodDetail = useMemo(() => {
    if (!data.methods) return undefined;
    return data.methods.find(m => (m.result_id || m.code) === selectedDetailCode);
  }, [data.methods, selectedDetailCode]);

  const trendData = useMemo(() => {
    if (!selectedMethodDetail || !selectedMethodDetail.results) return [];
    return selectedMethodDetail.results.map((r: any) => ({
      ay: r.ay,
      paid: parseFloat(r.paid) || 0,
      ibnr: parseFloat(r.ibnr) || 0,
      ultimate: parseFloat(r.ultimate) || 0,
      pctReported: (parseFloat(r.pctReported) || 0),
      settlementRate: parseFloat(r.ultimate) ? ((parseFloat(r.paid) || 0) / parseFloat(r.ultimate)) * 100 : 0
    }));
  }, [selectedMethodDetail]);

  const barChartData = useMemo(() => {
    return activeMethods.map(m => ({
      name: m.result_id || m.code || '',
      IBNR: m.ibnr || 0,
      Ultimate: m.ultimate || 0
    }));
  }, [activeMethods]);


  return (
    <div className="flex flex-col flex-1 animate-slide-in pb-10 space-y-6 text-left">
      
      {/* View Header */}
      <div className="flex justify-between items-center border-b border-border pb-3">
        <div>
          <h2 className="text-base font-bold text-text-main">Method Comparison & Reserving Indication</h2>
          <p className="text-xs text-text-sub mt-0.5 font-sans">Evaluate and contrast mathematical claim projection models side-by-side.</p>
        </div>
        <button
          onClick={onBack}
          className="px-3.5 py-1.5 bg-transparent border border-border-2 rounded text-xs text-text-sub hover:border-text-sub hover:text-text-main transition-colors cursor-pointer"
        >
          ← Adjust loss triangles
        </button>
      </div>

      {/* Case Outstanding Diagnostic Panel */}
      {coDiagnostic && (
        <div className="p-5 bg-blue-500/5 border border-blue-500/20 rounded-xl shadow-sm space-y-3 text-left">
          <div className="flex items-center justify-between border-b border-border pb-2.5">
            <h3 className="text-sm font-bold text-text-main flex items-center gap-2">
              🔎 Case Outstanding Diagnostic Analysis
            </h3>
            <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
              coDiagnostic.assessment === 'STRONG'
                ? 'bg-accent-green/10 border-accent-green/30 text-accent-green'
                : 'bg-accent-amber/10 border-accent-amber/30 text-accent-amber'
            }`}>
              {coDiagnostic.assessment} Case Reserves
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="md:col-span-2 space-y-1">
              <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">
                Reserving Adequacy Assessment
              </span>
              <p className="text-xs text-text-sub leading-relaxed">
                {coDiagnostic.recommendation}
              </p>
            </div>
            <div className="bg-bg-2 border border-border-2 rounded-lg p-3.5 flex flex-col items-center justify-center text-center font-mono">
              <span className="text-[9px] font-bold text-text-muted uppercase tracking-wider mb-1">
                Average Case CDF
              </span>
              <span className="text-lg font-bold text-accent">
                {coDiagnostic.avgCaseCdf.toFixed(3)}
              </span>
              <span className="text-[8px] text-text-sub mt-0.5">
                (Ratio of Paid vs. Incurred LDF)
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Method Comparison Grid */}
      <MethodTable
        data={data}
        currency={currency}
        selectedDetailCode={selectedDetailCode}
        onSelectMethod={setSelectedDetailCode}
        activeMethods={activeMethods}
        reservingMethods={reservingMethods}
      />

      {/* Range Meter and IBNR Visualizations */}
      {mounted && activeMethods.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <ReserveCharts
              barChartData={barChartData}
              trendData={trendData}
              selectedMethodName={selectedMethodDetail?.name || selectedDetailCode}
              currency={currency}
            />
          </div>

          {/* Indicated Range Gauge */}
          <div className="bg-bg-1 border border-border rounded-lg p-5 flex flex-col justify-between">
            <div>
              <div className="text-[11px] font-semibold text-text-sub mb-4 uppercase tracking-wider">
                Indicated Reserve Range
              </div>
              <div className="space-y-4 pt-2">
                <div className="flex justify-between text-xs border-b border-border/50 pb-2">
                  <span className="text-text-muted">Minimum Indication</span>
                  <span className="font-mono font-semibold">{fmt(ultimateStats.min, currency)}</span>
                </div>
                <div className="flex justify-between text-xs border-b border-border/50 pb-2">
                  <span className="text-text-muted">Median Indication</span>
                  <span className="font-mono font-semibold text-accent">{fmt(ultimateStats.median, currency)}</span>
                </div>
                <div className="flex justify-between text-xs border-b border-border/50 pb-2">
                  <span className="text-text-muted">Maximum Indication</span>
                  <span className="font-mono font-semibold">{fmt(ultimateStats.max, currency)}</span>
                </div>
              </div>
            </div>
            
            <div className="pt-5 border-t border-border mt-4">
              <div className="h-2 bg-bg-3 rounded-full relative w-full flex items-center">
                <div className="absolute left-[10%] w-2 h-2 rounded-full bg-text-muted" title="Min" />
                <div className="h-full bg-accent rounded-full absolute left-[10%] right-[10%]" />
                <div className="absolute left-[50%] -translate-x-1/2 w-3.5 h-3.5 rounded-full bg-accent border-2 border-white shadow" title="Median" />
                <div className="absolute right-[10%] w-2 h-2 rounded-full bg-text-muted" title="Max" />
              </div>
              <div className="flex justify-between text-[9px] text-text-muted mt-2">
                <span>Min</span>
                <span className="text-accent font-bold">Median</span>
                <span>Max</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detailed Method Analysis AY Grid */}
      <div className="border-t border-border pt-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-text-main uppercase tracking-wider">Detailed Method Analysis</h3>
            <p className="text-xs text-text-sub font-sans">Inspect the detailed accident-year grid and flowchart process for any method.</p>
          </div>
          
          <select
            value={selectedDetailCode}
            onChange={(e) => setSelectedDetailCode(e.target.value)}
            className="bg-bg-2 border border-border-2 rounded px-3 py-1.5 text-xs text-text-main font-semibold outline-none focus:border-accent h-9 cursor-pointer w-[240px]"
          >
            {activeMethods.map(m => (
              <option key={m.result_id || m.code} value={m.result_id || m.code}>{(m.result_id || m.code)} - {m.name}</option>
            ))}
          </select>
        </div>

        {selectedMethodDetail && (
          <div className="space-y-6">
            <div className="table-scroll border border-border rounded-lg bg-bg-1 overflow-x-auto">
              <table className="results-table w-full text-xs text-left min-w-[600px]">
                <thead>
                  <tr className="bg-bg-2 border-b border-border">
                    <th className="p-3">Accident Year</th>
                    <th className="p-3">Paid/Incurred Loss</th>
                    <th className="p-3">CDF to Ultimate</th>
                    <th className="p-3">% Reported</th>
                    <th className="p-3">Projected IBNR</th>
                    <th className="p-3 text-right">Projected Ultimate</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedMethodDetail.results?.map((r: any, i) => (
                    <tr key={i} className="border-b border-border last:border-none">
                      <td className="p-3 font-semibold">{r.ay}</td>
                      <td className="p-3 font-mono">{fmt(r.paid, currency)}</td>
                      <td className="p-3 font-mono">{r.cdfToUlt?.toFixed(4) || '—'}</td>
                      <td className="p-3 font-mono">{r.pctReported !== undefined ? `${r.pctReported.toFixed(1)}%` : '—'}</td>
                      <td className="p-3 font-mono text-accent-green">{fmt(r.ibnr, currency)}</td>
                      <td className="p-3 font-mono font-bold text-text-main text-right">{fmt(r.ultimate, currency)}</td>
                    </tr>
                  ))}
                  <tr className="totals-row font-bold bg-bg-2/30 border-t border-border">
                    <td className="p-3">Total</td>
                    <td className="p-3 font-mono">
                      {fmt(selectedMethodDetail.results?.reduce((acc, r) => acc + (r.paid || 0), 0) || 0, currency)}
                    </td>
                    <td className="p-3">—</td>
                    <td className="p-3">—</td>
                    <td className="p-3 font-mono text-accent-green">{fmt(selectedMethodDetail.ibnr || 0, currency)}</td>
                    <td className="p-3 font-mono text-accent text-right">{fmt(selectedMethodDetail.ultimate || 0, currency)}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Narrative Process Flowchart */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-stretch">
              <div className="bg-bg-1 border border-border p-5 rounded-lg flex flex-col justify-between">
                <div>
                  <div className="text-[10px] font-bold text-blue-400 tracking-wider mb-3 flex items-center gap-1.5 font-sans">
                    <span className="bg-blue-500 text-white w-4 h-4 rounded-full flex items-center justify-center text-[9px]">1</span>
                    REQUIRED INPUTS
                  </div>
                  <ul className="text-xs text-text-sub space-y-1.5 list-disc pl-4 font-sans">
                    <li>Loss development vectors</li>
                    <li>Tail factor: {(selectedMethodDetail.results?.[0]?.cdfToUlt || 1.0).toFixed(3)}</li>
                    {selectedMethodDetail.loss_ratio !== undefined && (
                      <li>Premium Volume data mapped</li>
                    )}
                  </ul>
                </div>
              </div>

              <div className="bg-bg-1 border border-border p-5 rounded-lg flex flex-col justify-between md:col-span-2">
                <div>
                  <div className="text-[10px] font-bold text-accent tracking-wider mb-3 flex items-center gap-1.5 font-sans">
                    <span className="bg-accent text-white w-4 h-4 rounded-full flex items-center justify-center text-[9px]">2</span>
                    MATHEMATICAL RESOURCING PROCESS
                  </div>
                  <p className="text-xs text-text-sub leading-relaxed font-sans">
                    {selectedMethodDetail 
                      ? (PROCESS_EXPLANATIONS[selectedMethodDetail.code || selectedMethodDetail.method || ''] || "Custom projection process.") 
                      : "Select a method to see process details."}
                  </p>
                </div>
              </div>
            </div>

            {/* Deep Dive Report Box */}
            <div className="bg-bg-1 border border-border p-5 rounded-lg flex flex-col justify-between mt-5">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="text-[10px] font-bold text-accent tracking-wider flex items-center gap-1.5 font-sans">
                    <span className="bg-accent text-white w-4 h-4 rounded-full flex items-center justify-center text-[9px]">3</span>
                    AI DEEP DIVE ANALYSIS
                  </div>
                  {!modelReports[selectedDetailCode] && (
                    <button 
                      onClick={() => generateDeepDiveReport(selectedDetailCode)}
                      disabled={generatingReportFor === selectedDetailCode}
                      className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:bg-bg-3 disabled:text-text-muted text-white text-[11px] font-bold rounded transition-colors flex items-center gap-2 cursor-pointer border-none"
                    >
                      {generatingReportFor === selectedDetailCode ? (
                        <><span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></span> Generating...</>
                      ) : 'Generate Analysis Report'}
                    </button>
                  )}
                </div>
                
                {modelReports[selectedDetailCode] ? (
                  <div 
                    className="text-[12.5px] text-text-sub leading-relaxed font-sans mt-2 pb-2"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(modelReports[selectedDetailCode]) }}
                  />
                ) : (
                  <div className="text-xs text-text-muted italic font-sans">
                    Generate a deep dive actuarial report tailored specifically to {selectedDetailCode}'s results.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
