'use client';
import React from 'react';
import { ExecutionConfig, TriangleData, MethodConfig } from '../types';

interface ConfigureAssumptionsProps {
  configs: ExecutionConfig;
  onChangeConfigs: (newConfigs: ExecutionConfig) => void;
  triangle: TriangleData;
  dataSource: 'paid' | 'incurred';
  onChangeDataSource: (source: 'paid' | 'incurred') => void;
  suggestedElrPaid: number | null;
  suggestedElrIncurred: number | null;
  paidLdfBase: string;
  incurredLdfBase: string;
  paidTailFactor: number;
  incurredTailFactor: number;
  onBack: () => void;
  onRunComparison: () => void;
}

export const AVAILABLE_METHODS = [
  { code: 'CL', label: 'Chain Ladder', desc: 'Pure development projection.' },
  { code: 'MCL', label: 'Mack Chain Ladder', desc: 'Standard errors & parameter uncertainty.' },
  { code: 'BF', label: 'Bornhuetter-Ferguson', desc: 'Credibility method utilizing an a priori ELR.', needsPremium: true },
  { code: 'BK', label: 'Benktander', desc: 'Iterative credibility method blending CL and BF.', needsPremium: true },
  { code: 'CC', label: 'Cape Cod', desc: 'Exposure-adjusted credibility method.', needsPremium: true },
  { code: 'ELR', label: 'Expected Loss Ratio', desc: 'Expected Claims Method utilizing an a priori ELR.', needsPremium: true },
  { code: 'CLK', label: 'Clark Stochastic', desc: 'Continuous growth curve MLE projection.' }
];

export const DIAGNOSTIC_METHODS = [
  { code: 'CO', label: 'Case Outstanding Development', desc: 'Uses reported Case CDF method to evaluate reserve strength.' }
];

export default function ConfigureAssumptions({
  configs,
  onChangeConfigs,
  triangle,
  dataSource,
  onChangeDataSource,
  suggestedElrPaid,
  suggestedElrIncurred,
  paidLdfBase,
  incurredLdfBase,
  paidTailFactor,
  incurredTailFactor,
  onBack,
  onRunComparison,
}: ConfigureAssumptionsProps) {

  const handleToggleMethod = (code: string) => {
    const current = configs[code] || { enabled: true };
    onChangeConfigs({
      ...configs,
      [code]: { ...current, enabled: !current.enabled },
    });
  };

  const handleParamChange = (code: string, key: string, value: any) => {
    const current = configs[code] || { enabled: true };
    onChangeConfigs({
      ...configs,
      [code]: { ...current, [key]: value },
    });
  };

  const hasPremium = triangle.hasPremium;

  return (
    <div className="flex flex-col flex-1 max-w-5xl mx-auto animate-slide-in pb-12 font-sans text-text-main text-left">
      {/* Top Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-extrabold tracking-tight">Configure Reserving Assumptions</h2>
          <p className="text-xs text-text-sub mt-1">Specify model-level data sources and parameters before running the comparison engine.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="px-4 py-2 border border-border bg-bg-1 rounded text-xs font-semibold hover:bg-bg-2 cursor-pointer transition-all"
          >
            ← Back to Triangle
          </button>
          <button
            onClick={onRunComparison}
            className="px-5 py-2 bg-accent hover:bg-accent-hover text-white text-xs font-bold rounded shadow-[0_4px_16px_rgba(91,124,250,0.35)] cursor-pointer transition-all"
          >
            Run Comparison Dashboard →
          </button>
        </div>
      </div>

      {/* Global Data Source Selection Toggle */}
      <div className="bg-bg-1 border border-border rounded-xl p-5 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
        <div>
          <h3 className="text-sm font-bold text-text-main">Global Data Source Selection</h3>
          <p className="text-xs text-text-sub mt-0.5">Select the loss triangle data source to run all reserving methods on.</p>
        </div>
        <div className="flex gap-2 bg-bg-2 p-1 rounded-lg border border-border-2">
          <button
            type="button"
            onClick={() => onChangeDataSource('incurred')}
            className={`px-4 py-2 text-xs font-bold rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              dataSource === 'incurred' 
                ? 'bg-accent text-white shadow-[0_2px_8px_rgba(91,124,250,0.35)]' 
                : 'text-text-sub hover:text-text-main'
            }`}
          >
            Incurred (Recommended)
          </button>
          <button
            type="button"
            onClick={() => onChangeDataSource('paid')}
            className={`px-4 py-2 text-xs font-bold rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
              dataSource === 'paid' 
                ? 'bg-accent text-white shadow-[0_2px_8px_rgba(91,124,250,0.35)]' 
                : 'text-text-sub hover:text-text-main'
            }`}
          >
            Paid
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Method config panels */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          
          {/* Group 1: Reserving Models */}
          <div className="flex flex-col gap-4">
            <h3 className="text-xs font-bold text-text-sub uppercase tracking-wider border-b border-border pb-1.5 mb-2">
              Primary Reserving Methods (Runs on {dataSource.toUpperCase()})
            </h3>
            {AVAILABLE_METHODS.map((method) => {
              const config = configs[method.code] || { enabled: false };
              const isDisabledByPremium = method.needsPremium && !hasPremium;

              return (
                <div
                  key={method.code}
                  className={`bg-bg-1 border rounded-xl p-5 transition-all ${
                    isDisabledByPremium
                      ? 'border-border-2 opacity-60'
                      : config.enabled
                      ? 'border-accent shadow-[0_2px_8px_rgba(91,124,250,0.05)]'
                      : 'border-border'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={config.enabled && !isDisabledByPremium}
                        disabled={isDisabledByPremium}
                        onChange={() => handleToggleMethod(method.code)}
                        className="w-4 h-4 text-accent border-border-2 rounded focus:ring-accent accent-accent cursor-pointer disabled:cursor-not-allowed"
                      />
                      <div>
                        <h3 className="text-sm font-bold flex items-center gap-2">
                          {method.label}
                          {isDisabledByPremium && (
                            <span className="text-[10px] font-bold text-accent-red bg-accent-red/10 px-2 py-0.5 rounded uppercase tracking-wide">
                              Disabled (No Premium)
                            </span>
                          )}
                        </h3>
                        <p className="text-xs text-text-sub mt-0.5">{method.desc}</p>
                      </div>
                    </div>
                  </div>

                  {config.enabled && !isDisabledByPremium && (
                    <div className="mt-4 pt-4 border-t border-border flex flex-col gap-4 animate-slide-in">
                      {/* Bornhuetter-Ferguson, Benktander, & Expected Loss Ratio settings */}
                      {(method.code === 'BF' || method.code === 'BK' || method.code === 'ELR') && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="flex flex-col gap-1">
                            <label className="text-xs font-bold text-text-sub">A Priori Expected Loss Ratio (%)</label>
                            <div className="flex flex-wrap items-center gap-2 mt-1">
                              <input
                                type="number"
                                value={config.aprioriLossRatio !== undefined && config.aprioriLossRatio !== null ? config.aprioriLossRatio : ''}
                                placeholder="e.g. 65"
                                onChange={(e) => handleParamChange(method.code, 'aprioriLossRatio', e.target.value === '' ? null : parseFloat(e.target.value))}
                                className="bg-bg-2 border border-border rounded px-3 py-1.5 text-xs outline-none focus:border-accent w-32 font-mono"
                              />
                              {suggestedElrPaid !== null && (
                                <span className="text-[10px] font-semibold text-accent bg-accent/10 px-2 py-1 rounded">
                                  Paid Suggestion: {suggestedElrPaid}%
                                </span>
                              )}
                              {suggestedElrIncurred !== null && (
                                <span className="text-[10px] font-semibold text-accent bg-accent/10 px-2 py-1 rounded">
                                  Incurred Suggestion: {suggestedElrIncurred}%
                                </span>
                              )}
                            </div>
                          </div>

                          {method.code === 'BK' && (
                            <div className="flex flex-col gap-1">
                              <label className="text-xs font-bold text-text-sub">Iterations (c)</label>
                              <input
                                type="number"
                                min="1"
                                max="10"
                                value={config.iterations !== undefined ? config.iterations : 2}
                                onChange={(e) => handleParamChange(method.code, 'iterations', parseInt(e.target.value) || 2)}
                                className="bg-bg-2 border border-border rounded px-3 py-1.5 text-xs outline-none focus:border-accent w-20 mt-1 font-mono"
                              />
                            </div>
                          )}
                        </div>
                      )}

                      {/* Cape Cod settings */}
                      {method.code === 'CC' && (
                        <div className="flex flex-col gap-1">
                          <label className="text-xs font-bold text-text-sub">Decay Factor</label>
                          <input
                            type="number"
                            step="0.05"
                            min="0.1"
                            max="1.0"
                            value={config.decay !== undefined ? config.decay : 1.0}
                            onChange={(e) => handleParamChange(method.code, 'decay', parseFloat(e.target.value) || 1.0)}
                            className="bg-bg-2 border border-border rounded px-3 py-1.5 text-xs outline-none focus:border-accent w-24 mt-1 font-mono"
                          />
                        </div>
                      )}

                      {/* Clark Stochastic settings */}
                      {method.code === 'CLK' && (
                        <div className="flex flex-col gap-1">
                          <label className="text-xs font-bold text-text-sub">Growth Curve shape</label>
                          <div className="flex gap-4 mt-1.5">
                            <label className="flex items-center gap-2 text-xs cursor-pointer">
                              <input
                                type="radio"
                                name="clark_curve"
                                checked={config.curveType === 'weibull' || !config.curveType}
                                onChange={() => handleParamChange(method.code, 'curveType', 'weibull')}
                                className="text-accent focus:ring-accent accent-accent"
                              />
                              <div>
                                <span className="font-bold">Weibull</span>
                                <span className="text-[10px] text-text-sub block">Smoother tail projection</span>
                              </div>
                            </label>
                            <label className="flex items-center gap-2 text-xs cursor-pointer">
                              <input
                                type="radio"
                                name="clark_curve"
                                checked={config.curveType === 'loglogistic'}
                                onChange={() => handleParamChange(method.code, 'curveType', 'loglogistic')}
                                className="text-accent focus:ring-accent accent-accent"
                              />
                              <div>
                                <span className="font-bold">Log-Logistic</span>
                                <span className="text-[10px] text-text-sub block">Heavier tail projection</span>
                              </div>
                            </label>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Group 2: Diagnostic Models */}
          <div className="flex flex-col gap-4">
            <h3 className="text-xs font-bold text-text-sub uppercase tracking-wider border-b border-border pb-1.5 mb-2">
              Diagnostic & Validation Analysis (Runs on BOTH Triangles)
            </h3>
            {DIAGNOSTIC_METHODS.map((method) => {
              const config = configs[method.code] || { enabled: false };

              return (
                <div
                  key={method.code}
                  className={`bg-bg-1 border rounded-xl p-5 transition-all ${
                    config.enabled
                      ? 'border-accent shadow-[0_2px_8px_rgba(91,124,250,0.05)]'
                      : 'border-border'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={config.enabled}
                        onChange={() => handleToggleMethod(method.code)}
                        className="w-4 h-4 text-accent border-border-2 rounded focus:ring-accent accent-accent cursor-pointer"
                      />
                      <div>
                        <h3 className="text-sm font-bold flex items-center gap-2 text-text-main">
                          {method.label}
                          <span className="text-[9.5px] font-bold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded uppercase tracking-wide">
                            Diagnostic
                          </span>
                        </h3>
                        <p className="text-xs text-text-sub mt-0.5">{method.desc}</p>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

        </div>

        {/* Right column: Selected LDF summary audit box */}
        <div className="flex flex-col gap-5 text-left">
          <div className="bg-bg-1 border border-border rounded-xl p-5 sticky top-6 shadow-sm">
            <h3 className="text-sm font-bold mb-4 flex items-center gap-2 border-b border-border pb-2.5">
              📋 Input Selection Audit
            </h3>

            <div className="flex flex-col gap-4">
              {/* Paid LDF Selection */}
              <div>
                <span className="text-[11px] font-bold text-text-sub uppercase tracking-wide">Paid Development Info</span>
                <div className="flex flex-col gap-1.5 mt-2 bg-bg-2 border border-border rounded-lg p-3 font-mono text-xs">
                  <div className="flex justify-between">
                    <span className="text-text-sub font-semibold">LDF Basis:</span>
                    <span className="text-text-main font-bold capitalize">{paidLdfBase.replace(/([A-Z])/g, ' $1')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-text-sub font-semibold">Tail Factor:</span>
                    <span className="text-accent font-bold">{paidTailFactor.toFixed(4)}</span>
                  </div>
                  <div className="mt-2 text-[10px] border-t border-border pt-2 text-text-sub leading-relaxed">
                    Selected Paid LDFs: [{triangle.ldfs.slice(0, 3).map((f) => (f[paidLdfBase as keyof typeof f] as number || 1.0).toFixed(3)).join(', ')}, ...]
                  </div>
                </div>
              </div>

              {/* Incurred LDF Selection */}
              {triangle.incurred_ldfs && (
                <div>
                  <span className="text-[11px] font-bold text-text-sub uppercase tracking-wide">Incurred Development Info</span>
                  <div className="flex flex-col gap-1.5 mt-2 bg-bg-2 border border-border rounded-lg p-3 font-mono text-xs">
                    <div className="flex justify-between">
                      <span className="text-text-sub font-semibold">LDF Basis:</span>
                      <span className="text-text-main font-bold capitalize">{incurredLdfBase.replace(/([A-Z])/g, ' $1')}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-sub font-semibold">Tail Factor:</span>
                      <span className="text-accent font-bold">{incurredTailFactor.toFixed(4)}</span>
                    </div>
                    <div className="mt-2 text-[10px] border-t border-border pt-2 text-text-sub leading-relaxed">
                      Selected Incurred LDFs: [{triangle.incurred_ldfs.slice(0, 3).map((f) => (f[incurredLdfBase as keyof typeof f] as number || 1.0).toFixed(3)).join(', ')}, ...]
                    </div>
                  </div>
                </div>
              )}

              {/* Premium Status Warning */}
              {!hasPremium && (
                <div className="bg-accent-red/5 border border-accent-red/20 text-accent-red rounded-lg p-3.5 text-xs leading-relaxed">
                  ⚠️ <strong>Earned Premium data is missing.</strong> Premium-dependent methods (BF, Benktander, Cape Cod, ELR) will be excluded from execution.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
