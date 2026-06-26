'use client';
import React, { useMemo } from 'react';
import { ExecuteResult } from '@/types';
import { CurrencyCode } from '@/lib/utils';
import ConfidenceDisplay from './ConfidenceDisplay';
import RecommendationSummary from './RecommendationSummary';
import DecisionTrace from './DecisionTrace';
import AlternativeMethods from './AlternativeMethods';

interface RecommendationViewProps {
  data: ExecuteResult | null;
  currency?: CurrencyCode;
  isLoading?: boolean;
  loadingStep?: number;
  error?: string | null;
  onRetry?: () => void;
}

const METHOD_NAMES: Record<string, string> = {
  "CL": "Chain Ladder (Paid/Incurred Development)",
  "MCL": "Mack Chain Ladder (Stochastic Volatility)",
  "BF": "Bornhuetter-Ferguson",
  "BK": "Benktander (Iterative Credibility)",
  "CC": "Cape Cod (Stanard-Buhlmann)",
  "CLK": "Clark Stochastic Growth Curve",
  "ELR": "Expected Loss Ratio",
  "CO": "Case Outstanding Development",
  "FS": "Frequency-Severity Method"
};

export default function RecommendationView({
  data,
  currency = 'USD',
  isLoading = false,
  loadingStep = 0,
  error = null,
  onRetry
}: RecommendationViewProps) {
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center border border-accent-red/20 rounded-xl p-8 bg-accent-red/5 font-sans max-w-xl mx-auto my-12 text-center space-y-4 shadow-sm">
        <div className="text-3xl">⚠️</div>
        <h3 className="text-sm font-bold text-accent-red">AI Recommendation Generation Failed</h3>
        <p className="text-xs text-text-sub leading-relaxed max-w-md">
          Unable to generate the AI recommendation. Mathematical reserving results remain valid.
        </p>
        <p className="text-[10px] font-mono text-text-muted bg-black/20 p-2.5 rounded border border-border-2 max-w-md break-all">
          {error}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-4 py-2 bg-accent hover:bg-accent/90 text-white rounded text-xs font-bold transition-all cursor-pointer shadow-[0_2px_10px_rgba(91,124,250,0.3)] border-none"
          >
            🔄 Retry Recommendation
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

  if (!data || !data.ai_recommendation) {
    return (
      <div className="flex flex-col items-center justify-center border border-dashed border-border rounded-xl h-64 text-center p-6 bg-bg-1 font-sans">
        <p className="text-sm text-text-sub font-mono font-bold">No recommendation results available.</p>
        <p className="text-xs text-text-muted mt-1 leading-normal max-w-sm">
          Run the reserving comparison engine first to let the reserving recommendation agent evaluate model results.
        </p>
      </div>
    );
  }

  const rec = data.ai_recommendation;
  const recommendedCode = rec.recommended_method;
  
  // Find recommended method details from the methods list
  const recommendedModel = useMemo(() => {
    if (!data.methods) return null;
    const baseCode = recommendedCode.split('_')[0];
    return data.methods.find(m => m.code === recommendedCode || m.code === baseCode || m.result_id === recommendedCode);
  }, [data.methods, recommendedCode]);

  const recommendedName = useMemo(() => {
    if (recommendedModel) return recommendedModel.name || METHOD_NAMES[recommendedModel.code || ''] || recommendedCode;
    const baseCode = recommendedCode.split('_')[0];
    return METHOD_NAMES[baseCode] || recommendedCode;
  }, [recommendedModel, recommendedCode]);

  // Extract totals or use fallbacks
  const ibnrVal = recommendedModel?.ibnr || data.summary?.best_estimate || 0;
  const ultimateVal = recommendedModel?.ultimate || 0;
  const paidVal = recommendedModel?.paid || 0;
  const caseVal = recommendedModel?.case_outstanding || 0;

  return (
    <div className="space-y-6 text-left font-sans animate-slide-in">
      <div>
        <h2 className="text-xl font-bold text-text-main">AI Reserve Recommendation Insights</h2>
        <p className="text-xs text-text-sub mt-0.5">Qualitative explanations and analytical assumptions of the recommended model.</p>
      </div>

      {/* Main recommendation panels layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Columns: Summary & Decision Trace */}
        <div className="lg:col-span-2 space-y-6">
          <RecommendationSummary
            methodName={recommendedName}
            methodCode={recommendedCode}
            ibnr={ibnrVal}
            ultimate={ultimateVal}
            paid={paidVal}
            caseOutstanding={caseVal}
            currency={currency}
          />

          {/* Reasoning Checklist */}
          {rec.reasoning && rec.reasoning.length > 0 && (
            <div className="bg-bg-1 border border-border rounded-xl p-5 shadow-sm space-y-3">
              <h3 className="text-xs font-bold text-text-main uppercase tracking-wider">
                Recommendation Rationale
              </h3>
              <ul className="space-y-2 text-xs leading-relaxed text-text-sub">
                {rec.reasoning.map((reason, i) => (
                  <li key={i} className="flex gap-2.5 items-start">
                    <span className="text-accent font-bold select-none">•</span>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Cautions and Warnings */}
          {rec.cautions && rec.cautions.length > 0 && (
            <div className="bg-bg-1 border border-border-2 rounded-xl p-5 shadow-sm space-y-3 bg-accent-amber/5 border-accent-amber/15">
              <h3 className="text-xs font-bold text-accent-amber uppercase tracking-wider flex items-center gap-1.5">
                <span>⚠️</span> Reserving Cautions & Warnings
              </h3>
              <ul className="space-y-2 text-xs leading-relaxed text-accent-amber/90">
                {rec.cautions.map((caution, i) => (
                  <li key={i} className="flex gap-2 items-start">
                    <span className="font-bold select-none">•</span>
                    <span>{caution}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right Column: Confidence Gauge & Alternatives */}
        <div className="space-y-6">
          <ConfidenceDisplay confidence={rec.confidence} />

          <AlternativeMethods alternatives={rec.alternative_methods || []} />

          <DecisionTrace trace={rec.decision_trace || []} />
        </div>
      </div>
    </div>
  );
}
