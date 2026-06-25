import pandas as pd

def select_ldfs(avg_factors: pd.DataFrame, method: str = "Simple", tail_factor: float = 1.0) -> pd.Series:
    """
    Selects LDFs based on method name and appends the tail factor.
    """
    method_normalized = str(method).capitalize()
    if method_normalized not in avg_factors.index:
        found = False
        for idx in avg_factors.index:
            if idx.lower() == str(method).lower():
                method_normalized = idx
                found = True
                break
        if not found:
            method_normalized = avg_factors.index[0]
            
    selected = avg_factors.loc[method_normalized].copy()
    selected["Tail"] = tail_factor
    return selected
