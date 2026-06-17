// ================================================================
// gemini.js — Gemini API Integration
// ================================================================

class GeminiClient {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.model  = 'gemini-2.0-flash';
    this.baseURL = `https://generativelanguage.googleapis.com/v1beta/models/${this.model}:generateContent`;
    this._context = {}; // shared actuarial context injected into every prompt
  }

  setContext(ctx) {
    this._context = { ...this._context, ...ctx };
  }

  _buildSystemPrompt() {
    const ctx = this._context;
    let system = `You are an expert actuarial reserving assistant embedded in a professional loss reserving platform.
You help actuaries and analysts understand loss development triangles, reserving methods, and IBNR estimates.

Your role:
- Narrate what each agent step is doing in plain, professional language
- Explain WHY IBNR is large or small, citing specific data values
- Guide users through parameter choices (ELR, IBNR load, etc.)
- Flag anomalies or concerns in the data
- Answer actuarial questions conversationally

Current dataset context:
`;

    if (ctx.summary) {
      const s = ctx.summary;
      system += `- Line of Business: ${s.lob || 'Not specified'}
- Accident Years: ${s.oldestAY} – ${s.latestAY} (${s.accidentYears} years)
- Development Periods: ${s.devPeriods} (max ${s.maxDevAge} months)
- Total Paid to Date: ${fmt(s.totalPaid)}
- Triangle Completeness: ${s.completeness}%
- New LOB: ${s.isNewLOB ? 'Yes' : 'No'}
- Has Premium Data: ${s.hasPremium ? 'Yes' : 'No'}
- Has Exposure Data: ${s.hasExposure ? 'Yes' : 'No'}
`;
    }

    if (ctx.selectedMethod) {
      system += `\nSelected Method: ${ctx.selectedMethod}\n`;
    }

    if (ctx.ibnrResults) {
      system += `\nIBNR Results (selected method):
- Total IBNR: ${fmt(ctx.ibnrResults.totalIBNR)}
- Total Ultimate: ${fmt(ctx.ibnrResults.totalUltimate)}
- Total Paid: ${fmt(ctx.ibnrResults.totalPaid)}
`;
    }

    if (ctx.ldfs) {
      system += `\nSelected LDFs: ${ctx.ldfs.map(l => l.toFixed(4)).join(' → ')}\n`;
    }

    if (ctx.premiums) {
      system += `\nPremiums by AY: ${JSON.stringify(ctx.premiums)}\n`;
    }
    if (ctx.exposures) {
      system += `\nExposures by AY: ${JSON.stringify(ctx.exposures)}\n`;
    }

    system += `\nBe concise but insightful. Use actual numbers from the context when explaining.
Do not repeat the question back. Respond in 2–4 sentences unless a longer explanation is warranted.
Format key figures in bold using markdown. Never make up data not in the context.`;

    return system;
  }

  async sendMessage(userMessage, history = []) {
    const systemPrompt = this._buildSystemPrompt();

    // Build conversation contents
    const contents = [];

    // Include history (alternating user/model)
    history.forEach(msg => {
      contents.push({
        role: msg.role === 'user' ? 'user' : 'model',
        parts: [{ text: msg.text }],
      });
    });

    // Current user message
    contents.push({
      role: 'user',
      parts: [{ text: userMessage }],
    });

    const body = {
      system_instruction: { parts: [{ text: systemPrompt }] },
      contents,
      generationConfig: {
        temperature: 0.4,
        maxOutputTokens: 1024,
        topP: 0.9,
      },
    };

    const res = await fetch(`${this.baseURL}?key=${this.apiKey}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const msg = err?.error?.message || `HTTP ${res.status}`;
      throw new Error(`Gemini API error: ${msg}`);
    }

    const data = await res.json();
    return data.candidates?.[0]?.content?.parts?.[0]?.text ?? '';
  }

  // Auto-narrate an agent step
  async narrateStep(stepName, stepData) {
    const prompts = {
      data_summary: `The Data Summary Agent has just analyzed the uploaded CSV file. Here is what it found:
${JSON.stringify(stepData, null, 2)}
Narrate this analysis to the user as if you are the Data Summary Agent reporting findings. Highlight what's notable — data maturity, completeness, whether this appears to be a new line of business, any concerns.`,

      converter: `The Converter Agent has built a loss development triangle from the raw data.
Triangle details: ${JSON.stringify(stepData, null, 2)}
Briefly explain what the triangle shows — development pattern, any obvious trends or gaps.`,

      analysis: `The Analysis Agent has evaluated the triangle and scored reserving methods.
Recommendation: ${stepData.recommended}
Scores: ${JSON.stringify(stepData.scores, null, 2)}
Warnings: ${JSON.stringify(stepData.warnings, null, 2)}
Narrate WHY this method is recommended, and briefly mention alternatives.`,

      execution: `The Execution Agent has computed IBNR using the ${stepData.method} method.
Results: ${JSON.stringify(stepData.results, null, 2)}
Explain WHY total IBNR is at this level. Which accident years are driving reserves? What is the key uncertainty? Mention any notable patterns.`,
    };

    const prompt = prompts[stepName];
    if (!prompt) return null;
    return this.sendMessage(prompt, []);
  }
}

// Helper (needs to be available when gemini.js loads)
function fmt(n) {
  if (n == null || isNaN(n)) return 'N/A';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}
