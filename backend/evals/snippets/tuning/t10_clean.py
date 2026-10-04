"""Small, correct helpers. A good reviewer should not invent problems here."""
# clean

from collections import Counter


def word_frequencies(text: str) -> dict[str, int]:
    return dict(Counter(text.lower().split()))


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def chunked(items: list, size: int) -> list[list]:
    if size <= 0:
        raise ValueError("size must be positive")
    return [items[i:i + size] for i in range(0, len(items), size)]
