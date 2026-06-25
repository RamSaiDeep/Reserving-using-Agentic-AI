import numpy as np
from typing import List, Union

def calculate_cdfs(ldfs: Union[List[float], np.ndarray], tail_factor: float = 1.0) -> np.ndarray:
    """
    Computes cumulative development factors (CDFs) by backward multiplication.
    If tail_factor is provided, it is appended to the ldfs list or multiplied.
    """
    factors = list(ldfs)
    # If the last factor is not already the tail factor or we need to ensure tail is included,
    # we can append the tail factor. Usually, in standard actuarial calculations, 
    # the last age-to-age factor is followed by the tail factor.
    factors = factors + [tail_factor]
    
    cdfs = []
    for i in range(len(factors)):
        cdfs.append(float(np.prod(factors[i:])))
    return np.array(cdfs)
