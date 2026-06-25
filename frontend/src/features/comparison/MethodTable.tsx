'use client';
import React from 'react';
import { ExecuteResult, MethodResultItem } from '@/types';
import { fmt, CurrencyCode } from '@/lib/utils';

interface MethodTableProps {
  data: ExecuteResult;
  currency: CurrencyCode;
  selectedDetailCode: string;
  onSelectMethod: (code: string) => void;
  activeMethods: MethodResultItem[];
  reservingMethods: MethodResultItem[];
}

export default function MethodTable({
  data,
  currency,
  selectedDetailCode,
  onSelectMethod,
  activeMethods,
  reservingMethods,
}: MethodTableProps) {
  // Helper to format diff from median percentage
  const getDiffFromMedianStr = (m: MethodResultItem) => {
    if (m.diff_from_median === undefined || m.diff_from_median === null) return 'N/A';
    const val = m.diff_from_median;
    const sign = val > 0 ? '+' : '';
    return `${sign}${(val * 100).toFixed(1)}%`;
  };

  return (
    <div className="space-y-3 text-left">
      <h3 className="text-xs font-bold text-text-main uppercase tracking-wider">Method Comparison Summary</h3>
      <div className="table-scroll border border-border rounded-lg bg-bg-1 overflow-x-auto">
        <table className="results-table w-full text-xs text-left min-w-[700px]">
          <thead className="bg-bg-2 border-b border-border">
            <tr>
              <th className="p-3 font-semibold text-text-sub">Method Code</th>
              <th className="p-3 font-semibold text-text-sub">Method Name</th>
              <th className="p-3 font-semibold text-text-sub">Source</th>
              <th className="p-3 font-semibold text-text-sub">Status</th>
              <th className="p-3 font-semibold text-text-sub text-right">Ultimate Claim</th>
              <th className="p-3 font-semibold text-text-sub text-right">IBNR Estimate</th>
              <th className="p-3 font-semibold text-text-sub text-right">Diff from Median</th>
              <th className="p-3 font-semibold text-text-sub text-right">CV / CoV</th>
            </tr>
          </thead>
          <tbody>
            {reservingMethods.map((m) => {
              const isSelected = m.result_id === selectedDetailCode;
              const isSuccess = m.status === 'success';

              return (
                <tr
                  key={m.result_id}
                  onClick={() => onSelectMethod(m.result_id || m.code || '')}
                  className={`border-b border-border last:border-none cursor-pointer transition-colors hover:bg-bg-2 ${
                    isSelected ? 'bg-accent-dim/30 font-semibold border-l-2 border-l-accent' : ''
                  }`}
                >
                  <td className="p-3 font-mono font-bold text-accent">{m.result_id || m.code}</td>
                  <td className="p-3 text-text-main">{m.name}</td>
                  <td className="p-3 text-text-sub capitalize">{m.source}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      m.status === 'success' ? 'bg-accent-green/10 text-accent-green' :
                      m.status === 'disabled' ? 'bg-text-muted/10 text-text-muted' :
                      'bg-accent-red/10 text-accent-red'
                    }`}>
                      {m.status}
                    </span>
                  </td>
                  <td className="p-3 text-right font-mono text-text-main">
                    {isSuccess ? fmt(m.ultimate, currency) : '—'}
                  </td>
                  <td className="p-3 text-right font-mono text-accent-green">
                    {isSuccess ? fmt(m.ibnr, currency) : '—'}
                  </td>
                  <td className={`p-3 text-right font-mono ${
                    !isSuccess ? 'text-text-muted' :
                    (m.diff_from_median || 0) > 0 ? 'text-accent-red' : 'text-accent-green'
                  }`}>
                    {isSuccess ? getDiffFromMedianStr(m) : '—'}
                  </td>
                  <td className="p-3 text-right font-mono text-text-sub">
                    {isSuccess && m.cv ? `${(m.cv * 100).toFixed(1)}%` : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
