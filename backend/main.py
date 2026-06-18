from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from typing import Dict, Any, Optional

import agent_workflow

app = FastAPI(title="Agentic Actuarial Reserving Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExecuteRequest(BaseModel):
    session_id: str
    method_code: str
    params: Dict[str, Any]
    custom_ldfs: list
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None

class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None

from fastapi.responses import StreamingResponse

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...), 
    api_key: str = Form(None),
    base_url: str = Form(None),
    model_name: str = Form(None),
    n_years: int = Form(5)
):
    content = await file.read()
    csv_text = content.decode('utf-8')
    
    try:
        # Step 1: Create session
        session_id = agent_workflow.create_session(csv_text, n_years, api_key, base_url, model_name)
        
        # Step 2: Execute Sequential Pipeline Generator
        return StreamingResponse(
            agent_workflow.execute_sequential_pipeline(session_id),
            media_type="text/event-stream"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.post("/api/execute")
async def execute_model(req: ExecuteRequest):
    try:
        session = agent_workflow.SESSION_STORE.get(req.session_id)
        if not session:
            return {"success": False, "error": "Invalid session_id"}
            
        session['params'] = req.params
        session['custom_ldfs'] = req.custom_ldfs # if we want to override ldfs
        
        # 1. Deterministically execute the model to get the exact data for the frontend
        from models.methods import METHODS
        MethodClass = METHODS.get(req.method_code)
        
        # Check if the model requires premium and we don't have it
        if MethodClass.needs_premium and not session['triangle'].premiums:
            error_msg = f"Data Input Insufficient: The {MethodClass.label} model requires Premium data, which was not found in your dataset. Please choose a different model."
            session['report'] = error_msg
            return {
                "success": True,
                "results": [],
                "totalIBNR": 0,
                "totalUlt": 0,
                "totalPaid": 0,
                "narration": error_msg
            }
            
        model = MethodClass()
        model.fit(session['triangle'], req.params, req.custom_ldfs)
        
        diag = session['triangle'].get_latest_diagonal()
        total_paid = sum(v for v in diag if v is not None)
        
        # 2. Agent 6: Execution Agent generates the detailed calculation report
        PROCESS_EXPLANATIONS = {
            "CL": "The Chain Ladder (CL) method is the most fundamental reserving technique. It operates under the assumption that historical loss development patterns will remain stable and repeat in the future. The process begins by calculating Age-to-Age factors (LDFs) from the historical cumulative paid triangle. These individual factors are then multiplied together to calculate Cumulative Development Factors (CDFs) to Ultimate. Finally, the most recent diagonal (the latest paid losses for each accident year) is multiplied by the corresponding CDF to project the Total Ultimate loss. IBNR is simply calculated by subtracting the paid losses from the Ultimate.",
            "MCL": "The Mack Chain Ladder (MCL) method is a stochastic expansion of the basic Chain Ladder. While it calculates the exact same Ultimate and IBNR as the deterministic Chain Ladder, its true value lies in quantifying uncertainty. The process involves calculating the 'Sigma Squared' variance for every historical data point to measure volatility. It then applies this variance mathematically across the projected ultimate losses to calculate standard errors. This allows the model to output confidence intervals (such as the 75th and 95th percentiles), providing a statistical range of where the true IBNR is likely to fall.",
            "BF": "The Bornhuetter-Ferguson (BF) method is designed to stabilize reserve estimates for highly immature accident years where pure Chain Ladder estimates would be extremely volatile. Instead of relying solely on paid losses multiplied by huge development factors, the BF method calculates an 'Expected Ultimate' by multiplying the total Premium volume by a user-supplied A Priori Expected Loss Ratio (ELR). The process then calculates the percentage of claims that are mathematically 'unreported' (1.0 - 1.0/CDF). The IBNR is established by multiplying the Expected Ultimate by this unreported percentage. This grounds the estimate in a logical expectation rather than pure historical extrapolation.",
            "CC": "The Cape Cod (Stanard-Bühlmann) method is an enhancement of the Bornhuetter-Ferguson method. In the BF method, the actuary must manually guess the 'A Priori' Expected Loss Ratio (ELR) for each year. Cape Cod eliminates this guesswork by mathematically deriving a single, perfectly volume-weighted 'Overall ELR' from the entire historical dataset. It calculates the 'Used Premium' and 'Used Ultimate' across all years to find the true historical average loss ratio. Once this Overall ELR is calculated, it applies the exact same methodology as the BF method to calculate the final IBNR.",
            "BK": "The Benktander (BK) method is an iterative, credibility-weighted compromise between the Chain Ladder and Bornhuetter-Ferguson methods. It is mathematically designed to be more responsive than BF but more stable than Chain Ladder. The process begins by calculating an initial Bornhuetter-Ferguson Ultimate. It then feeds that BF Ultimate back into the equation as the new 'A Priori' expected target, and recalculates the IBNR. This iterative loop is repeated based on the 'Iterations (c)' parameter. The mathematical result is a perfectly weighted blend: it heavily trusts the BF method for very 'young' immature years, while shifting weight towards the Chain Ladder method for older, mature years.",
            "CO": "The Case Outstanding (CO) method is the most simplistic deterministic reserving approach. It completely ignores historical development patterns, CDFs, and any projection of future 'Incurred But Not Reported' (IBNR) claims. The process simply looks at the total 'Incurred Losses' (which is the sum of Paid Losses plus manually estimated Case Reserves currently sitting in the adjuster's file) and subtracts the Paid Losses. The resulting reserve is strictly equal to the known Case Reserves, assuming zero future development or newly reported claims.",
            "CLK": "The Clark Stochastic model (CLK) departs from discrete Age-to-Age jumps and instead fits a continuous mathematical growth curve (such as Log-Logistic or Weibull) to the loss data. This process is particularly useful for smoothing out volatile data or for very long-tail lines of business. By fitting a continuous curve to the cumulative development, the model calculates highly stabilized continuous CDFs, which are then applied to the current paid losses to project the Ultimate. This continuous smoothing drastically reduces the impact of single-year anomalies in the historical triangle."
        }
        
        sys_inst = """You are the Actuarial Execution Agent. You MUST return a pure JSON object (no markdown formatting, no code blocks) with EXACTLY the following keys:
{
  "inputs": "List the required inputs, e.g. Premium, CDFs, and specific parameters used.",
  "process": "You MUST copy and paste the 'DETAILED_PROCESS_EXPLANATION' exactly word-for-word from the prompt into this field.",
  "output_text": "A brief sentence summarizing the output.",
  "output_numbers": {"Total IBNR": <number>, "Total Ultimate": <number>},
  "impact": "Analyze how changing premium or exposure volume would impact the calculation based on this model."
}
Do not include anything else in your response. Only the JSON object.
"""
        
        # Give the agent a sneak peek at the exact results so it can write a truthful report
        sneak_peek = {
            "Method": req.method_code,
            "Total IBNR": model.get_total_ibnr(),
            "Total Ultimate": model.get_total_ultimate(),
            "Parameters Used": req.params,
            "Has Premium Data": bool(session['triangle'].premiums),
            "DETAILED_PROCESS_EXPLANATION": PROCESS_EXPLANATIONS.get(req.method_code, "Standard actuarial process.")
        }
        prompt = f"Please write the 4-part calculation report. Here are the exact mathematical outputs of the execution: {json.dumps(sneak_peek)}"
        
        msg = agent_workflow.run_agent(req.api_key, req.base_url, req.model_name, sys_inst, prompt, [])
        session['report'] = msg  # Save report for the parallel chat agent
        
        return {
            "success": True,
            "results": model.get_results(),
            "totalIBNR": model.get_total_ibnr(),
            "totalUlt": model.get_total_ultimate(),
            "totalPaid": total_paid,
            "narration": msg
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        if not req.api_key:
            return {"success": False, "error": "API key required"}
            
        reply = agent_workflow.run_parallel_chat(req.session_id, req.message, req.history)
        
        return {"success": True, "reply": reply}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Native HTML Hosting
import os
from fastapi.staticfiles import StaticFiles
dashboard_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard"))
app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="dashboard")
