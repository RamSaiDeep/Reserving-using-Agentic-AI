'use client';
import React, { useState, useRef } from 'react';

interface RateChange {
  id: string;
  effectiveDate: string;
  rateChange: number;
}

interface UploadZoneProps {
  onRunPipeline: (file: File, rateChanges: { effective_date: string; rate_change: number }[], context: { tail: string; volatility: string; environment: string; distortions: string }) => void;
}

export default function UploadZone({ onRunPipeline }: UploadZoneProps) {
  const [rateChanges, setRateChanges] = useState<RateChange[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isLaunching, setIsLaunching] = useState(false);

  // Business Context values
  const [tail, setTail] = useState('Not Known');
  const [volatility, setVolatility] = useState('Not Known');
  const [environment, setEnvironment] = useState('Not Known');
  const [distortions, setDistortions] = useState('Not Known');

  const addRateChangeRow = () => {
    setRateChanges([
      ...rateChanges,
      {
        id: Math.random().toString(36).substring(7),
        effectiveDate: '',
        rateChange: 0,
      },
    ]);
  };

  const removeRateChangeRow = (id: string) => {
    setRateChanges(rateChanges.filter((rc) => rc.id !== id));
  };

  const updateRateChange = (id: string, field: 'effectiveDate' | 'rateChange', value: any) => {
    setRateChanges(
      rateChanges.map((rc) => {
        if (rc.id === id) {
          return { ...rc, [field]: value };
        }
        return rc;
      })
    );
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const clearSelectedFile = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSubmit = () => {
    if (!selectedFile) return;
    setIsLaunching(true);

    const formattedRateChanges = rateChanges
      .filter((rc) => rc.effectiveDate && !isNaN(rc.rateChange))
      .map((rc) => ({
        effective_date: rc.effectiveDate,
        rate_change: rc.rateChange / 100.0,
      }));

    onRunPipeline(
      selectedFile,
      formattedRateChanges,
      { tail, volatility, environment, distortions }
    );
  };

  return (
    <div className="flex flex-col flex-1 animate-slide-in">
      <div className="mb-5">
        <h2 className="text-lg font-bold text-text-main">Upload Loss Data</h2>
        <p className="text-xs text-text-sub mt-0.5">Sequential Agent Pipeline</p>
      </div>

      {/* Historical Rate Changes */}
      <div className="mb-6 p-4 bg-white/5 border border-border rounded-lg">
        <div className="flex justify-between items-center mb-2">
          <label className="text-xs font-semibold text-text-main">Historical Rate Changes (Optional):</label>
          <button
            onClick={addRateChangeRow}
            className="px-2 py-1 bg-transparent hover:bg-white/10 border border-border-2 rounded text-[11px] text-text-sub hover:text-text-main font-medium transition-colors"
          >
            + Add Row
          </button>
        </div>

        <div className="flex flex-col gap-2">
          {rateChanges.map((rc) => (
            <div key={rc.id} className="flex gap-2 items-center">
              <input
                type="date"
                value={rc.effectiveDate}
                onChange={(e) => updateRateChange(rc.id, 'effectiveDate', e.target.value)}
                className="flex-1 bg-black/30 border border-white/10 text-xs text-text-main px-3 py-2 rounded outline-none focus:border-accent"
              />
              <input
                type="number"
                placeholder="Change % (e.g. 5)"
                value={rc.rateChange === 0 ? '' : rc.rateChange}
                onChange={(e) => updateRateChange(rc.id, 'rateChange', parseFloat(e.target.value) || 0)}
                step="any"
                className="flex-1 bg-black/30 border border-white/10 text-xs text-text-main px-3 py-2 rounded outline-none focus:border-accent"
              />
              <button
                onClick={() => removeRateChangeRow(rc.id)}
                className="p-2 text-text-sub hover:text-accent-red hover:bg-white/5 rounded transition-colors"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        <div className="text-[10px] text-text-sub/70 mt-2.5">
          If provided, the Preprocessing Agent will on-level your premiums automatically before the Triangle Builder runs.
        </div>
      </div>

      {/* Dropzone */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`border-1.5 border-dashed rounded-lg p-10 text-center cursor-pointer transition-all duration-200 bg-bg-1 ${
          isDragOver || selectedFile
            ? 'border-accent bg-accent-dim'
            : 'border-border-2 hover:border-accent hover:bg-accent-dim'
        }`}
      >
        <div className="text-3xl mb-2 text-text-muted">{selectedFile ? '📄' : '↑'}</div>
        <div className="text-sm font-semibold text-text-main mb-1">
          {selectedFile ? 'File selected — see preview below' : 'Drop CSV file here or click to browse'}
        </div>
        <div className="text-xs text-text-sub">CSV or TXT files only</div>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".csv,.txt"
          className="hidden"
        />
      </div>

      {/* File Preview Bar */}
      {selectedFile && (
        <div className="mt-2.5 p-2.5 px-3.5 bg-accent-green/8 border border-accent-green/30 rounded-md flex items-center gap-2.5 animate-slide-in">
          <span className="text-accent-green text-lg">✓</span>
          <span className="text-accent-green text-xs font-semibold flex-1 truncate">
            {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
          </span>
          <button
            onClick={clearSelectedFile}
            className="text-text-sub hover:text-text-main text-base cursor-pointer line-height-none p-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Business Context Selectors */}
      <div className="mt-5 p-4 bg-purple-400/5 border border-purple-400/20 rounded-lg">
        <div className="text-xs font-bold text-purple-400 mb-3 flex items-center gap-1.5">
          ✦ Business &amp; Data Context
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] text-text-sub font-semibold">Line of Business</label>
            <select
              value={tail}
              onChange={(e) => setTail(e.target.value)}
              className="w-full bg-black/30 border border-purple-400/30 rounded p-2 text-xs text-text-main outline-none"
            >
              <option value="Not Known">Not Known</option>
              <option value="Short-tail">Short-tail (e.g. Auto Phys Dam, Property)</option>
              <option value="Long-tail">Long-tail (e.g. Workers Comp, Liability)</option>
            </select>
            <div className="text-[10px] text-text-sub/50 leading-relaxed">
              <b>Line of Business (Tail Length):</b> Dictates settlement speed. Short-tail claims close quickly (e.g., Property), while Long-tail claims take many years (e.g., Workers Comp).
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] text-text-sub font-semibold">Data Volatility</label>
            <select
              value={volatility}
              onChange={(e) => setVolatility(e.target.value)}
              className="w-full bg-black/30 border border-purple-400/30 rounded p-2 text-xs text-text-main outline-none"
            >
              <option value="Not Known">Not Known</option>
              <option value="Stable">Stable &amp; Credible</option>
              <option value="Volatile">Thin or Volatile</option>
            </select>
            <div className="text-[10px] text-text-sub/50 leading-relaxed">
              <b>Credibility (Data Volatility):</b> High volume data is stable for development-based methods (Chain Ladder). Volatile data requires expected-loss blends (BF).
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] text-text-sub font-semibold">Environment</label>
            <select
              value={environment}
              onChange={(e) => setEnvironment(e.target.value)}
              className="w-full bg-black/30 border border-purple-400/30 rounded p-2 text-xs text-text-main outline-none"
            >
              <option value="Not Known">Not Known</option>
              <option value="Stable">Stable (No major changes)</option>
              <option value="Changing">Changing (New ops, reforms)</option>
            </select>
            <div className="text-[10px] text-text-sub/50 leading-relaxed">
              <b>Environment:</b> Changes in claims handling speeds or reserve adequacy distort historical patterns, causing projection inaccuracies.
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] text-text-sub font-semibold">Distortions</label>
            <select
              value={distortions}
              onChange={(e) => setDistortions(e.target.value)}
              className="w-full bg-black/30 border border-purple-400/30 rounded p-2 text-xs text-text-main outline-none"
            >
              <option value="Not Known">Not Known</option>
              <option value="None">None (Smooth progression)</option>
              <option value="Present">Present (Large CAT/sporadic claims)</option>
            </select>
            <div className="text-[10px] text-text-sub/50 leading-relaxed">
              <b>Distortions:</b> Catastrophic events or massive sporadic claims skew historical loss development ratios.
            </div>
          </div>
        </div>
      </div>

      {/* Submit Button */}
      <button
        onClick={handleSubmit}
        disabled={!selectedFile || isLaunching}
        className={`mt-6 w-full py-3.5 rounded-lg border-none text-sm font-bold tracking-wider transition-all duration-300 ${
          selectedFile && !isLaunching
            ? 'bg-gradient-to-r from-accent to-accent-green text-white cursor-pointer shadow-[0_4px_20px_rgba(91,124,250,0.4)]'
            : 'bg-white/5 text-text-muted cursor-not-allowed'
        }`}
      >
        {isLaunching ? '⏳ Launching Pipeline...' : '🚀 Run Pipeline →'}
      </button>

      <div className="text-[11px] text-text-muted text-center mt-2">
        {selectedFile ? 'All inputs ready — click to launch the pipeline' : 'Select a CSV file above to enable submission'}
      </div>
    </div>
  );
}
