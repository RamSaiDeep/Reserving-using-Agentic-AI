from reserving.services.reserving_engine import ReservingEngine
from reserving.schemas.reserving import ExecuteRequest
from agents.utils import run_agent, parse_json_response

class ReservingAgent:
    """
    ReservingAgent
    Uses: ReservingEngine
    Responsible for:
      - executing requested reserving methods
      - configuring assumptions
      - validating execution
    """
    def __init__(self, api_key: str = None, base_url: str = None, model_name: str = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

    def execute(self, req: ExecuteRequest) -> dict:
        """Triggers the mathematical execution on the ReservingEngine, then validates and narrates results via LLM."""
        # 1. Run deterministic reserving calculations
        raw_results = ReservingEngine.execute_models(req)
        
        if not raw_results.get("success"):
            return raw_results

        # 2. AI validation and narration of execution
        sys_inst = (
            "You are an expert actuarial reserving validation agent. Analyze the reserving model run "
            "outputs and validate if the execution succeeded under standard actuarial principles. "
            "Provide an explanation of any failures, default configuration choices, or initial check results. "
            "Provide your validation in strict JSON format with the following keys:\n"
            "1. 'validation_summary': a short summary of whether the execution is actuarially valid.\n"
            "2. 'assumptions_configured': explanation of the assumptions used in the runs.\n"
            "3. 'notes': any specific observations or alerts about the execution.\n"
            "Respond ONLY with the raw JSON string. Do not include markdown formatting."
        )
        
        methods_summary = []
        for m in raw_results.get("methods", []):
            methods_summary.append({
                "code": m.get("code"),
                "name": m.get("name"),
                "status": m.get("status"),
                "ultimate": m.get("ultimate", 0.0),
                "ibnr": m.get("ibnr", 0.0),
                "error": m.get("error")
            })

        prompt = (
            f"Execution Results Summary:\n"
            f"Selected Method: {raw_results.get('selected_method')}\n"
            f"Best Estimate Ultimate: {raw_results.get('best_estimate')}\n"
            f"Methods Executed: {methods_summary}\n\n"
            "Validate this execution and describe the assumptions configured."
        )

        try:
            raw_response = run_agent(self.api_key, self.base_url, self.model_name, sys_inst, prompt)
            llm_val = parse_json_response(raw_response)
        except Exception as e:
            llm_val = {
                "validation_summary": "Heuristic: Reserving engine executed calculations successfully.",
                "assumptions_configured": "Heuristic: Standard volume-weighted average LDFs and tail factors were configured.",
                "notes": f"LLM narration bypassed: {str(e)}"
            }

        raw_results["validation"] = llm_val
        return raw_results
