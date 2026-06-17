"""Bornhuetter-Ferguson reserving method."""

from backend.src.models_legacy.methods import BornhuetterFerguson
from backend.src.reserving.registry import register_method

register_method(BornhuetterFerguson)

__all__ = ["BornhuetterFerguson"]
