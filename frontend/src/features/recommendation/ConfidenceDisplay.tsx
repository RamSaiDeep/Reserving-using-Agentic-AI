'use client';
import React from 'react';

interface ConfidenceDisplayProps {
  confidence: 'High' | 'Medium' | 'Low' | string;
}

export default function ConfidenceDisplay({ confidence }: ConfidenceDisplayProps) {
  const normalizedConf = confidence.toLowerCase();
  
  const config = {
    high: {
      color: 'text-accent-green bg-accent-green/10 border-accent-green/30',
      label: 'High Confidence',
      percentage: 90,
      desc: 'Highly consistent data development patterns and strong curve fits.'
    },
    medium: {
      color: 'text-accent-amber bg-accent-amber/10 border-accent-amber/30',
      label: 'Medium Confidence',
      percentage: 60,
      desc: 'Typical development volatility or moderate curve-fitting uncertainty.'
    },
    low: {
      color: 'text-accent-red bg-accent-red/10 border-accent-red/30',
      label: 'Low Confidence',
      percentage: 30,
      desc: 'Severe LDF instability, significant anomalies, or poor curve fit R².'
    }
  }[normalizedConf as 'high' | 'medium' | 'low'] || {
    color: 'text-text-sub bg-bg-2 border-border',
    label: confidence,
    percentage: 50,
    desc: 'Reasonable development factors with baseline parameters.'
  };

  return (
    <div className="bg-bg-1 border border-border rounded-xl p-5 shadow-sm space-y-4 text-left">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">
          Recommendation Quality
        </span>
        <span className={`text-[9.5px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${config.color}`}>
          {config.label}
        </span>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-text-sub font-semibold">Credibility Score</span>
          <span className="font-mono font-bold text-accent">{config.percentage}%</span>
        </div>
        <div className="h-2 bg-bg-2 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${
              normalizedConf === 'high' ? 'bg-accent-green' :
              normalizedConf === 'medium' ? 'bg-accent-amber' : 'bg-accent-red'
            }`}
            style={{ width: `${config.percentage}%` }}
          />
        </div>
      </div>

      <p className="text-[11.5px] text-text-sub leading-normal">
        {config.desc}
      </p>
    </div>
  );
}
