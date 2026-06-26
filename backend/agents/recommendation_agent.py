from agents.utils import run_agent, parse_json_response
from reserving.diagnostics.trace_generator import generate_decision_trace
from agents.prompt_builders import RecommendationPromptBuilder

class RecommendationAgent:
    """
    RecommendationAgent
    Consumes: diagnostics, suitability scores, reserving results, comparison results
    Produces:
      - recommended reserving method (e.g., CL, MCL, BF, CC, BK, CLK, CO, ELR)
      - confidence score ('High', 'Medium', 'Low')
      - reasoning (qualitative justification)
      - assumptions used
      - cautions
      - alternative methods
      - decision_trace (generated deterministically from diagnostics)
    """
    def __init__(self, api_key: str = None, base_url: str = None, model_name: str = None):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

    def recommend(self, diagnostics: dict, reserving_results: dict, comparison_results: dict) -> dict:
        """Determines the recommended reserving method based on diagnostics and comparisons, returning a structured recommendation."""
        metrics = diagnostics.get('metrics', {})
        suitability = metrics.get('suitability', {})
        suitability_scores = suitability.get('scores', {})
        
        # Build prompt context and render (separating construction and template rendering)
        context = RecommendationPromptBuilder.build_context(
            suitability=suitability,
            reporting_pattern=metrics.get('reporting_pattern', {}),
            ldf_stability=metrics.get('ldf_stability', {}),
            calendar_effects=metrics.get('calendar_effects', {}),
            tail_analysis=metrics.get('tail_analysis', {}),
            outliers=metrics.get('outliers', {}),
            comparison_table=comparison_results.get('comparison_table', []),
            differences=comparison_results.get('differences', {})
        )
        sys_inst, prompt, sections = RecommendationPromptBuilder.render(context)

        try:
            raw_response = run_agent(
                self.api_key, 
                self.base_url, 
                self.model_name, 
                sys_inst, 
                prompt,
                agent_name="RecommendationAgent",
                sections=sections
            )
            recommendation = parse_json_response(raw_response)
        except Exception as e:
            # Fallback recommendation based on highest suitability score
            best_method = "CL"
            if suitability_scores:
                best_method = max(suitability_scores, key=suitability_scores.get)
                
            recommendation = {
                "recommended_method": best_method,
                "confidence": "Medium",
                "reasoning": [
                    "Deterministic fallback recommendation based on suitability scores.",
                    f"Error parsing LLM recommendation: {str(e)}"
                ],
                "assumptions_used": "Volume weighted LDF averages.",
                "cautions": ["LLM recommendation failed, fell back to highest deterministic score."],
                "alternative_methods": ["BF", "BK"] if best_method == "CL" else ["CL"]
            }

        # Generate the decision trace deterministically from diagnostics
        selected_method = recommendation.get("recommended_method", "CL")
        trace = generate_decision_trace(metrics, selected_method)
        recommendation["decision_trace"] = trace

        return recommendation
