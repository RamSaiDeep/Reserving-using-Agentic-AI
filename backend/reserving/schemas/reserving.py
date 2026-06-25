from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Literal

class MethodConfig(BaseModel):
    enabled: bool
    run_paid: Optional[bool] = True
    run_incurred: Optional[bool] = True
    source: Optional[Literal["paid", "incurred", "both"]] = None
    aprioriLossRatio: Optional[float] = None
    iterations: Optional[int] = None
    decay: Optional[float] = None
    matureYears: Optional[List[int]] = None
    curveType: Optional[str] = None
    approach: Optional[str] = None
    inflationRate: Optional[float] = None
    allow_negative_ibnr: Optional[bool] = False
    legacy_compatibility: Optional[bool] = True

class ExecuteRequest(BaseModel):
    session_id: str
    configs: Optional[Dict[str, MethodConfig]] = None
    paid_ldfs: Optional[List[float]] = None
    incurred_ldfs: Optional[List[float]] = None
    paid_tail_factor: Optional[float] = 1.0
    incurred_tail_factor: Optional[float] = 1.0
    mature_cdf_threshold: Optional[float] = 1.05
    allow_negative_ibnr: Optional[bool] = False
    legacy_compatibility: Optional[bool] = True
    
    # Backward compatibility fields
    method_code: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    custom_ldfs: Optional[list] = None
    custom_incurred_ldfs: Optional[list] = None
    data_source: Optional[str] = "paid"
    
    rate_changes: Optional[list] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
