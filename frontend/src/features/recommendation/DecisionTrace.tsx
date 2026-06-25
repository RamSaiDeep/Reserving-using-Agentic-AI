'use client';
import React from 'react';

interface DecisionTraceProps {
  trace: string[];
}

export default function DecisionTrace({ trace }: DecisionTraceProps) {
  return (
    <div className="bg-bg-1 border border-border rounded-xl p-5 shadow-sm space-y-4 text-left">
      <h3 className="text-xs font-bold text-text-main uppercase tracking-wider border-b border-border pb-2">
        AI Orchestration Decision Trace
      </h3>
      {trace && trace.length > 0 ? (
        <div className="space-y-3 pl-2">
          {trace.map((step, idx) => (
            <div key={idx} className="flex gap-3 items-start text-xs leading-relaxed text-text-sub">
              <span className="w-5 h-5 rounded-full bg-accent/10 border border-accent/20 text-accent flex items-center justify-center flex-shrink-0 text-[10px] font-mono font-bold">
                {idx + 1}
              </span>
              <div className="pt-0.5 font-sans">
                {step}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-muted font-mono leading-normal py-4 text-center">
          No automated decision trace available for this recommendation.
        </p>
      )}
    </div>
  );
}
