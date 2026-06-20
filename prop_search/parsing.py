"""Shared helpers for turning messy source values into numbers."""

from __future__ import annotations

import re
from typing import Any, Optional


def parse_price(value: Any) -> Optional[int]:
    """Turn '€485,000' / '485.000 €' / 485000 into an int euro amount."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def parse_size(text: Any) -> Optional[int]:
    """Extract square metres from a number or a string like '90 m² · 3 hab.'."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    match = re.search(r"(\d[\d.,]*)\s*m", str(text))
    if not match:
        digits = re.sub(r"[^\d]", "", str(text))
        return int(digits) if digits else None
    digits = re.sub(r"[^\d]", "", match.group(1))
    return int(digits) if digits else None


def parse_rooms(text: Any) -> Optional[int]:
    """Extract bedroom count from a number or a string ('3 hab.', '2 bed.')."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    match = re.search(r"(\d+)\s*(?:hab|dorm|bed|room|habitaci)", str(text), re.I)
    return int(match.group(1)) if match else None


def first(item: dict, *keys: str) -> Any:
    """First present, non-empty value among ``keys`` in ``item``."""
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None
