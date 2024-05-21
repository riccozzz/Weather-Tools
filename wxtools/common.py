"""
Common helper methods used in various modules.
"""

from __future__ import annotations

from typing import Any


def quotify(value: Any) -> str:
    """
    Returns str(value), if input value is already a string we wrap it in single
    quotes.
    """
    return f"'{value}'" if isinstance(value, str) else str(value)
