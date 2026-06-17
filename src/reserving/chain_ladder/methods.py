"""Chain ladder reserving methods."""

from backend.models.methods import ChainLadder, MackChainladder
from src.reserving.registry import register_method

register_method(ChainLadder)
register_method(MackChainladder)

__all__ = ["ChainLadder", "MackChainladder"]
