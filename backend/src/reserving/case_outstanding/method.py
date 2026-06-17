"""Case outstanding reserving method."""

from backend.src.models_legacy.methods import CaseOutstanding
from backend.src.reserving.registry import register_method

register_method(CaseOutstanding)

__all__ = ["CaseOutstanding"]
