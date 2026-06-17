"""Cape Cod reserving method."""

from backend.src.models_legacy.methods import CapeCod
from backend.src.reserving.registry import register_method

register_method(CapeCod)

__all__ = ["CapeCod"]
