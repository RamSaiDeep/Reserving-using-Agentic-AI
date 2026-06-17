"""General triangle utilities."""

from backend.models.triangle import Triangle


def latest_diagonal(triangle: Triangle):
    return triangle.get_latest_diagonal()
