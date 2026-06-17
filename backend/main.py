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

class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list
    api_key: Optional[str] = None

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...), 
    api_key: str = Form(None),
    n_years: int = Form(5)
):
    content = await file.read()
    csv_text = content.decode('utf-8')
    
    try:
        # Step 1: Create session
        session_id = agent_workflow.create_session(csv_text, n_years, api_key)
        
        # Step 2: Execute Sequential Pipeline
        narratives, summary, triangle, ldfs = agent_workflow.execute_sequential_pipeline(session_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "summary": summary,
            "triangle": {
                "accidentYears": triangle.accident_years,
                "devAges": triangle.dev_ages,
                "matrix": triangle.matrix,
                "ldfs": ldfs
            },
            "narratives": narratives
        }
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
        
        # Agent 6: Execution Agent
        sys_inst = "You are the Execution Agent. You MUST call `run_actuarial_model`. Then narrate the result."
        prompt = f"Session: {req.session_id}, Method: {req.method_code}"
        
        msg = agent_workflow.run_agent(req.api_key, sys_inst, prompt, [agent_workflow.run_actuarial_model])
        
        results = session.get('results', {})
        # Note: to get the actual array of results, we need the model's get_results() array.
        # Let's quickly pull it from the triangle mathematically or modify the tool to save it.
        # Actually, since the LLM ran it, we can re-run it deterministically to get the array for the frontend UI.
        from models.methods import METHODS
        MethodClass = METHODS.get(req.method_code)
        model = MethodClass()
        model.fit(session['triangle'], req.params, req.custom_ldfs)
        
        diag = session['triangle'].get_latest_diagonal()
        total_paid = sum(v for v in diag if v is not None)
        
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
