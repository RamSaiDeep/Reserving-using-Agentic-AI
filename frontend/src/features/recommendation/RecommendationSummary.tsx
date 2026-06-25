'use client';
import React from 'react';
import { fmt, CurrencyCode } from '@/lib/utils';

interface RecommendationSummaryProps {
  methodName: string;
  methodCode: string;
  ibnr: number;
  ultimate: number;
  paid: number;
  caseOutstanding: number;
  currency: CurrencyCode;
}

export default function RecommendationSummary({
  methodName,
  methodCode,
  ibnr,
  ultimate,
  paid,
  caseOutstanding,
  currency,
}: RecommendationSummaryProps) {
  return (
    <div className="bg-bg-1 border border-border rounded-xl p-5 shadow-sm space-y-5 text-left">
      <div className="border-b border-border pb-3">
        <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider block mb-1">
          Actuarial Model Selection
        </span>
        <h3 className="text-lg font-bold text-text-main flex items-center gap-2">
          ✨ {methodName || methodCode}
        </h3>
        <p className="text-[11.5px] text-text-sub mt-0.5 leading-relaxed">
          Based on diagnostics, this method provides the most credible, stable reserving indication for this dataset.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* IBNR Estimate */}
        <div className="p-3 bg-bg-2 rounded-lg border border-border flex flex-col justify-between font-mono">
          <span className="text-[9px] font-bold text-text-muted uppercase tracking-wider">
            Projected IBNR
          </span>
          <span className="text-base font-bold text-accent-green mt-1">
            {fmt(ibnr, currency)}
          </span>
        </div>

        {/* Ultimate Claims */}
        <div className="p-3 bg-bg-2 rounded-lg border border-border flex flex-col justify-between font-mono">
          <span className="text-[9px] font-bold text-text-muted uppercase tracking-wider">
            Total Ultimate
          </span>
          <span className="text-base font-bold text-text-main mt-1">
            {fmt(ultimate, currency)}
          </span>
        </div>

        {/* Paid to Date */}
        <div className="p-3 bg-bg-2 rounded-lg border border-border flex flex-col justify-between font-mono">
          <span className="text-[9px] font-bold text-text-muted uppercase tracking-wider">
            Paid to Date
          </span>
          <span className="text-base font-bold text-text-sub mt-1">
            {fmt(paid, currency)}
          </span>
        </div>

        {/* Case Reserves */}
        <div className="p-3 bg-bg-2 rounded-lg border border-border flex flex-col justify-between font-mono">
          <span className="text-[9px] font-bold text-text-muted uppercase tracking-wider">
            Case Outstanding
          </span>
          <span className="text-base font-bold text-text-sub mt-1">
            {fmt(caseOutstanding, currency)}
          </span>
        </div>
      </div>
    </div>
  );
}
