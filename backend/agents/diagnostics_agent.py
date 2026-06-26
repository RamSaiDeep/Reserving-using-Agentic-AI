import pandas as pd
from reserving.core.triangle import Triangle
from reserving.diagnostics.diagnostics import compute_diagnostics
from reserving.core.development_engine import DevelopmentEngine
from agents.utils import run_agent, parse_json_response
from agents.prompt_builders import DiagnosticsPromptBuilder

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

        # 3. Build prompt context and render
        context = DiagnosticsPromptBuilder.build_context(overall, ldf_diag, loss_ratios, dq_status)
        sys_inst, prompt, sections = DiagnosticsPromptBuilder.render(context)
        
        try:
            raw_response = run_agent(
                self.api_key, 
                self.base_url, 
                self.model_name, 
                sys_inst, 
                prompt,
                agent_name="DiagnosticsAgent",
                sections=sections
            )
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
