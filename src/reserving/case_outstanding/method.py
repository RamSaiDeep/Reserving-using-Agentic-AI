"""Case outstanding reserving method."""

from backend.models.methods import CaseOutstanding
from src.reserving.registry import register_method

register_method(CaseOutstanding)

__all__ = ["CaseOutstanding"]
