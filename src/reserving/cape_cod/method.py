"""Cape Cod reserving method."""

from backend.models.methods import CapeCod
from src.reserving.registry import register_method

register_method(CapeCod)

__all__ = ["CapeCod"]
