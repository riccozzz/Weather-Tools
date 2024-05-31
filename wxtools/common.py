"""
Common helper methods used in various modules.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

_CARDINAL_FULLNAMES = (
    "North",
    "North-Northeast",
    "Northeast",
    "East-Northeast",
    "East",
    "East-Southeast",
    "Southeast",
    "South-Southeast",
    "South",
    "South-Southwest",
    "Southwest",
    "West-Southwest",
    "West",
    "West-Northwest",
    "Northwest",
    "North-Northwest",
)

_CARDINAL_ARROWS = (
    "⬇",
    "⬇",
    "⬋",
    "⬅",
    "⬅",
    "⬅",
    "⬉",
    "⬆",
    "⬆",
    "⬆",
    "⬈",
    "➡",
    "➡",
    "➡",
    "⬊",
    "⬇",
)

_CARDINAL_ABBREVIATED = (
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
)


def fraction_str_to_float(fractional: str) -> float:
    """Converts a string with fractions to a floating point number."""
    parts = fractional.split()
    if len(parts) == 2:
        return round(int(parts[0]) + float(Fraction(parts[1])), 2)
    return round(float(Fraction(parts[0])), 2)


def quotify(value: Any) -> str:
    """
    Returns str(value), if input value is already a string we wrap it in single
    quotes.
    """
    return f"'{value}'" if isinstance(value, str) else str(value)


def cardinal_direction(direction: int, style: str = "shortarrow") -> str:
    """
    The cardinal direction of the specified wind direction value.

    Parameters:
    * direction (int) -- Direction of wind in 0-360 degrees.
    * style (str) -- The style of string to be returned. Possible values
    are 'short', 'long', 'arrow', 'shortarrow', 'degrees'. Defaults to
    'shortarrow'.

    Examples of each style for northeasterly wind:
    * 'short' -> 'NE'
    * 'long' -> 'Northeast'
    * 'arrow' -> '⬋'
    * 'shortarrow -> 'NE ⬋'
    * 'degrees' -> '45°'
    """
    cfstyle = style.casefold()
    cardinal_index = int(round(direction / 22.5) % 16)
    if cfstyle == "shortarrow":
        arrow = _CARDINAL_ARROWS[cardinal_index]
        abbr = _CARDINAL_ABBREVIATED[cardinal_index]
        return f"{abbr} {arrow}"
    if cfstyle == "arrow":
        return _CARDINAL_ARROWS[cardinal_index]
    if cfstyle == "long":
        return _CARDINAL_FULLNAMES[cardinal_index]
    if cfstyle == "degrees":
        return f"{direction}°"
    return _CARDINAL_ABBREVIATED[cardinal_index]
