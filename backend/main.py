from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import json
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

from reserving.schemas import MethodConfig, ExecuteRequest

class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None

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
            from models.tools import compute_suggested_elr, compute_mature_accident_years, compute_method_availability
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
        session = agent_workflow.SESSION_STORE.get(req.session_id)
        if not session:
            return {"success": False, "error": "Invalid session_id"}

        session['params'] = req.params
        session['custom_ldfs'] = req.custom_ldfs
        if req.api_key: session['api_key'] = req.api_key
        if req.base_url: session['base_url'] = req.base_url
        if req.model_name: session['model_name'] = req.model_name

        from reserving.methods import METHODS
        from models.tools import (get_environment_sensitivity, compute_ibnr_table,
                                   compute_loss_ratios, suggest_elr,
                                   compute_ldf_stability, compute_tail_factor)

        MethodClass = METHODS.get(req.method_code)
        if not MethodClass:
            return {"success": False, "error": "Invalid method code"}

        if MethodClass.needs_premium and not session['triangle'].premiums:
            error_msg = (f"Data Input Insufficient: The {MethodClass.label} model requires "
                         f"Premium data, which was not found in your dataset. Please choose a different model.")
            session['report'] = error_msg
            return {"success": True, "results": [], "totalIBNR": 0, "totalUlt": 0, "totalPaid": 0, "narration": error_msg}

        import copy
        t_eval = copy.deepcopy(session['triangle'])

        # Determine LDFs and matrix based on Selected Data Source
        data_source = req.data_source or "paid"
        ldfs_to_use = req.custom_ldfs
        
        if data_source == "incurred":
            t_eval.matrix = t_eval.incurred_matrix
            t_eval.data_type = "incurred"
            if req.custom_incurred_ldfs:
                ldfs_to_use = req.custom_incurred_ldfs

        # ── On-Level Premium (if rate changes provided) ───────────────────────
        olf_note = ""
        if req.rate_changes and t_eval.premiums:
            try:
                import pandas as pd
                from models.on_level import OnLevelPremiumCalculator
                prem_data = [{"accident_year": int(ay), "earned_premium": float(p)} for ay, p in t_eval.premiums.items()]
                calc = OnLevelPremiumCalculator(pd.DataFrame(prem_data), pd.DataFrame(req.rate_changes))
                on_level_df = calc.calculate()
                t_eval.premiums = dict(zip(on_level_df["accident_year"], on_level_df["on_level_premium"]))
                olf_note = "Premiums were adjusted to current rate levels using On-Level Factors (OLF) before projection."
            except Exception as e:
                return {"success": False, "error": f"On-Leveling error: {str(e)}"}

        # ── TOOL: Tail Factor (deterministic) ─────────────────────────────────
        tail_result = compute_tail_factor(ldfs_to_use, t_eval)
        chosen_tail   = tail_result["chosen"]
        chosen_reason = tail_result["reason"]
        if ldfs_to_use[-1] == 1.0:
            ldfs_to_use[-1] = chosen_tail
        else:
            chosen_reason = f"User Manual Override ({ldfs_to_use[-1]})"

        # ── Run Model ─────────────────────────────────────────────────────────
        model = MethodClass()
        model.fit(t_eval, req.params, ldfs_to_use)

        diag       = t_eval.get_latest_diagonal()
        total_paid = sum(v for v in diag if v is not None)

        # ── TOOL: IBNR Table (deterministic) ──────────────────────────────────
        ibnr_table = compute_ibnr_table(t_eval, model, ldfs_to_use)

        # ── TOOL: Loss Ratios (deterministic, only if premium) ────────────────
        loss_ratios = compute_loss_ratios(t_eval, ibnr_table) if t_eval.premiums else []

        # ── TOOL: Suggested ELR (deterministic) ───────────────────────────────
        elr_suggestion = suggest_elr(t_eval)

        # ── TOOL: LDF Stability Diagnostics (deterministic) ───────────────────
        ldf_stability  = compute_ldf_stability(t_eval)

        # ── TOOL: Environment Sensitivity (deterministic lookup) ──────────────
        env_sensitivity = get_environment_sensitivity(req.method_code)

        # ── PROCESS descriptions (static strings — no LLM needed) ────────────
        PROCESS_EXPLANATIONS = {
            "CL":  "Chain Ladder projects ultimate claims by multiplying the latest paid diagonal by Cumulative Development Factors (CDFs) derived from historical age-to-age LDFs. IBNR = Ultimate − Paid.",
            "MCL": "Mack Chain Ladder calculates identical ultimates to CL but additionally computes sigma-squared variance for each column, producing standard errors and confidence intervals (75th/95th percentile) around the IBNR estimate.",
            "BF":  "Bornhuetter-Ferguson splits the IBNR into (a) expected unreported claims = Expected Ultimate × (1 − 1/CDF), plus (b) actual paid to date. Expected Ultimate = Premium × A Priori ELR.",
            "CC":  "Cape Cod derives the ELR automatically from actual data: ELR = Σ(Reported Claims) / Σ(Used-Up Premium). Used-Up Premium = Earned Premium × % Reported (1/CDF). IBNR is then computed identically to BF.",
            "BK":  "Benktander iteratively refines the BF estimate: BF Ultimate is fed back as the new A Priori, and IBNR is recomputed. Each iteration shifts credibility from BF toward Chain Ladder proportional to % reported.",
            "CO":  "Case Outstanding method sets IBNR = total case reserves currently held by adjusters. It assumes zero future newly-reported claims. Reserve = Incurred − Paid = Case Reserves.",
            "CLK": "Clark Stochastic fits a continuous growth curve (Log-Logistic or Weibull) to the paid triangle using maximum likelihood. Stabilised CDFs from the curve are applied to project ultimates with a distribution of outcomes.",
            "FS":  "Frequency-Severity Method implements Chapter 11 techniques, projecting ultimate claims count and ultimate average severity separately (or using disposal and frequency rates) to compute reserves."
        }

        # ── Deterministic Report Generation (No Tokens Used) ──────────────────
        inputs_txt = f"Data used: {len(t_eval.accident_years)} accident years, evaluated to {max(t_eval.dev_ages)} months."
        if session['triangle'].premiums:
            inputs_txt += " Premium data was included."
            
        process_txt = PROCESS_EXPLANATIONS.get(req.method_code, "")
        if olf_note:
            process_txt += f" {olf_note}"
            
        output_txt = f"The model projected a Total IBNR of {round(model.get_total_ibnr(), 0):,.0f} and a Total Ultimate of {round(model.get_total_ultimate(), 0):,.0f}."
        
        ldf_txt = "LDFs were mathematically computed. "
        if ldf_stability:
            ldf_txt += f"Overall stability is based on {len(ldf_stability)} development periods. "
            
        impact_txt = "Premium and exposure changes directly scale the A Priori ELR and Expected Ultimates in this model." if session['triangle'].premiums else "No premium or exposure data used in this model."
        if req.method_code in ['CL', 'MCL', 'CO', 'CLK']:
            impact_txt = "This method relies purely on historical development patterns, meaning premium/exposure changes do not impact the projection."

        parsed = {
            "inputs": inputs_txt,
            "process": process_txt,
            "output_text": output_txt,
            "ldf_analysis": ldf_txt,
            "tail_factor_selection": f"Selected tail factor: {chosen_reason}.",
            "impact": impact_txt
        }

        parsed["environment_sensitivity"] = env_sensitivity
        parsed["output_numbers"] = {"Total IBNR": round(model.get_total_ibnr(), 0), "Total Ultimate": round(model.get_total_ultimate(), 0)}
        parsed["loss_ratios"] = loss_ratios
        parsed["suggested_elr"] = elr_suggestion

        final_msg = json.dumps(parsed)
        session['report'] = final_msg

        # ── Store results & Standardize ───────────────────────────────────────
        cdfs_curve = t_eval.compute_cdfs(req.custom_ldfs)
        
        from models.standardizer import standardize_method_output
        std_out = standardize_method_output(
            code=req.method_code,
            label=MethodClass.label,
            source_val=data_source,
            t_eval=t_eval,
            model=model,
            configs={req.method_code: req}
        )

        session['results'] = std_out['results']
        session['total_ultimate'] = std_out['ultimate']
        session['total_ibnr'] = std_out['ibnr']
        session['volatility'] = getattr(model, 'volatility', None)
        session['cdfs']      = cdfs_curve
        session['ldfs']      = req.custom_ldfs
        session['dev_ages']  = t_eval.dev_ages
        session['totalIBNR'] = std_out['ibnr']
        session['totalUlt']  = std_out['ultimate']
        
        # Store diagnostics for Analysis Agent
        session['loss_ratios'] = loss_ratios
        session['suggested_elr'] = elr_suggestion
        session['ldf_stability'] = ldf_stability
        session['volatility'] = getattr(model, 'volatility', 0)
        session['ratio_triangles'] = getattr(model, 'ratio_triangles', None) # If available
        session['curve_fitting_results'] = getattr(model, 'curve_fitting_results', None) # If available

        return {
            "success":   True,
            "results":   std_out['results'],
            "totalIBNR": std_out['ibnr'],
            "totalUlt":  std_out['ultimate'],
            "totalPaid": std_out['paid'],
            "narration": final_msg,
            "cdfs":      cdfs_curve,
            "ldfs":      req.custom_ldfs,
            "dev_ages":  t_eval.dev_ages,
            "loss_ratios":   loss_ratios,
            "suggested_elr": elr_suggestion,
            "ldf_stability": ldf_stability,
            "volatility":    session.get('volatility', 0),
            **std_out
        }
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

@app.post("/api/execute_all")
async def execute_all_models(req: ExecuteRequest):
    try:
        from reserving.services import ReservingEngine
        return ReservingEngine.execute_models(req)
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
        from models.tools import compute_suggested_elr, compute_mature_accident_years
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
        
        try:
            from models.diagnostics import compute_diagnostics
            diag_metrics = compute_diagnostics(triangle)
        except Exception:
            diag_metrics = {}

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
            "selected_ldfs": session.get('ldfs'),
            "total_ibnr_selected": session.get('totalIBNR'),
            "total_ultimate_selected": session.get('totalUlt'),
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
