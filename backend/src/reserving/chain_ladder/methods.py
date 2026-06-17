"""Chain ladder reserving methods."""

from backend.src.models_legacy.methods import ChainLadder, MackChainladder
from backend.src.reserving.registry import register_method

register_method(ChainLadder)
register_method(MackChainladder)

__all__ = ["ChainLadder", "MackChainladder"]
