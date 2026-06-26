import datetime
from agents.utils import run_agent
from agents.prompt_builders import ReportingPromptBuilder

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
        """Compiles a comprehensive actuarial report in markdown format using structured prompt builder."""
        
        # Build prompt context and render (separating construction and template rendering)
        context = ReportingPromptBuilder.build_context(
            diagnostics_summary=diagnostics,
            reserving_outputs=reserving_results,
            comparison_table=comparison_results.get("comparison_table", []),
            differences=comparison_results.get("differences", {}),
            comparison_explanation=comparison_results.get("explanation", ""),
            recommendation=recommendation
        )
        sys_inst, prompt, sections = ReportingPromptBuilder.render(context)

        try:
            report_md = run_agent(
                self.api_key, 
                self.base_url, 
                self.model_name, 
                sys_inst, 
                prompt,
                agent_name="ReportingAgent",
                sections=sections
            )
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
