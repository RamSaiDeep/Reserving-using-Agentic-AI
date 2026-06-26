import re
from agents.registry import METHOD_ALIASES, CONVERSATIONAL_KEYWORDS

def parse_request(message: str) -> dict:
    """
    Parses the incoming chatbot message deterministically.
    Extracts intent, target reserving methods, data basis, and flags.
    """
    msg_lower = message.lower().strip()
    
    # 1. Extract methods explicitly mentioned (using word boundaries to prevent partial matches)
    methods = []
    for alias in sorted(METHOD_ALIASES.keys(), key=len, reverse=True):
        code = METHOD_ALIASES[alias]
        pattern = r'\b' + re.escape(alias) + r'\b'
        if re.search(pattern, msg_lower):
            if code not in methods:
                methods.append(code)
                
    # 2. Extract data basis (paid or incurred)
    basis = None
    if "incurred" in msg_lower:
        basis = "incurred"
    elif "paid" in msg_lower:
        basis = "paid"
        
    # 3. Detect comparison/recommendation intent indicators
    comparison = "compare" in msg_lower or "comparison" in msg_lower or "differences" in msg_lower or "vs" in msg_lower
    recommendation = (
        "recommend" in msg_lower or "best" in msg_lower or "suitability" in msg_lower or 
        "reason" in msg_lower or "why" in msg_lower or "trust" in msg_lower or "choose" in msg_lower
    )
    
    # Detect if user explicitly requests all methods/models
    explicit_all = any(k in msg_lower for k in [
        "compare all", 
        "run all", 
        "recommend the best", 
        "recommend best", 
        "execute all",
        "all models",
        "all methods"
    ])
    
    # 4. Classify intent deterministically
    intent = "ACTUARIAL_KNOWLEDGE" # default fallback for actuarial topics
    
    # Check conversational / greeting intent
    words = set(msg_lower.replace("?", "").replace("!", "").replace(".", "").split())
    is_greeting = bool(words & CONVERSATIONAL_KEYWORDS)
    
    # Actuarial keywords to verify if query is about reserving or dataset metadata
    actuarial_keywords = {
        "reserve", "reserving", "ultimate", "ibnr", "claims", "paid", "incurred", "outstanding", 
        "triangle", "ldf", "cdf", "tail", "development", "loss", "premium", "diagnostic", 
        "outlier", "stability", "suitability", "comparison", "recommendation", "on-level",
        "inflation", "volatility", "case reserves", "adequacy", "mack", "friedland", "chain ladder",
        "bornhuetter", "ferguson", "cape cod", "benktander", "clark", "expected loss",
        "row", "rows", "column", "columns", "variable", "variables", "shape", "dimension", "dimensions",
        "accident year", "accident years", "missing value", "missing values", "missing", "entity", "entities",
        "development period", "development periods", "dataset", "data"
    }
    has_actuarial_terms = any(k in msg_lower for k in actuarial_keywords)
    
    # Out of scope keywords
    out_of_scope_keywords = {
        "weather", "sports", "joke", "ipl", "python", "programming", "quantum", "coding", 
        "write a code", "write a python", "javascript", "html", "css", "news", "movie", "song",
        "sing", "dance", "game", "match", "recipe", "food", "cook"
    }
    has_out_of_scope_terms = any(k in msg_lower for k in out_of_scope_keywords)
    
    if is_greeting and not has_actuarial_terms:
        intent = "GREETING"
    elif has_out_of_scope_terms and not has_actuarial_terms:
        intent = "OUT_OF_SCOPE"
    elif not has_actuarial_terms and not is_greeting:
        # If it doesn't match any reserving concept or greeting, it's out of scope
        intent = "OUT_OF_SCOPE"
    elif recommendation or "recommend" in msg_lower or "best estimate" in msg_lower or "why did" in msg_lower:
        intent = "RECOMMENDATION_QUERY"
    elif comparison or "calculate" in msg_lower or "compute" in msg_lower or len(methods) > 0 or "reserve" in msg_lower or "ultimate" in msg_lower or "ibnr" in msg_lower:
        intent = "CALCULATION_QUERY"
    elif any(k in msg_lower for k in ["row", "column", "variable", "shape", "accident year", "missing", "entit", "development period", "dataset", "dimension"]):
        intent = "DATASET_QUERY"
        
    return {
        "intent": intent,
        "methods": methods,
        "basis": basis,
        "comparison": comparison,
        "recommendation": recommendation,
        "explicit_all": explicit_all,
        "parameters": {}
    }
