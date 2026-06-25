'use client';
import React from 'react';

interface AlternativeMethodsProps {
  alternatives: string[];
}

const METHOD_LABELS: Record<string, string> = {
  "CL": "Chain Ladder (Development Method)",
  "MCL": "Mack Chain Ladder (Stochastic Volatility)",
  "BF": "Bornhuetter-Ferguson (A Priori ELR Blend)",
  "BK": "Benktander (Iterative Credibility)",
  "CC": "Cape Cod (Stanard-Buhlmann)",
  "CLK": "Clark Stochastic (Growth Curve Fitting)",
  "ELR": "Expected Loss Ratio (Baseline Prem)",
  "CO": "Case Outstanding (Adjuster Reserves)",
  "FS": "Frequency-Severity Method"
};

export default function AlternativeMethods({ alternatives }: AlternativeMethodsProps) {
  // Strip source codes from alternative method codes if any (e.g., 'BF_PAID' -> 'BF')
  const cleanAlternatives = alternatives.map(code => {
    const baseCode = code.split('_')[0];
    return {
      code,
      label: METHOD_LABELS[baseCode] || code
    };
  });

  return (
    <div className="bg-bg-1 border border-border rounded-xl p-5 shadow-sm space-y-4 text-left">
      <h3 className="text-xs font-bold text-text-main uppercase tracking-wider border-b border-border pb-2">
        Alternative Reserving Methods Considered
      </h3>
      {cleanAlternatives.length > 0 ? (
        <div className="space-y-3">
          {cleanAlternatives.map((alt, idx) => (
            <div key={idx} className="flex items-center gap-3 p-3 bg-bg-2 border border-border rounded-lg">
              <span className="font-mono text-xs font-bold text-accent w-12 flex-shrink-0">
                {alt.code}
              </span>
              <span className="text-xs text-text-sub font-semibold">
                {alt.label}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-muted font-mono leading-normal py-4 text-center">
          No alternative models suggested by the recommender agent.
        </p>
      )}
    </div>
  );
}
