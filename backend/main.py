from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from typing import Dict, Any, Optional

from models.triangle import Triangle
from models.methods import METHODS
from recommendation import recommend_method
from agents import ActuarialAgents

app = FastAPI(title="Actuarial Reserving Backend")

# Allow frontend to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    csv_text: str
    api_key: Optional[str] = None

class ExecuteRequest(BaseModel):
    csv_text: str
    method_code: str
    params: Dict[str, Any]
    custom_ldfs: list
    api_key: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    history: list
    context_data: dict
    api_key: Optional[str] = None

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), api_key: str = Form(None)):
    content = await file.read()
    csv_text = content.decode('utf-8')
    
    try:
        t = Triangle.from_csv(csv_text)
        summary = t.get_summary()
        ldfs = t.compute_ldfs()
        
        narration = ""
        if api_key:
            agents = ActuarialAgents(api_key)
            narration = agents.narrate_data_summary(summary)
            
        return {
            "success": True,
            "summary": summary,
            "triangle": {
                "accidentYears": t.accident_years,
                "devAges": t.dev_ages,
                "matrix": t.matrix,
                "ldfs": ldfs
            },
            "csv_text": csv_text,
            "narration": narration
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/analyze")
async def analyze_data(req: AnalyzeRequest):
    try:
        t = Triangle.from_csv(req.csv_text)
        summary = t.get_summary()
        
        rec = recommend_method(summary)
        
        narration = ""
        if req.api_key:
            agents = ActuarialAgents(req.api_key)
            narration = agents.narrate_analysis(rec, summary)
            
        return {
            "success": True,
            "recommendation": rec,
            "narration": narration
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/execute")
async def execute_model(req: ExecuteRequest):
    try:
        t = Triangle.from_csv(req.csv_text)
        
        MethodClass = METHODS.get(req.method_code)
        if not MethodClass:
            return {"success": False, "error": "Invalid method code"}
            
        # Insert UI premiums if provided via params
        if 'premiums' in req.params:
            for ay_str, prem in req.params['premiums'].items():
                t.premiums[int(ay_str)] = float(prem)
                
        model = MethodClass()
        model.fit(t, req.params, req.custom_ldfs)
        
        results = model.get_results()
        total_ibnr = model.get_total_ibnr()
        total_ult = model.get_total_ultimate()
        diag = t.get_latest_diagonal()
        total_paid = sum(v for v in diag if v is not None)
        
        narration = ""
        if req.api_key:
            agents = ActuarialAgents(req.api_key)
            exec_data = {
                "method": MethodClass.label,
                "totalIBNR": total_ibnr,
                "totalUlt": total_ult,
                "totalPaid": total_paid,
                "params": req.params
            }
            narration = agents.narrate_execution(exec_data)
            
        return {
            "success": True,
            "results": results,
            "totalIBNR": total_ibnr,
            "totalUlt": total_ult,
            "totalPaid": total_paid,
            "narration": narration
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        if not req.api_key:
            return {"success": False, "error": "API key required"}
            
        agents = ActuarialAgents(req.api_key)
        reply = agents.chat(req.message, req.history, req.context_data)
        
        return {"success": True, "reply": reply}
    except Exception as e:
        return {"success": False, "error": str(e)}
