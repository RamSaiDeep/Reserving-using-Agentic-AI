"""Benktander reserving method."""

from backend.src.models_legacy.methods import Benktander
from backend.src.reserving.registry import register_method

register_method(Benktander)

__all__ = ["Benktander"]
