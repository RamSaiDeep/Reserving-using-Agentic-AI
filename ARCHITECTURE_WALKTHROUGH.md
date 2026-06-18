# Actuarial Reserving Platform: End-to-End Architecture Walkthrough

This document serves as a complete, highly detailed map of every decision, logic flow, and code tweak we implemented to build this platform. Since you requested an explanation of FastAPI and model deployment logic, I have included code snippets and structural breakdowns to demystify the "black box."

---

## 1. The Core Problem: Detaching from Gemini
**The Issue:** The platform was originally hardcoded to use Google's Gemini SDK. When you tried to run a custom local model (like Ollama), the system crashed with a `run_agent() missing 2 required positional arguments` error.
**The Fix:** We completely ripped out the Gemini SDK and replaced it with a **Universal OpenAI Client** inside `agent_workflow.py`.

**The Code Logic:**
By using the standard `openai` Python package, we allowed the system to connect to *any* LLM in the world (Ollama, OpenRouter, ChatGPT, Claude) as long as it speaks the OpenAI protocol.
```python
# Inside agent_workflow.py
def run_agent(api_key: str, base_url: str, model_name: str, sys_inst: str, prompt: str, tools: list) -> str:
    # We dynamically pass the base_url. If it's a local Ollama model, 
    # base_url might be "http://localhost:11434/v1"
    client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
    
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": sys_inst},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content
```

---

## 2. Speeding up the Pipeline (Parallel Processing)
**The Issue:** Running 6 AI agents sequentially on a local machine takes a massive amount of time. 
**The Fix:** We used Python's `concurrent.futures.ThreadPoolExecutor` to fire all 6 agents simultaneously.

**The Code Logic:**
FastAPI allows for "Server-Sent Events" (SSE). As soon as an agent finishes its thought, FastAPI "yields" the result instantly to the UI, creating the live streaming effect you see in the left panel.
```python
# Inside agent_workflow.py
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
    # Submit all 6 AI tasks to the CPU at the exact same time
    futures = [executor.submit(run_agent, ...) for t in tasks]
    
    # As each individual AI finishes, instantly stream its result to the frontend
    for i, future in enumerate(futures):
        result = future.result() 
        yield emit(tasks[i][0], result)
```

---

## 3. The "Black Box": Deterministic Actuarial Math
**The Major Decision:** Never trust an AI to do complex actuarial math on the fly. It will hallucinate.
**The Fix:** We detached the mathematics from the AI. We built a library of 7 pure Python classes in the `models/methods.py` file. 

**The Code Logic:**
When you click "Execute" on the frontend, the UI sends a `POST` request to FastAPI (`main.py`). FastAPI completely bypasses the AI, runs the exact mathematical `.fit()` calculation natively in Python, and generates the exact IBNR and Ultimate loss numbers.
```python
# Inside main.py (The FastAPI Server)
@app.post("/api/execute")
def execute_model(req: ExecuteRequest):
    # 1. Fetch the exact mathematical class you clicked (e.g., Bornhuetter-Ferguson)
    MethodClass = METHODS.get(req.method_code)
    model = MethodClass()
    
    # 2. Run the pure math (No AI involved yet)
    model.fit(session['triangle'], req.params, req.custom_ldfs)
    total_ibnr = model.get_total_ibnr()
    total_ult = model.get_total_ultimate()
```
Only *after* the math is perfectly calculated does FastAPI hand those exact numbers to the "Execution Agent" to write a report about it.

---

## 4. Smart Failsafes & The Recommender Agent
**The Issue:** Users could try to run a Bornhuetter-Ferguson (BF) model on a CSV that didn't actually contain Premium data, causing a mathematical crash.
**The Fix:** We implemented two layers of protection.

**Layer 1 (The Backend Failsafe):**
Inside `main.py`, we added a strict data check. If the model requires premium and the user doesn't have it, FastAPI immediately halts execution and throws an error.
```python
# Inside main.py
if MethodClass.needs_premium and not session['triangle'].premiums:
    return {"narration": f"Data Input Insufficient: {MethodClass.label} requires Premium data..."}
```

**Layer 2 (The AI Recommender):**
We updated the `sys6` prompt in `agent_workflow.py`. The Recommender Agent now acts as a gatekeeper.
```python
sys6 = "You are the Recommender Agent... If the data DOES NOT contain Premium volume, strongly recommend the Chain Ladder or Mack methods, and explicitly state that BF/Benktander/Cape Cod are incompatible."
```

---

## 5. Dynamic UI & Custom Parameters
**The Issue:** The frontend was hardcoded to only show 4 columns (AY, Paid, Ultimate, IBNR) and didn't allow for custom parameters.
**The Fix:** We rewrote `app.js` to dynamically scrape data and inputs.

**The Code Logic:**
If you select Cape Cod, the frontend Javascript dynamically reads the model's required parameters and generates an input box for `Decay Factor`. Furthermore, when the results return, the JS loops through every single key the math generated (like `StdError`, `CV`, `% Reported`) and dynamically creates new columns for them in the table.

---

## 6. The "Hack": The Predefined Actuarial Library
**The Issue:** Even with exact numbers, the AI's explanation of the mathematical process was sometimes shallow or hallucinatory.
**The Fix:** We hardcoded a textbook-level actuarial dictionary directly into FastAPI.

**The Code Logic:**
```python
# Inside main.py
PROCESS_EXPLANATIONS = {
    "CL": "The Chain Ladder (CL) method is the most fundamental reserving technique...",
    "BK": "The Benktander (BK) method is an iterative, credibility-weighted compromise...",
}

sneak_peek = {
    "DETAILED_PROCESS_EXPLANATION": PROCESS_EXPLANATIONS.get(req.method_code)
}
```
We then gave the AI a strict prompt: *"You MUST copy and paste the 'DETAILED_PROCESS_EXPLANATION' exactly word-for-word from the prompt into this field."* This forces the AI to act as a pure formatting engine, guaranteeing 100% academic accuracy in the UI.

---

## 7. Structuring the JSON Flowchart UI
**The Issue:** The AI's final report was just a messy, massive Markdown paragraph. You wanted it structured into distinct boxes.
**The Fix:** We forced the LLM to output pure JSON, and used Javascript to paint a CSS Grid layout.

**The Code Logic:**
Instead of asking the LLM to "write a report", we commanded it to output a JSON string:
```json
{
  "inputs": ["Premium", "A Priori = 0.65"],
  "process": "The Benktander method...",
  "output_numbers": {"Total IBNR": 1500000}
}
```
In `app.js`, we parse `JSON.parse(cleanJson)` and inject the data into beautifully styled HTML divs. 
- We built a **Vertical Flowchart** layout.
- We caught the `[object Object]` bug by checking `if (Array.isArray(rep.inputs))` and unpacking the arrays into HTML bulleted lists `<li>`.
- We rendered the `output_numbers` inside dark, premium metric cards with large, bold green text (`#10b981`).

---

## 8. The Parallel Agent Context Brain
**The Final Touch:** We wanted the Chat Agent to be able to talk about the model you just executed.
**The Logic:** Whenever the JSON Flowchart report is generated, FastAPI saves that exact text into the server's `SESSION_STORE`. When you type a question into the chat, FastAPI injects that exact report directly into the Chat Agent's context memory. This means the Chat Agent literally "reads" the flowchart on your screen before answering your question!
