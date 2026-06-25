import datetime
from agents.utils import run_agent

class ReportingAgent:
    """
    ReportingAgent
    Generates:
      - executive summary
      - actuarial report
      - assumption summary
      - diagnostics summary
      - recommendation summary
    Output should be suitable for PDF generation later.
    """
    def __init__(self, api_key: str = None, base_url: str = None, model_name: str = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

    def generate_report(self, diagnostics: dict, reserving_results: dict, comparison_results: dict, recommendation: dict) -> dict:
        """Compiles a comprehensive actuarial report in markdown format."""
        sys_inst = (
            "You are an expert actuarial reporting agent. Your task is to compile a formal, professional "
            "actuarial report in Markdown format. The report should be comprehensive and suitable for PDF generation later. "
            "Your output must contain these five distinct sections:\n"
            "1. Executive Summary\n"
            "2. Actuarial Report (Methodology, indications, and differences explanation)\n"
            "3. Assumption Summary (tail factors, LDFs, ELR, and negative IBNR configurations)\n"
            "4. Diagnostics Summary (data quality, outliers, stability, maturity)\n"
            "5. Recommendation Summary (method, confidence, reasoning, cautions, and alternatives)\n\n"
            "Use formal professional actuarial language. Do not invent calculations. Represent all figures cleanly."
        )

        prompt = (
            f"Diagnostics: {diagnostics}\n"
            f"Reserving Results: {reserving_results}\n"
            f"Comparison: {comparison_results}\n"
            f"Recommendation: {recommendation}\n\n"
            "Compile the complete Markdown actuarial report."
        )

        try:
            report_md = run_agent(self.api_key, self.base_url, self.model_name, sys_inst, prompt)
        except Exception as e:
            report_md = (
                f"# Actuarial Reserving Report (Bypass)\n\n"
                f"## Executive Summary\n"
                f"Calculations completed successfully. Recommended Method: {recommendation.get('recommended_method')}.\n\n"
                f"## Diagnostics Summary\n"
                f"Maturity and quality tests run. Detail: {str(e)}\n"
            )

        return {
            "report_markdown": report_md,
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
