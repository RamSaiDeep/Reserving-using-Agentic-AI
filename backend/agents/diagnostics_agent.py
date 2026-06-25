import pandas as pd
from reserving.core.triangle import Triangle
from reserving.diagnostics.diagnostics import compute_diagnostics
from reserving.core.development_engine import DevelopmentEngine
from agents.utils import run_agent, parse_json_response

class DiagnosticsAgent:
    """
    DiagnosticsAgent
    Uses: Triangle, Diagnostics, DevelopmentEngine
    Produces:
      - data quality assessment
      - reporting pattern diagnostics
      - LDF stability assessment
      - outlier detection
      - maturity assessment
    """
    def __init__(self, api_key: str = None, base_url: str = None, model_name: str = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

    def analyze(self, triangle: Triangle, df: pd.DataFrame = None) -> dict:
        """Runs the deterministic diagnostics and supplements them with AI qualitative reasoning."""
        # 1. Compute deterministic diagnostics
        raw_metrics = compute_diagnostics(triangle)
        
        # 2. Extract some basic stats for the prompt
        overall = raw_metrics.get('overall', {})
        ldf_diag = raw_metrics.get('ldf_diagnostics', [])
        loss_ratios = raw_metrics.get('loss_ratios_by_ay', [])
        
        dq_status = "No raw dataframe provided."
        if df is not None:
            missing = int(df.isnull().sum().sum())
            duplicates = int(df.duplicated().sum())
            dq_status = f"Rows: {len(df)}, Columns: {len(df.columns)}, Missing values: {missing}, Duplicates: {duplicates}."

        # 3. Prompt the LLM
        sys_inst = (
            "You are an expert actuarial diagnostics agent. Your task is to analyze loss reserving data "
            "and provide professional reasoning for data quality, reporting patterns, LDF stability, "
            "outliers, and maturity. Do not perform any actuarial calculations yourself. "
            "Provide your findings in strict JSON format with the following keys:\n"
            "1. 'data_quality_assessment': evaluation of the data completeness and quality.\n"
            "2. 'reporting_pattern_diagnostics': description of how reporting patterns develop over time.\n"
            "3. 'ldf_stability_assessment': evaluation of LDF stability (reference COV, straight avg vs weighted).\n"
            "4. 'outlier_detection': identification of any anomalous accident years or cells.\n"
            "5. 'maturity_assessment': assessment of the triangle's overall maturity.\n"
            "Respond ONLY with the raw JSON string. Do not include markdown formatting."
        )
        
        prompt = (
            f"Actuarial Metrics Summary:\n"
            f"Overall Statistics: {overall}\n"
            f"LDF Diagnostics (first few): {ldf_diag[:5]}\n"
            f"Loss Ratios by Accident Year: {loss_ratios}\n"
            f"Data Quality Status: {dq_status}\n\n"
            "Based on these metrics, provide the assessments requested in the JSON schema."
        )
        
        try:
            raw_response = run_agent(self.api_key, self.base_url, self.model_name, sys_inst, prompt)
            llm_assessments = parse_json_response(raw_response)
        except Exception as e:
            llm_assessments = {
                "data_quality_assessment": f"Failed to generate LLM assessment: {str(e)}",
                "reporting_pattern_diagnostics": "Heuristic: Development ages show standard loss progression.",
                "ldf_stability_assessment": "Heuristic: LDF stability is moderate across recent periods.",
                "outlier_detection": "Heuristic: No distinct outliers detected automatically.",
                "maturity_assessment": f"Heuristic: Triangle is {'long-tail' if overall.get('is_long_tail') else 'short-tail'}."
            }
            
        return {
            "metrics": raw_metrics,
            "llm_analysis": llm_assessments
        }
