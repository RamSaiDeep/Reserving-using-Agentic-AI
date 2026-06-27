'use client';

import React, { useState, useEffect } from 'react';
import {
  ChatMessage,
  SummaryData,
  TriangleData,
  RankedModel,
  ExecuteResult,
  ExecutionConfig,
} from '@/types';

// Import Feature Components
import UploadZone from '@/features/upload/UploadZone';
import SummaryView from '@/features/diagnostics/SummaryView';
import TriangleView from '@/features/diagnostics/TriangleView';
import DiagnosticsDashboard from '@/features/diagnostics/DiagnosticsDashboard';
import ConfigureAssumptions from '@/features/comparison/ConfigureAssumptions';
import ComparisonDashboard from '@/features/comparison/ComparisonDashboard';
import RecommendationView from '@/features/recommendation/RecommendationView';
import ReportView from '@/features/report/ReportView';
import SidebarChat from '@/features/chat/SidebarChat';
import SettingsModal from '@/components/SettingsModal';

import { CURRENCIES, CurrencyCode } from '@/lib/utils';

const TABS = [
  { id: 'dataset', label: 'Dataset' },
  { id: 'triangles', label: 'Loss Triangles' },
  { id: 'diagnostics', label: 'Diagnostics' },
  { id: 'comparison', label: 'Model Comparison' },
  { id: 'recommendation', label: 'AI Recommendation' },
  { id: 'report', label: 'Report Preview' }
];

export default function Workspace() {
  // Navigation
  const [activeTab, setActiveTab] = useState<string>('dataset');
  const [showConfig, setShowConfig] = useState<boolean>(true); // Toggles between ConfigureAssumptions and ComparisonDashboard in Comparison tab

  // Session & Actuarial State
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [triangle, setTriangle] = useState<TriangleData | null>(null);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [diagnostics, setDiagnostics] = useState<any>(null);
  const [isDiagnosticsLoading, setIsDiagnosticsLoading] = useState(false);
  const [recommendation, setRecommendation] = useState<string | null>(null);
  const [customLDFs, setCustomLDFs] = useState<number[]>([]);
  const [ldfBase, setLdfBase] = useState('volumeWeighted');
  const [tailFactor, setTailFactor] = useState(1.0);
  const [customIncurredLDFs, setCustomIncurredLDFs] = useState<number[]>([]);
  const [incurredLdfBase, setIncurredLdfBase] = useState('volumeWeighted');
  const [incurredTailFactor, setIncurredTailFactor] = useState(1.0);
  const [dataSource, setDataSource] = useState<'paid' | 'incurred'>('paid');
  const [ranked, setRanked] = useState<RankedModel[]>([]);
  const [executeResult, setExecuteResult] = useState<ExecuteResult | null>(null);
  const [currency, setCurrency] = useState<CurrencyCode>('USD');
  const [configs, setConfigs] = useState<ExecutionConfig>({
    CL: { enabled: true },
    MCL: { enabled: true },
    BF: { enabled: true, aprioriLossRatio: null },
    BK: { enabled: true, aprioriLossRatio: null, iterations: 2 },
    CC: { enabled: true, decay: 1.0, aprioriLossRatio: null },
    ELR: { enabled: true, aprioriLossRatio: null },
    CLK: { enabled: true, curveType: 'weibull' },
    CO: { enabled: true },
    FS: { enabled: true, approach: 'approach1', inflationRate: 3.0 }
  });
  const [suggestedElrPaid, setSuggestedElrPaid] = useState<number | null>(65.0);
  const [suggestedElrIncurred, setSuggestedElrIncurred] = useState<number | null>(65.0);
  const [suggestedMatureYears, setSuggestedMatureYears] = useState<number[]>([]);
  const [matureCdfThreshold, setMatureCdfThreshold] = useState<number>(1.05);
  const [isAiLoading, setIsAiLoading] = useState<boolean>(false);
  const [aiLoadingStep, setAiLoadingStep] = useState<number>(0);
  const [aiError, setAiError] = useState<string | null>(null);

  // Settings
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [baseUrl, setBaseUrl] = useState('');
  const [modelName, setModelName] = useState('');
  const [apiKey, setApiKey] = useState('');

  // Sidebar Chat / Logs
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-msg',
      role: 'system',
      text: 'Multi-Agent architecture active. Please start the Python server, then configure your parameters and upload a CSV file.',
    },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState<{ role: 'user' | 'model'; text: string }[]>([]);

  // Load localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setBaseUrl(localStorage.getItem('ai_base_url') || '');
      setModelName(localStorage.getItem('ai_model_name') || '');
      setApiKey(localStorage.getItem('ai_api_key') || '');
    }
  }, []);

  // Sync suggestions and prefill configs when triangle changes
  useEffect(() => {
    if (triangle) {
      const elrPaid = triangle.suggested_elr_paid !== undefined ? triangle.suggested_elr_paid : 65.0;
      const elrInc = triangle.suggested_elr_incurred !== undefined ? triangle.suggested_elr_incurred : 65.0;

      setSuggestedElrPaid(elrPaid);
      setSuggestedElrIncurred(elrInc);
      setSuggestedMatureYears(triangle.suggested_mature_years || []);

      setConfigs((prev) => {
        const nextConfigs = { ...prev };

        const codes = Object.keys(nextConfigs);
        for (const code of codes) {
          const methodConfig = { ...(nextConfigs[code] || { enabled: true }) };

          if (triangle.method_availability && triangle.method_availability[code]) {
            methodConfig.enabled = triangle.method_availability[code].available;
          } else if (['BF', 'BK', 'CC', 'ELR'].includes(code)) {
            methodConfig.enabled = triangle.hasPremium;
          }

          if (code === 'BF' || code === 'BK' || code === 'ELR') {
            const appropriateElr = dataSource === 'paid' ? elrPaid : elrInc;
            methodConfig.aprioriLossRatio = methodConfig.aprioriLossRatio !== null && methodConfig.aprioriLossRatio !== undefined
              ? methodConfig.aprioriLossRatio
              : appropriateElr;
          }

          nextConfigs[code] = methodConfig;
        }

        return nextConfigs;
      });
    }
  }, [triangle, dataSource]);

  // Fetch advanced diagnostics whenever sessionId changes
  useEffect(() => {
    if (sessionId) {
      loadDiagnostics(sessionId);
    } else {
      setDiagnostics(null);
    }
  }, [sessionId]);

  // Recalculate suggestions when mature CDF threshold changes
  useEffect(() => {
    if (sessionId && matureCdfThreshold) {
      fetch(getApiUrl('recalculate_suggestions'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          mature_cdf_threshold: matureCdfThreshold,
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.success) {
            setSuggestedElrPaid(data.suggested_elr_paid);
            setSuggestedElrIncurred(data.suggested_elr_incurred);
            setSuggestedMatureYears(data.suggested_mature_years);
          }
        })
        .catch((err) => console.error('Failed to recalculate suggestions:', err));
    }
  }, [matureCdfThreshold, sessionId]);

  const loadDiagnostics = async (sid: string) => {
    setIsDiagnosticsLoading(true);
    try {
      const res = await fetch(getApiUrl(`export/${sid}`));
      if (res.ok) {
        const data = await res.json();
        if (data && data.diagnostics) {
          setDiagnostics(data.diagnostics);
        }
      }
    } catch (e) {
      console.error('Failed to load advanced diagnostics:', e);
    } finally {
      setIsDiagnosticsLoading(false);
    }
  };

  const saveSettings = (newBase: string, newModel: string, newKey: string) => {
    setBaseUrl(newBase);
    setModelName(newModel);
    setApiKey(newKey);
    localStorage.setItem('ai_base_url', newBase);
    localStorage.setItem('ai_model_name', newModel);
    localStorage.setItem('ai_api_key', newKey);
    setIsSettingsOpen(false);
    addLogMessage('system', 'AI Settings saved and verified.');
  };

  // Log helpers
  const addLogMessage = (
    role: ChatMessage['role'],
    text: string,
    state: ChatMessage['state'] = ''
  ): string => {
    const id = `msg-${Math.random().toString(36).substring(7)}`;
    setMessages((prev) => [...prev, { id, role, text, state }]);
    return id;
  };

  const updateLogMessage = (id: string, text: string) => {
    setMessages((prev) =>
      prev.map((msg) => (msg.id === id ? { ...msg, text, state: '' } : msg))
    );
  };

  const getApiUrl = (endpoint: string) => {
    if (typeof window !== 'undefined') {
      const hn = window.location.hostname;
      const isLocal =
        hn === 'localhost' ||
        hn === '127.0.0.1' ||
        hn === '[::1]' ||
        hn === '0.0.0.0' ||
        hn.startsWith('192.168.') ||
        hn.startsWith('10.') ||
        hn.startsWith('172.') ||
        hn.endsWith('.local');
      const base = isLocal
        ? 'http://localhost:8000/api'
        : process.env.NEXT_PUBLIC_API_URL;
      return `${base}/${endpoint}`;
    }
    return `/api/${endpoint}`;
  };

  // Process SSE Stream
  const processPipelineStream = async (res: Response, uploadMsgId: string) => {
    if (!res.body) return;
    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const msg = JSON.parse(line);
          if (msg.type === 'agent') {
            addLogMessage('action', `<strong>[${msg.agent}]</strong> ${msg.text}`);
            if (msg.agent === 'System Error' || (msg.text && msg.text.includes('Agent Error'))) {
              updateLogMessage(uploadMsgId, 'Pipeline aborted due to backend error.');
              return;
            }
          } else if (msg.type === 'input_required') {
            setSessionId(msg.session_id);
            addLogMessage('action', `Requires Input: Data Conditions`);
            return;
          } else if (msg.type === 'complete') {
            setSessionId(msg.session_id);
            setSummary(msg.summary);
            setTriangle(msg.triangle);
            setRecommendation(msg.recommendation);
            setCustomLDFs([]);
            setCustomIncurredLDFs([]);

            // Build initial ranked list mapping
            if (msg.triangle) {
              setupRankedMethods(msg.triangle);
            }

            // Auto switch to dataset view
            setActiveTab('dataset');

            updateLogMessage(
              uploadMsgId,
              'Pipeline execution completed. Dataset loaded in main workspace.'
            );
          } else if (msg.type === 'error') {
            updateLogMessage(uploadMsgId, `Failed: ${msg.message}`);
          }
        } catch (err) {
          console.error('Stream parse error:', err);
        }
      }
    }
  };

  const setupRankedMethods = (t: TriangleData) => {
    let rankedMethods: RankedModel[] = [
      {
        code: 'BF',
        label: 'Bornhuetter-Ferguson',
        desc: 'Uses a priori expected loss ratios.',
        score: 10,
        recommended: true,
        params: [{ key: 'aprioriLossRatio', label: 'A Priori Loss Ratio (%)', default: 65 }],
      },
      {
        code: 'CL',
        label: 'Chain Ladder (Basic)',
        desc: 'Standard development method.',
        score: 9,
        recommended: true,
        params: [],
      },
      {
        code: 'ELR',
        label: 'Expected Loss Ratio',
        desc: 'Expected Claims Method using a user-specified a priori loss ratio.',
        score: 8.5,
        recommended: false,
        params: [{ key: 'aprioriLossRatio', label: 'A Priori Loss Ratio (%)', default: 65 }],
      },
      {
        code: 'CC',
        label: 'Cape Cod',
        desc: 'Uses an overall loss ratio for stability.',
        score: 8,
        recommended: false,
        params: [
          { key: 'aprioriLossRatio', label: 'A Priori Loss Ratio (%)', default: 65 },
          { key: 'decay', label: 'Decay Factor', default: 1.0 }
        ],
      },
      {
        code: 'BK',
        label: 'Benktander',
        desc: 'Iterative blend of BF and CL.',
        score: 7,
        recommended: false,
        params: [
          { key: 'aprioriLossRatio', label: 'A Priori Loss Ratio (%)', default: 65 },
          { key: 'iterations', label: 'Iterations (c)', default: 1 },
        ],
      },
      {
        code: 'MCL',
        label: 'Mack Chain Ladder',
        desc: 'Calculates standard errors and variance.',
        score: 6,
        recommended: false,
        params: [],
      },
      {
        code: 'CLK',
        label: 'Clark Stochastic',
        desc: 'Stochastic curve fitting approximation.',
        score: 5,
        recommended: false,
        params: [{ key: 'curveType', label: 'Growth Curve', default: 'loglogistic' }],
      },
      {
        code: 'CO',
        label: 'Case Outstanding',
        desc: 'Uses only reported case reserves.',
        score: 4,
        recommended: false,
        params: [],
      },
    ];

    if (!t.hasPremium) {
      rankedMethods = rankedMethods.filter((m) => !['BF', 'CC', 'BK', 'ELR'].includes(m.code));
    }
    setRanked(rankedMethods);
  };

  const handleRunPipeline = async (
    file: File,
    rateChanges: { effective_date: string; rate_change: number }[],
    context: { tail: string; volatility: string; environment: string; distortions: string }
  ) => {
    const uploadMsgId = addLogMessage(
      'agent',
      `🚀 Launching Sequential Multi-Agent Pipeline for <strong>${file.name}</strong>...`,
      'analyzing'
    );

    const formData = new FormData();
    formData.append('file', file);
    formData.append('n_years', '5');

    if (rateChanges.length > 0) {
      formData.append('rate_changes_json', JSON.stringify(rateChanges));
      const years = rateChanges.map((r) => new Date(r.effective_date).getFullYear());
      const maxYear = Math.max(...years);
      formData.append('valuation_year', maxYear.toString());
    }

    formData.append('business_context', JSON.stringify(context));

    if (apiKey) {
      formData.append('api_key', apiKey);
      formData.append('base_url', baseUrl);
      formData.append('model_name', modelName);
    }

    try {
      const res = await fetch(getApiUrl('upload'), {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('Network response was not ok');
      await processPipelineStream(res, uploadMsgId);
    } catch (e: any) {
      addLogMessage('error', `Pipeline Error: ${e.message}`);
      updateLogMessage(uploadMsgId, `Failed to process: ${e.message}`);
    }
  };

  const handleSubmitConditions = async (conditions: {
    credible: boolean;
    freq: boolean;
    distort: boolean;
  }) => {
    const resumeMsgId = addLogMessage('agent', '⚙️ Resuming sequential pipeline...', 'analyzing');
    try {
      const res = await fetch(getApiUrl('resume_pipeline'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          conditions: conditions,
          api_key: apiKey,
          base_url: baseUrl,
          model_name: modelName,
        }),
      });

      if (!res.ok) throw new Error('Network response was not ok');
      updateLogMessage(resumeMsgId, 'Conditions submitted. Pipeline resumed.');
      await processPipelineStream(res, resumeMsgId);
    } catch (e: any) {
      addLogMessage('error', `Pipeline Resume Error: ${e.message}`);
      updateLogMessage(resumeMsgId, `Failed to resume: ${e.message}`);
    }
  };

  const fetchAiRecommendation = async (execId: string) => {
    setIsAiLoading(true);
    setAiError(null);
    setAiLoadingStep(1); // Math reserving completed

    const stepIntervals = [
      setTimeout(() => setAiLoadingStep(2), 600),   // Comparing reserving methods
      setTimeout(() => setAiLoadingStep(3), 2000),  // AI reviewing diagnostics
      setTimeout(() => setAiLoadingStep(4), 5000),  // Preparing recommendation
    ];

    try {
      const res = await fetch(getApiUrl('recommendation'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          execution_id: execId,
          api_key: apiKey,
          base_url: baseUrl,
          model_name: modelName,
        }),
      });

      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      stepIntervals.forEach(clearTimeout);

      setExecuteResult((prev) =>
        prev
          ? {
              ...prev,
              ai_recommendation: data.ai_recommendation,
              summary: {
                best_estimate: data.ai_recommendation?.best_estimate || prev.summary?.best_estimate,
                selected_method: data.ai_recommendation?.recommended_method || prev.summary?.selected_method,
              }
            }
          : null
      );
      
      addLogMessage('system', '🤖 <strong>AI Recommendation Agent</strong> analysis is ready! Open the Recommendation or Report tab to view.');
      setIsAiLoading(false);
      setAiLoadingStep(0);
    } catch (err: any) {
      stepIntervals.forEach(clearTimeout);
      setAiError(err.message || 'Failed to generate AI recommendation.');
      setIsAiLoading(false);
      setAiLoadingStep(0);
      addLogMessage('error', `AI Recommendation failed: ${err.message}. Mathematical results remain valid.`);
    }
  };

  const handleExecuteAllModels = async () => {
    setExecuteResult(null);
    setShowConfig(false);
    setIsAiLoading(false);
    setAiError(null);
    setAiLoadingStep(0);

    const execMsgId = addLogMessage(
      'agent',
      `⚙️ <strong>Execution Agent</strong> running reserving models concurrently on backend…`,
      'analyzing'
    );

    const ldfsToUse = customLDFs.length > 0 ? customLDFs : triangle?.ldfs.slice(0, -1).map((s: any) => s[ldfBase] ?? 1.0) || [];
    const incurredLdfsToUse = customIncurredLDFs.length > 0 ? customIncurredLDFs : triangle?.incurred_ldfs?.slice(0, -1).map((s: any) => s[incurredLdfBase] ?? 1.0) || [];

    const payload = {
      session_id: sessionId,
      configs: configs,
      data_source: dataSource,
      paid_ldfs: [...ldfsToUse, tailFactor],
      incurred_ldfs: [...incurredLdfsToUse, incurredTailFactor],
      paid_tail_factor: tailFactor,
      incurred_tail_factor: incurredTailFactor,
      mature_cdf_threshold: matureCdfThreshold,
      api_key: apiKey,
      base_url: baseUrl,
      model_name: modelName,
    };

    try {
      const res = await fetch(getApiUrl('execute_all'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      setExecuteResult(data);
      updateLogMessage(execMsgId, 'Multi-model execution complete. Dashboard loaded.');

      // Auto-switch to recommendation results once execute completes
      setActiveTab('comparison');

      if (data.execution_id) {
        fetchAiRecommendation(data.execution_id);
      }
    } catch (e: any) {
      addLogMessage('error', `Execution failed: ${e.message}`);
      updateLogMessage(execMsgId, `Execution failed: ${e.message}`);
    }
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || !sessionId) return;
    const userText = chatInput.trim();
    setChatInput('');

    addLogMessage('user', userText);
    const typingId = addLogMessage('agent', '…', 'analyzing');

    try {
      const res = await fetch(getApiUrl('chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: userText,
          history: chatHistory,
          api_key: apiKey,
          base_url: baseUrl,
          model_name: modelName,
        }),
      });

      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      setChatHistory((prev) => [
        ...prev,
        { role: 'user', text: userText },
        { role: 'model', text: data.reply },
      ]);
      updateLogMessage(typingId, data.reply);
    } catch (e: any) {
      updateLogMessage(typingId, `Error: ${e.message}`);
    }
  };

  const handleUpdateMappings = async (
    newRoles: Record<string, string | null>,
    selectedEntities?: string[] | null
  ) => {
    const updateMsgId = addLogMessage(
      'agent',
      '⚙️ <strong>System Agent</strong> rebuilding loss triangle...',
      'analyzing'
    );
    try {
      const res = await fetch(getApiUrl('update_mappings'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          reserving_roles: newRoles,
          selected_entities: selectedEntities || null,
        }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      setSummary(data.summary);
      setTriangle(data.triangle);
      setCustomLDFs([]);
      setCustomIncurredLDFs([]);
      updateLogMessage(updateMsgId, 'Triangle configurations successfully updated.');
    } catch (e: any) {
      addLogMessage('error', `Configuration Update Failed: ${e.message}`);
      updateLogMessage(updateMsgId, `Failed to update configurations: ${e.message}`);
    }
  };

  const handleUpdateEntities = async (selectedEntities: string[] | null) => {
    const updateMsgId = addLogMessage(
      'agent',
      '⚙️ <strong>System Agent</strong> rebuilding loss triangle with custom entity scope...',
      'analyzing'
    );
    try {
      const res = await fetch(getApiUrl('update_mappings'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          reserving_roles: summary?.inspection?.reserving_roles || {},
          selected_entities: selectedEntities,
        }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      setSummary(data.summary);
      setTriangle(data.triangle);
      setCustomLDFs([]);
      setCustomIncurredLDFs([]);
      updateLogMessage(updateMsgId, 'Triangle successfully rebuilt with selected entity scope.');
    } catch (e: any) {
      addLogMessage('error', `Scope Update Failed: ${e.message}`);
      updateLogMessage(updateMsgId, `Failed to update scope: ${e.message}`);
    }
  };

  // Resets the workspace to upload a new file
  const handleResetWorkspace = () => {
    setSessionId(null);
    setTriangle(null);
    setSummary(null);
    setExecuteResult(null);
    setRecommendation(null);
    setDiagnostics(null);
    setActiveTab('dataset');
  };

  // Checks if a tab should be disabled
  const isTabEnabled = (tabId: string) => {
    if (tabId === 'dataset') return true;
    if (!sessionId || !summary) return false;

    // Recommendations & Reports need execute results
    if (tabId === 'recommendation' || tabId === 'report') {
      return !!executeResult;
    }
    return true;
  };

  // Render Router
  const renderWorkspaceTab = () => {
    switch (activeTab) {
      case 'dataset':
        return summary ? (
          <div className="space-y-4">
            <div className="flex justify-between items-center bg-bg-1 border border-border p-4 rounded-xl shadow-sm">
              <div className="text-left">
                <h3 className="text-sm font-bold text-text-main">Active Claims Dataset</h3>
                <p className="text-xs text-text-sub font-mono">Session ID: {sessionId}</p>
              </div>
              <button
                onClick={handleResetWorkspace}
                className="px-3.5 py-1.5 bg-accent-red/10 border border-accent-red/20 text-accent-red rounded text-xs font-bold hover:bg-accent-red/20 transition-all cursor-pointer"
              >
                Reset & Re-upload
              </button>
            </div>
            <SummaryView
              summary={summary}
              currency={currency}
              onProceed={() => setActiveTab('triangles')}
              onUpdateMappings={handleUpdateMappings}
            />
          </div>
        ) : (
          <UploadZone onRunPipeline={handleRunPipeline} />
        );

      case 'triangles':
        return triangle && summary ? (
          <TriangleView
            triangle={triangle}
            summary={summary}
            currency={currency}
            ldfBase={ldfBase}
            onChangeLdfBase={(base) => {
              setLdfBase(base);
              setCustomLDFs(triangle.ldfs.slice(0, -1).map((s: any) => s[base] ?? 1.0));
            }}
            customLDFs={
              customLDFs.length > 0
                ? customLDFs
                : triangle.ldfs.slice(0, -1).map((s: any) => s[ldfBase] ?? 1.0)
            }
            onChangeCustomLDFs={setCustomLDFs}
            tailFactor={tailFactor}
            onChangeTailFactor={setTailFactor}
            incurredLdfBase={incurredLdfBase}
            onChangeIncurredLdfBase={(base) => {
              setIncurredLdfBase(base);
              if (triangle.incurred_ldfs) {
                setCustomIncurredLDFs(triangle.incurred_ldfs.slice(0, -1).map((s: any) => s[base] ?? 1.0));
              }
            }}
            customIncurredLDFs={
              customIncurredLDFs.length > 0
                ? customIncurredLDFs
                : triangle.incurred_ldfs?.slice(0, -1).map((s: any) => s[incurredLdfBase] ?? 1.0) || []
            }
            onChangeCustomIncurredLDFs={setCustomIncurredLDFs}
            incurredTailFactor={incurredTailFactor}
            onChangeIncurredTailFactor={setIncurredTailFactor}
            onProceed={() => setActiveTab('comparison')}
            onUpdateEntities={handleUpdateEntities}
          />
        ) : null;

      case 'diagnostics':
        return (
          <DiagnosticsDashboard
            diagnostics={diagnostics}
            isLoading={isDiagnosticsLoading}
          />
        );

      case 'comparison':
        if (showConfig || !executeResult) {
          return triangle ? (
            <ConfigureAssumptions
              configs={configs}
              onChangeConfigs={setConfigs}
              triangle={triangle}
              dataSource={dataSource}
              onChangeDataSource={setDataSource}
              suggestedElrPaid={suggestedElrPaid}
              suggestedElrIncurred={suggestedElrIncurred}
              paidLdfBase={ldfBase}
              incurredLdfBase={incurredLdfBase}
              paidTailFactor={tailFactor}
              incurredTailFactor={incurredTailFactor}
              onBack={() => setActiveTab('triangles')}
              onRunComparison={handleExecuteAllModels}
            />
          ) : null;
        } else {
          return (
            <ComparisonDashboard
              data={executeResult}
              currency={currency}
              onBack={() => setShowConfig(true)}
              sessionId={sessionId!}
              getApiUrl={getApiUrl}
            />
          );
        }

      case 'recommendation':
        return (
          <RecommendationView
            data={executeResult}
            currency={currency}
            isLoading={isAiLoading}
            loadingStep={aiLoadingStep}
            error={aiError}
            onRetry={() => {
              if (executeResult?.execution_id) {
                fetchAiRecommendation(executeResult.execution_id);
              }
            }}
          />
        );

      case 'report':
        return (
          <ReportView
            data={executeResult}
            summary={summary}
            currency={currency}
            isLoading={isAiLoading}
            loadingStep={aiLoadingStep}
            error={aiError}
            onRetry={() => {
              if (executeResult?.execution_id) {
                fetchAiRecommendation(executeResult.execution_id);
              }
            }}
            sessionId={sessionId!}
            getApiUrl={getApiUrl}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="grid grid-rows-[48px_1fr] grid-cols-[360px_1fr] h-screen w-screen overflow-hidden bg-bg text-text-main font-sans">
      {/* Top Header */}
      <header className="col-span-2 flex items-center justify-between px-5 bg-bg-1 border-b border-border h-12 shadow-sm z-10">
        <div className="font-bold text-sm text-text-main whitespace-nowrap">
          Actuarial <span className="text-accent">Reserve</span> AI Workspace
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 bg-bg-2 p-1 rounded-lg border border-border">
          {TABS.map((t) => {
            const enabled = isTabEnabled(t.id);
            const active = activeTab === t.id;
            return (
              <button
                key={t.id}
                disabled={!enabled}
                onClick={() => {
                  setActiveTab(t.id);
                  if (t.id === 'comparison') {
                    // Show comparison results if already executed
                    setShowConfig(!executeResult);
                  }
                }}
                className={`px-3.5 py-1.5 text-[11px] font-bold rounded transition-all whitespace-nowrap cursor-pointer ${active
                    ? 'bg-accent text-white shadow-sm'
                    : enabled
                      ? 'text-text-sub hover:text-text-main hover:bg-bg-1'
                      : 'text-text-muted opacity-40 cursor-not-allowed'
                  }`}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Header Right Settings & Controls */}
        <div className="flex items-center gap-2.5">
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value as CurrencyCode)}
            className="px-2 py-1.5 bg-bg-2 border border-border rounded text-xs text-text-sub font-semibold hover:border-border-2 outline-none cursor-pointer h-8"
          >
            {Object.entries(CURRENCIES).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>

          <button
            onClick={() => setIsSettingsOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-bg-2 border border-border rounded text-xs text-text-sub font-semibold hover:border-border-2 hover:text-text-main transition-colors cursor-pointer h-8"
          >
            <div
              className={`w-1.5 h-1.5 rounded-full transition-colors ${apiKey ? 'bg-accent-green' : 'bg-text-muted'
                }`}
              title={apiKey ? 'AI API connected' : 'AI not connected'}
            />
            AI Settings
          </button>
        </div>
      </header>

      {/* Main Grid Workspace Panels */}
      <SidebarChat
        messages={messages}
        chatInput={chatInput}
        setChatInput={setChatInput}
        onSendMessage={handleSendMessage}
        onSubmitConditions={handleSubmitConditions}
        isSessionActive={!!sessionId}
      />

      <main className="flex-1 overflow-y-auto bg-bg p-6 md:p-8">
        {renderWorkspaceTab()}
      </main>

      {/* AI Key Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        baseUrl={baseUrl}
        modelName={modelName}
        apiKey={apiKey}
        onSave={saveSettings}
      />
    </div>
  );
}
