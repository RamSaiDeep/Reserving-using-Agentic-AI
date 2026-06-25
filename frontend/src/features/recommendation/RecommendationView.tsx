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

export default function RecommendationView({ data, currency = 'USD' }: RecommendationViewProps) {
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
