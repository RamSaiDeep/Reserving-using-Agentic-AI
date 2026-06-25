import numpy as np
import pandas as pd
from typing import List, Union, Optional

from reserving.core.averages import volume_weighted_average, simple_average, geometric_average, medial_average
from reserving.core.cdfs import calculate_cdfs as calc_cdfs
from reserving.core.development import calculate_age_to_age_factors as calc_ata

class DevelopmentEngine:
    @staticmethod
    def incremental_to_cumulative(triangle: Union[pd.DataFrame, np.ndarray, list]) -> Union[pd.DataFrame, np.ndarray]:
        """
        Convert incremental loss triangle to cumulative loss triangle.
        """
        if isinstance(triangle, pd.DataFrame):
            cumulative = triangle.cumsum(axis=1)
            cumulative.columns = cumulative.columns.astype(int)
            return cumulative
        else:
            mat = np.array(triangle, dtype=float)
            return np.cumsum(mat, axis=1)

    @staticmethod
    def calculate_ata_factors(cumulative_triangle: Union[pd.DataFrame, np.ndarray, list]) -> Union[pd.DataFrame, np.ndarray]:
        """
        Calculate individual age-to-age factors.
        """
        return calc_ata(cumulative_triangle)

    @staticmethod
    def calculate_average_ldfs(
        ata_triangle: Union[pd.DataFrame, np.ndarray],
        method: str = "volume_weighted",
        cumulative_triangle: Optional[Union[pd.DataFrame, np.ndarray]] = None
    ) -> Union[pd.Series, np.ndarray]:
        """
        Computes average loss development factors (LDFs) using selected averages:
        - "volume_weighted"
        - "simple" (or "straight_average")
        - "geometric"
        - "medial"
        """
        method_lower = str(method).lower().replace(" ", "_")
        
        if isinstance(ata_triangle, pd.DataFrame):
            results = {}
            columns = ata_triangle.columns
            
            for j, col in enumerate(columns):
                factors = ata_triangle[col].dropna().values
                
                if method_lower == "volume_weighted":
                    if cumulative_triangle is None:
                        raise ValueError("cumulative_triangle DataFrame is required for volume_weighted average.")
                    
                    if isinstance(cumulative_triangle, pd.DataFrame):
                        current_losses = cumulative_triangle.iloc[:, j].values
                        next_losses = cumulative_triangle.iloc[:, j+1].values
                    else:
                        current_losses = cumulative_triangle[:, j]
                        next_losses = cumulative_triangle[:, j+1]
                        
                    val = volume_weighted_average(current_losses, next_losses)
                elif method_lower in ("simple", "straight_average", "straight"):
                    val = simple_average(factors)
                elif method_lower == "geometric":
                    val = geometric_average(factors)
                elif method_lower == "medial":
                    val = medial_average(factors)
                else:
                    raise ValueError(f"Unknown averaging method: {method}")
                
                results[col] = val
                
            return pd.Series(results)
        else:
            mat = np.array(ata_triangle, dtype=float)
            n_rows, n_cols = mat.shape
            results = np.zeros(n_cols)
            
            for j in range(n_cols):
                factors = mat[:, j]
                factors = factors[~np.isnan(factors)]
                
                if method_lower == "volume_weighted":
                    if cumulative_triangle is None:
                        raise ValueError("cumulative_triangle numpy array is required for volume_weighted average.")
                    cum_mat = np.array(cumulative_triangle, dtype=float)
                    current_losses = cum_mat[:, j]
                    next_losses = cum_mat[:, j+1]
                    val = volume_weighted_average(current_losses, next_losses)
                elif method_lower in ("simple", "straight_average", "straight"):
                    val = simple_average(factors)
                elif method_lower == "geometric":
                    val = geometric_average(factors)
                elif method_lower == "medial":
                    val = medial_average(factors)
                else:
                    raise ValueError(f"Unknown averaging method: {method}")
                
                results[j] = val
                
            return results

    @staticmethod
    def calculate_cdfs(ldfs: Union[List[float], np.ndarray, pd.Series], tail_factor: float = 1.0) -> np.ndarray:
        """
        Calculate CDFs from LDFs.
        """
        if isinstance(ldfs, pd.Series):
            ldfs_val = ldfs.values
        else:
            ldfs_val = np.array(ldfs, dtype=float)
        return calc_cdfs(ldfs_val, tail_factor)

    @staticmethod
    def project_ultimate(
        latest_diagonal: Union[List[float], np.ndarray, pd.Series],
        cdfs: Union[List[float], np.ndarray, pd.Series]
    ) -> np.ndarray:
        """
        Projects ultimate losses: latest_diagonal * cdfs
        """
        if isinstance(latest_diagonal, pd.Series):
            diag = latest_diagonal.values
        else:
            diag = np.array(latest_diagonal, dtype=float)
            
        if isinstance(cdfs, pd.Series):
            cdf_vals = cdfs.values
        else:
            cdf_vals = np.array(cdfs, dtype=float)
            
        n = min(len(diag), len(cdf_vals))
        return diag[:n] * cdf_vals[:n]
