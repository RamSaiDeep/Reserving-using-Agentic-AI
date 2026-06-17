"""Triangle construction helpers kept separate from API and agents."""

from backend.src.models_legacy.triangle import Triangle


def triangle_from_csv(csv_text: str) -> Triangle:
    return Triangle.from_csv(csv_text)
