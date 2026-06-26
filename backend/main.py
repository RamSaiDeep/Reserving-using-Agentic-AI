from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import json
import os
from typing import Dict, Any, Optional, List, Literal

import agent_workflow

app = FastAPI(title="Agentic Actuarial Reserving Backend")

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "healthy", "message": "Agentic Actuarial Reserving Backend is running"}

from reserving.schemas import MethodConfig, ExecuteRequest, RecommendationRequest

class ChatRequest(BaseModel):
    session_id: str
    user_text: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None

class OverrideRequest(BaseModel):
    session_id: str
    category: str
    rule: str
    rationale: str

class ResumePipelineRequest(BaseModel):
    session_id: str
    conditions: Optional[Dict[str, bool]] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None

class UpdateMappingsRequest(BaseModel):
    session_id: str
    reserving_roles: Dict[str, Optional[str]]
    selected_entities: Optional[list] = None

class RecalculateSuggestionsRequest(BaseModel):
    session_id: str
    mature_cdf_threshold: float

from fastapi.responses import StreamingResponse

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...), 
    api_key: str = Form(None),
    base_url: str = Form(None),
    model_name: str = Form(None),
    n_years: int = Form(5),
    valuation_year: int = Form(None),
    rate_changes_json: str = Form(None),
    business_context: str = Form(None)
):
    # Enforce AI settings availability
    has_api_key = bool(api_key or os.environ.get("LLM_API_KEY"))
    has_model_name = bool(model_name or os.environ.get("LLM_MODEL_NAME"))
    if not has_api_key or not has_model_name:
        async def error_stream():
            yield json.dumps({
                "type": "agent", 
                "agent": "Analysis Agent", 
                "text": "AI settings are missing or incomplete. Please configure your LLM API Key and Model Name in the Settings panel (at the top of the page) to enable the agentic reserving workflows."
            }) + "\n"
            yield json.dumps({
                "type": "complete", 
                "session_id": "", 
                "summary": None, 
                "triangle": None, 
                "recommendation": None
            }) + "\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    content = await file.read()
    csv_text = content.decode('utf-8')
    
    rate_changes = None
    if rate_changes_json:
        try:
            rate_changes = json.loads(rate_changes_json)
        except:
            pass
            
    try:
        session_id = agent_workflow.create_session(csv_text, n_years, valuation_year, api_key, base_url, model_name, business_context)
        
        return StreamingResponse(
            agent_workflow.execute_sequential_pipeline_part1(session_id, rate_changes),
            media_type="text/event-stream"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.post("/api/resume_pipeline")
async def resume_pipeline(req: ResumePipelineRequest):
    session = agent_workflow.SESSION_STORE.get(req.session_id)
    if session:
        if req.api_key: session['api_key'] = req.api_key
        if req.base_url: session['base_url'] = req.base_url
        if req.model_name: session['model_name'] = req.model_name

    # Enforce AI settings availability
    api_key = req.api_key or (session.get('api_key') if session else None)
    model_name = req.model_name or (session.get('model_name') if session else None)
    has_api_key = bool(api_key or os.environ.get("LLM_API_KEY"))
    has_model_name = bool(model_name or os.environ.get("LLM_MODEL_NAME"))
    
    if not has_api_key or not has_model_name:
        async def error_stream():
            yield json.dumps({
                "type": "agent", 
                "agent": "Analysis Agent", 
                "text": "AI settings are missing or incomplete. Please configure your LLM API Key and Model Name in the Settings panel."
            }) + "\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    return StreamingResponse(
        agent_workflow.execute_sequential_pipeline_part2(req.session_id, req.conditions),
        media_type="text/event-stream"
    )

@app.post("/api/update_mappings")
async def update_mappings(req: UpdateMappingsRequest):
    try:
        session = agent_workflow.SESSION_STORE.get(req.session_id)
        if not session:
            return {"success": False, "error": "Invalid session_id"}
        session['selected_entities'] = req.selected_entities
        
        # Update mappings in inspection results
        inspection = session.get('inspection')
        if inspection:
            for k, v in req.reserving_roles.items():
                inspection.reserving_roles[k] = v
        else:
            from reserving.ingestion.inspector import InspectionResult, EntityCheckResult
            session['inspection'] = InspectionResult(
                columns=[],
                entity_check=EntityCheckResult(is_multi_entity=False, entity_column=None, entity_count=0, reasons=[]),
                row_count=len(session['df']),
                column_count=len(session['df'].columns),
                reserving_roles=req.reserving_roles
            )

        # Re-build the triangle
        t_msg = agent_workflow.build_loss_triangle(req.session_id)
        if t_msg.startswith("Failed"):
            return {"success": False, "error": t_msg}

        # Re-calculate LDFs
        ldf_msg = agent_workflow.calculate_ldfs(req.session_id)
        if ldf_msg.startswith("Failed"):
            return {"success": False, "error": ldf_msg}

        # Format and return new triangle and summary
        triangle = session.get('triangle')
        triangle_data = None
        if triangle:
            from reserving.core.tools import compute_suggested_elr, compute_mature_accident_years, compute_method_availability
            mature_info = compute_mature_accident_years(triangle)
            triangle_data = {
                "accidentYears": triangle.accident_years,
                "devAges": triangle.dev_ages,
                "matrix": triangle.matrix,
                "incurred_matrix": triangle.incurred_matrix,
                "ldfs": session.get('ldfs'),
                "incurred_ldfs": session.get('incurred_ldfs'),
                "hasPremium": bool(triangle.premiums),
                "suggested_elr_paid": compute_suggested_elr(triangle, "paid"),
                "suggested_elr_incurred": compute_suggested_elr(triangle, "incurred"),
                "suggested_mature_years": mature_info.get("mature_years", []),
                "mature_reasoning": mature_info.get("reasoning", {}),
                "method_availability": compute_method_availability(triangle)
            }
            
        return {
            "success": True,
            "summary": session.get('summary'),
            "triangle": triangle_data
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.post("/api/execute")
async def execute_model(req: ExecuteRequest):
    try:
        from reserving.services import ReservingEngine
        result = ReservingEngine.execute_single_model(req)
        
        # Add compliance audit to result if successful
        if result.get("success"):
            session = agent_workflow.SESSION_STORE.get(req.session_id)
            if session and 'compliance_engine' in session:
                ce = session['compliance_engine']
                # Track method execution for compliance
                if 'methods_executed' not in session:
                    session['methods_executed'] = set()
                session['methods_executed'].add(req.method_code)
                ce.run_estimation_checks(list(session['methods_executed']))
                ce.run_selection_checks()
                ce.run_results_checks()
                result["compliance_audit"] = ce.audit_log
        
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        session = agent_workflow.SESSION_STORE.get(req.session_id)
        if session:
            if req.api_key: session['api_key'] = req.api_key
            if req.base_url: session['base_url'] = req.base_url
            if req.model_name: session['model_name'] = req.model_name
            
        # Enforce AI settings availability
        api_key = req.api_key or (session.get('api_key') if session else None)
        model_name = req.model_name or (session.get('model_name') if session else None)
        has_api_key = bool(api_key or os.environ.get("LLM_API_KEY"))
        has_model_name = bool(model_name or os.environ.get("LLM_MODEL_NAME"))
        
        if not has_api_key or not has_model_name:
            return {"success": False, "error": "AI settings are missing or incomplete. Please configure your LLM API Key and Model Name in the Settings panel."}
            
        reply = agent_workflow.run_parallel_chat(req.session_id, req.message, req.history)
        
        return {"success": True, "reply": reply}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/override_compliance")
async def override_compliance(req: OverrideRequest):
    try:
        session = agent_workflow.SESSION_STORE.get(req.session_id)
        if not session or 'compliance_engine' not in session:
            return {"success": False, "error": "Invalid session or compliance engine not found"}
        
        ce = session['compliance_engine']
        found = False
        for r in ce.audit_log.get(req.category, []):
            if r['rule'] == req.rule:
                r['status'] = "OVERRIDDEN_DOCUMENTED"
                r['details'] = f"Override Rationale: {req.rationale} | Original: {r['details']}"
                found = True
                break
        
        if not found:
            return {"success": False, "error": "Rule not found in specified category"}
            
        return {"success": True, "compliance_audit": ce.audit_log}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/execute_all")
async def execute_all_models(req: ExecuteRequest):
    try:
        from reserving.services import ReservingEngine
        return ReservingEngine.execute_models(req)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.post("/api/recommendation")
async def get_recommendation(req: RecommendationRequest):
    try:
        session = None
        session_id = None
        for sid, s in agent_workflow.SESSION_STORE.items():
            if 'executions' in s and req.execution_id in s['executions']:
                session = s
                session_id = sid
                break
                
        if not session:
            for sid, s in agent_workflow.SESSION_STORE.items():
                res = s.get('results')
                if res and res.get('run_id') == req.execution_id:
                    session = s
                    session_id = sid
                    break
                    
        if not session:
            return {"success": False, "error": f"Execution {req.execution_id} not found."}
            
        exec_data = session['executions'].get(req.execution_id) if 'executions' in session else None
        if not exec_data:
            exec_data = session.get('results')
            
        if not exec_data:
            return {"success": False, "error": "Execution results not found."}
            
        if exec_data.get('ai_recommendation') is not None:
            return {
                "success": True,
                "ai_recommendation": exec_data['ai_recommendation'],
                "report_markdown": session.get('report_markdown')
            }
            
        api_key = req.api_key or session.get('api_key') or os.environ.get("LLM_API_KEY")
        base_url = req.base_url or session.get('base_url') or os.environ.get("LLM_BASE_URL")
        model_name = req.model_name or session.get('model_name') or os.environ.get("LLM_MODEL_NAME")
        
        if not api_key or not model_name:
            return {"success": False, "error": "AI settings are missing or incomplete. Please configure your LLM API Key and Model Name in the Settings panel."}
            
        if req.api_key: session['api_key'] = req.api_key
        if req.base_url: session['base_url'] = req.base_url
        if req.model_name: session['model_name'] = req.model_name
        
        methods_out = exec_data.get('methods') or []
        results_summary_for_ai = [
            {
                "code": m["code"],
                "name": m["name"],
                "status": m["status"],
                "ibnr": m.get("ibnr", 0.0),
                "ultimate": m.get("ultimate", 0.0),
                "loss_ratio": m.get("loss_ratio", 0.0),
                "maturity_score": m.get("maturity_score", 0.0),
                "reserve_to_case_ratio": m.get("reserve_to_case_ratio", 0.0)
            } for m in methods_out if m["status"] == "success"
        ]
        
        ai_recommendation = agent_workflow.run_reserve_recommendation_agent(session_id, results_summary_for_ai)
        
        exec_data['ai_recommendation'] = ai_recommendation
        if session.get('results') and session['results'].get('run_id') == req.execution_id:
            session['results']['ai_recommendation'] = ai_recommendation
            
        rec_code = ai_recommendation.get("recommended_method", "CL")
        rec_model_res = next((m for m in methods_out if m.get('code') == rec_code and m.get('status') == 'success'), None)
        if rec_model_res:
            exec_data['best_estimate'] = rec_model_res["ultimate"]
            exec_data['selected_method'] = rec_code
            if session.get('results') and session['results'].get('run_id') == req.execution_id:
                session['results']['best_estimate'] = rec_model_res["ultimate"]
                session['results']['selected_method'] = rec_code
            
            session['totalIBNR'] = rec_model_res.get('ibnr', 0.0)
            session['totalUlt'] = rec_model_res.get('ultimate')
            session['total_ibnr'] = session['totalIBNR']
            session['total_ultimate'] = session['totalUlt']
            
        return {
            "success": True,
            "ai_recommendation": ai_recommendation,
            "report_markdown": session.get('report_markdown')
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.post("/api/recalculate_suggestions")
async def recalculate_suggestions(req: RecalculateSuggestionsRequest):
    try:
        session = agent_workflow.SESSION_STORE.get(req.session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        triangle = session.get('triangle')
        if not triangle:
            return {"success": False, "error": "Triangle not found"}
        from reserving.core.tools import compute_suggested_elr, compute_mature_accident_years
        mature_info = compute_mature_accident_years(triangle, req.mature_cdf_threshold)
        return {
            "success": True,
            "suggested_elr_paid": compute_suggested_elr(triangle, "paid", req.mature_cdf_threshold),
            "suggested_elr_incurred": compute_suggested_elr(triangle, "incurred", req.mature_cdf_threshold),
            "suggested_mature_years": mature_info.get("mature_years", []),
            "mature_reasoning": mature_info.get("reasoning", {})
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/export/{session_id}")
async def export_data(session_id: str):
    try:
        session = agent_workflow.SESSION_STORE.get(session_id)
        if not session: return JSONResponse(status_code=404, content={"error": "Session not found"})
        
        triangle = session.get('triangle')
        if not triangle: return JSONResponse(status_code=400, content={"error": "No triangle data"})
        
        # Determine active data source basis from session
        data_source = session.get('data_source', 'paid')
        
        # Diagnostics should use the explicitly selected matrix without mutating the original Triangle object
        import copy
        t_diag = copy.deepcopy(triangle)
        if data_source == "incurred":
            t_diag.matrix = t_diag.incurred_matrix
            t_diag.data_type = "incurred"
            
        try:
            from reserving.diagnostics import compute_diagnostics
            diag_metrics = compute_diagnostics(t_diag)
        except Exception:
            diag_metrics = {}

        # Export already-computed results stored during execution to guarantee consistency
        results_val = session.get('results') or {}
        active_method = results_val.get('selected_method')
        methods = results_val.get('methods') or []
        method_res = next((m for m in methods if m.get('code') == active_method), None)
        
        # Default fallbacks
        selected_ldfs = session.get('incurred_ldfs' if data_source == "incurred" else 'ldfs')
        total_ibnr_selected = session.get('totalIBNR')
        total_ultimate_selected = session.get('totalUlt')
        
        if method_res:
            total_ibnr_selected = method_res.get('ibnr', total_ibnr_selected)
            total_ultimate_selected = method_res.get('ultimate', total_ultimate_selected)
            if data_source == "incurred":
                selected_ldfs = results_val.get('incurred_ldfs') or selected_ldfs
            else:
                selected_ldfs = results_val.get('paid_ldfs') or selected_ldfs

        export_obj = {
            "currency": "USD",
            "valuation_year": triangle.valuation_year,
            "accident_years": triangle.accident_years,
            "development_ages": triangle.dev_ages,
            "gross_paid_matrix": triangle.matrix,
            "gross_incurred_matrix": triangle.incurred_matrix,
            "gross_outstanding_matrix": getattr(triangle, 'outstanding_matrix', None),
            "closed_claim_counts": getattr(triangle, 'closed_counts_matrix', None),
            "reported_claim_counts": getattr(triangle, 'reported_counts_matrix', None),
            "earned_premiums": triangle.premiums,
            "exposures": triangle.exposures,
            "selected_ldfs": selected_ldfs,
            "total_ibnr_selected": total_ibnr_selected,
            "total_ultimate_selected": total_ultimate_selected,
            "diagnostics": diag_metrics
        }
        
        return JSONResponse(content=export_obj)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Native HTML Hosting
import os
from fastapi.staticfiles import StaticFiles
dashboard_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "out"))
os.makedirs(dashboard_path, exist_ok=True)
app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="dashboard")
