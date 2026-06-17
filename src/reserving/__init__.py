"""Reserving method package with plugin-style registration."""

from src.reserving.registry import registry, register_method

# Import modules for built-in method registration. New method modules only need
# to call register_method; orchestrators consume the registry rather than the
# individual implementations.
from src.reserving.chain_ladder import methods as _chain_ladder  # noqa: F401
from src.reserving.bornhuetter_ferguson import method as _bf  # noqa: F401
from src.reserving.benktander import method as _benktander  # noqa: F401
from src.reserving.cape_cod import method as _cape_cod  # noqa: F401
from src.reserving.case_outstanding import method as _case_outstanding  # noqa: F401
from backend.models.methods import Clark

register_method(Clark)

__all__ = ["registry", "register_method"]
