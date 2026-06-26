def create_execution_plan(parsed_req: dict) -> dict:
    """
    Creates a declarative execution plan from the parsed request details.
    Maps what stages and calculations are required.
    """
    intent = parsed_req["intent"]
    
    # Determine stage dependencies
    need_dataset = intent in ["DATASET_QUERY", "CALCULATION_QUERY", "RECOMMENDATION_QUERY"]
    need_results = intent in ["CALCULATION_QUERY", "RECOMMENDATION_QUERY"]
    need_recommendation = intent == "RECOMMENDATION_QUERY"
    
    # If the user asks for comparison or recommendation, we definitely need results and recommendation stages
    if parsed_req["comparison"] or parsed_req["recommendation"]:
        need_results = True
        need_recommendation = True
        
    return {
        "intent": intent,
        "methods_required": parsed_req["methods"],
        "basis": parsed_req["basis"],
        "explicit_all": parsed_req.get("explicit_all", False),
        "need_dataset": need_dataset,
        "need_results": need_results,
        "need_recommendation": need_recommendation,
        "need_llm_explanation": intent not in ["OUT_OF_SCOPE"]
    }
