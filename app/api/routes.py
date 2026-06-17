"""FastAPI route definitions for the reserving backend."""

from fastapi import APIRouter, File, Form, UploadFile

from backend.agents import ActuarialAgents
from backend.recommendation import recommend_method
from src.models.request_models import AnalyzeRequest, ChatRequest, ExecuteRequest
from src.services.reserve_service import ReserveService

router = APIRouter(prefix="/api")
reserve_service = ReserveService()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), api_key: str = Form(None)):
    try:
        csv_text = (await file.read()).decode("utf-8")
        output = reserve_service.summarize_upload(csv_text)
        narration = ""
        if api_key:
            narration = ActuarialAgents(api_key).narrate_data_summary(output["summary"])
        return {"success": True, **output, "csv_text": csv_text, "narration": narration}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.post("/analyze")
async def analyze_data(req: AnalyzeRequest):
    try:
        output = reserve_service.summarize_upload(req.csv_text)
        rec = recommend_method(output["summary"])
        narration = ""
        if req.api_key:
            narration = ActuarialAgents(req.api_key).narrate_analysis(rec, output["summary"])
        return {"success": True, "recommendation": rec, "narration": narration}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.post("/execute")
async def execute_model(req: ExecuteRequest):
    try:
        output = reserve_service.execute_method(req.csv_text, req.method_code, req.params, req.custom_ldfs)
        narration = ""
        if req.api_key:
            narration = ActuarialAgents(req.api_key).narrate_execution(
                {
                    "method": output["method"],
                    "totalIBNR": output["totalIBNR"],
                    "totalUlt": output["totalUlt"],
                    "totalPaid": output["totalPaid"],
                    "params": req.params,
                }
            )
        return {"success": True, **output, "narration": narration}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.post("/chat")
async def chat(req: ChatRequest):
    try:
        if not req.api_key:
            return {"success": False, "error": "API key required"}
        reply = ActuarialAgents(req.api_key).chat(req.message, req.history, req.context_data)
        return {"success": True, "reply": reply}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
