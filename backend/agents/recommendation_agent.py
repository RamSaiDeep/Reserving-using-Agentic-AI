from agents.utils import run_agent, parse_json_response
from reserving.diagnostics.trace_generator import generate_decision_trace

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
        
        sys_inst = (
            "You are an expert actuarial AI Reserving Recommender. You analyze loss reserving outputs "
            "across multiple methods along with data diagnostics, comparison results, and deterministic method suitability scores. "
            "Your task is to recommend the most appropriate reserving method for the best estimate. "
            "Your recommendation must align with the deterministic suitability scores provided (higher is better). "
            "Explain the recommendation qualitatively using the diagnostics; do not invent actuarial reasoning. "
            "Provide your recommendation in strict JSON format containing these fields:\n"
            "1. 'recommended_method': The code of the method (e.g. 'BK', 'BF', 'CL', 'MCL', 'CC', 'CLK', 'CO', 'ELR')\n"
            "2. 'confidence': The confidence level ('High', 'Medium', 'Low')\n"
            "3. 'reasoning': An array of strings explaining the selection qualitatively based on diagnostics. Do not exceed 4 reasons.\n"
            "4. 'assumptions_used': summary of assumptions used (e.g. volume-weighted LDFs, tail factor, ELR).\n"
            "5. 'cautions': array of strings with any warnings or cautions from the diagnostic checks.\n"
            "6. 'alternative_methods': array of alternative methods that were highly scored but not selected.\n"
            "Respond ONLY with the raw JSON string. Do not include markdown code block formatting."
        )

        prompt = (
            f"Deterministic Method Suitability Scores (out of 100): {suitability_scores}\n"
            f"Method Pros: {suitability.get('pros')}\n"
            f"Method Cons: {suitability.get('cons')}\n"
            f"Reporting Pattern Diagnostics: {metrics.get('reporting_pattern')}\n"
            f"LDF Stability Analysis: {metrics.get('ldf_stability')}\n"
            f"Calendar Year Effects: {metrics.get('calendar_effects')}\n"
            f"Tail Factor Diagnostics: {metrics.get('tail_analysis')}\n"
            f"Outliers: {metrics.get('outliers')}\n"
            f"Reserving Indications (results summary): {comparison_results.get('comparison_table')}\n"
            f"Reserving Differences: {comparison_results.get('differences')}\n"
            f"Comparison Explanation: {comparison_results.get('explanation')}\n\n"
            "Recommend the best method and return the JSON payload. Ensure the recommended method is one of the available codes (e.g. CL, MCL, BF, CC, BK, CLK, CO, ELR)."
        )

        try:
            raw_response = run_agent(self.api_key, self.base_url, self.model_name, sys_inst, prompt)
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
