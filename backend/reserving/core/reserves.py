def calculate_unpaid_claim_estimate(ultimate: float, paid_latest: float) -> float:
    """
    Reserve = Ultimate - Paid
    """
    return float(ultimate - paid_latest)

def calculate_total_reserve(reserves: list) -> float:
    """
    Sums total reserve estimates.
    """
    return float(sum(r for r in reserves if r is not None))

def calculate_case_outstanding(incurred_latest: float, paid_latest: float, allow_negative_case: bool = False) -> float:
    """
    Case Outstanding = Incurred - Paid
    """
    case = incurred_latest - paid_latest
    if not allow_negative_case:
        case = max(0.0, case)
    return float(case)

def calculate_ibnr(ultimate: float, incurred_latest: float, allow_negative_ibnr: bool = False) -> float:
    """
    IBNR = Ultimate - Incurred
    """
    ibnr = ultimate - incurred_latest
    if not allow_negative_ibnr:
        ibnr = max(0.0, ibnr)
    return float(ibnr)
