"""General triangle utilities."""

from backend.src.models_legacy.triangle import Triangle


def latest_diagonal(triangle: Triangle):
    return triangle.get_latest_diagonal()
