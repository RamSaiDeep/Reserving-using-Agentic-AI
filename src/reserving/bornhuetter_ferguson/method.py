"""Bornhuetter-Ferguson reserving method."""

from backend.models.methods import BornhuetterFerguson
from src.reserving.registry import register_method

register_method(BornhuetterFerguson)

__all__ = ["BornhuetterFerguson"]
