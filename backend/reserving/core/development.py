import numpy as np
import pandas as pd
from typing import Union

def calculate_age_to_age_factors(cumulative_triangle: Union[pd.DataFrame, np.ndarray, list]) -> Union[pd.DataFrame, np.ndarray]:
    """
    Calculate individual age-to-age factors for every accident year.
    Supports both pandas DataFrame (with column names) and numpy array/list inputs.
    """
    if isinstance(cumulative_triangle, pd.DataFrame):
        factors = pd.DataFrame(index=cumulative_triangle.index)
        for col in range(cumulative_triangle.shape[1] - 1):
            current = cumulative_triangle.iloc[:, col]
            nxt = cumulative_triangle.iloc[:, col + 1]
            factors[f"{cumulative_triangle.columns[col]}->{cumulative_triangle.columns[col+1]}"] = nxt / current
        return factors
    else:
        mat = np.array(cumulative_triangle, dtype=float)
        if len(mat.shape) != 2:
            raise ValueError("Triangle must be a 2D structure.")
        n_rows, n_cols = mat.shape
        factors = np.full((n_rows, n_cols - 1), np.nan)
        for j in range(n_cols - 1):
            factors[:, j] = mat[:, j + 1] / mat[:, j]
        return factors
