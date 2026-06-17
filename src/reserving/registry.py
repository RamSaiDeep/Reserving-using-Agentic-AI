"""Registry for actuarial reserving methods.

Methods register themselves here so API and agents can discover available
reserving techniques without changing orchestration code.
"""

from __future__ import annotations

from typing import Dict, Iterable, Type

from backend.models.methods import MethodBase


class ReservingMethodRegistry:
    """In-memory registry of independent reserving method classes."""

    def __init__(self) -> None:
        self._methods: Dict[str, Type[MethodBase]] = {}

    def register(self, method: Type[MethodBase]) -> Type[MethodBase]:
        self._methods[method.code] = method
        return method

    def get(self, code: str) -> Type[MethodBase] | None:
        return self._methods.get(code)

    def all(self) -> Dict[str, Type[MethodBase]]:
        return dict(self._methods)

    def codes(self) -> Iterable[str]:
        return self._methods.keys()


registry = ReservingMethodRegistry()


def register_method(method: Type[MethodBase]) -> Type[MethodBase]:
    return registry.register(method)
