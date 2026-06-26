import numpy as np
from agents.utils import run_agent, parse_json_response
from agents.prompt_builders import ComparisonPromptBuilder

class ComparisonAgent:
    """
    ComparisonAgent
    Consumes outputs from multiple methods.
    Produces:
      - comparison tables
      - reserve differences
      - ultimate differences
      - IBNR comparison
      - explanation of why methods differ
    """
    def __init__(self, api_key: str = None, base_url: str = None, model_name: str = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

    def compare(self, methods_results: list) -> dict:
        """Compares reserving output metrics side-by-side and calls LLM to explain differences."""
        success_runs = [m for m in methods_results if m.get("status") == "success"]
        if not success_runs:
            return {
                "comparison_table": [],
                "differences": {},
                "explanation": "No successful model runs to compare."
            }

        # 1. Construct comparison tables (deterministic)
        comparison_table = []
        for m in success_runs:
            comparison_table.append({
                "code": m.get("code"),
                "name": m.get("name"),
                "ultimate": m.get("ultimate"),
                "ibnr": m.get("ibnr"),
                "loss_ratio": m.get("loss_ratio", 0.0),
                "reserve": m.get("reserve", 0.0),
                "paid": m.get("paid", 0.0)
            })

        # Calculate differences relative to median
        images = None
        ultimates = [c["ultimate"] for c in comparison_table if c["ultimate"] is not None]
        median_ultimate = float(np.median(ultimates)) if ultimates else 0.0
        
        ibnrs = [c["ibnr"] for c in comparison_table if c["ibnr"] is not None]
        median_ibnr = float(np.median(ibnrs)) if ibnrs else 0.0

        differences = {}
        for c in comparison_table:
            code = c["code"]
            res_diff = c["reserve"] - (c["ultimate"] - c["paid"]) if c["ultimate"] is not None and c["paid"] is not None else 0.0
            ult_diff = c["ultimate"] - median_ultimate if c["ultimate"] is not None else 0.0
            ibnr_diff = c["ibnr"] - median_ibnr if c["ibnr"] is not None else 0.0
            differences[code] = {
                "ultimate_diff_vs_median": ult_diff,
                "ultimate_pct_diff_vs_median": (ult_diff / median_ultimate * 100) if median_ultimate > 0 else 0.0,
                "ibnr_diff_vs_median": ibnr_diff,
                "ibnr_pct_diff_vs_median": (ibnr_diff / median_ibnr * 100) if median_ibnr > 0 else 0.0,
            }

        # 2. Use LLM to explain why the methods differ (separated context and rendering)
        context = ComparisonPromptBuilder.build_context(median_ultimate, median_ibnr, comparison_table, differences)
        sys_inst, prompt, sections = ComparisonPromptBuilder.render(context)

        try:
            explanation = run_agent(
                self.api_key, 
                self.base_url, 
                self.model_name, 
                sys_inst, 
                prompt,
                agent_name="ComparisonAgent",
                sections=sections
            )
        except Exception as e:
            explanation = f"Failed to generate LLM comparison explanation: {str(e)}"

        return {
            "comparison_table": comparison_table,
            "differences": differences,
            "median_ultimate": median_ultimate,
            "median_ibnr": median_ibnr,
            "explanation": explanation
        }
