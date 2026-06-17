"""Development factor utilities."""

from backend.models.triangle import Triangle


def compute_ldfs(triangle: Triangle):
    return triangle.compute_ldfs()


def compute_cdfs(triangle: Triangle, selected_ldfs):
    return triangle.compute_cdfs(selected_ldfs)
