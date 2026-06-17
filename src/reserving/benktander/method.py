"""Benktander reserving method."""

from backend.models.methods import Benktander
from src.reserving.registry import register_method

register_method(Benktander)

__all__ = ["Benktander"]
