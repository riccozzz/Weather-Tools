"""
Common calculations for different weather parameters
"""

from __future__ import annotations

import math

from .units import convert_unit


class CalculatorError(Exception):
    """Exception for calculator related errors."""


def saturation_vapor_pressure(temperature: float, unit: str = "C") -> float:
    """
    Calculates saturation vapour pressure of water given the specified
    temperature in degrees using Tetens equation. Will return the pressure in
    hPa.

    https://en.wikipedia.org/wiki/Tetens_equation

    Parameters:
        * temperature (float) -- Temperature value in degrees.
        * unit (str) -- Unit of the values, either 'C' (default) or 'F'.
    """
    if unit == "C":
        temp_c = temperature
    elif unit == "F":
        temp_c = convert_unit(temperature, from_unit="fahrenheit", to_unit="celsius")
    else:
        raise CalculatorError(f"Invalid unit specified: '{unit}'")
    if temp_c >= 0:
        return 6.1078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    return 6.1078 * math.exp((21.875 * temp_c) / (temp_c + 265.5))


def relative_humidity(temperature: float, dew_point: float, unit: str = "C") -> float:
    """
    Calculates relative humidity given air temperature and dew point values in
    degrees. Unit of both values must be the same, specified by either 'C'
    (celsius, default) or 'F' (fahrenheit) as the specified unit. Returns
    percentage rounded to 2 decimal places.

    Based on the Clausius-Clapeyron relation and empirical approximations.

    Parameters:
        * temperature (float) -- Air temperature value in degrees.
        * dew_point (float) -- Dew point temperature value in degrees.
        * unit (str) -- Unit of the values, either 'C' (default) or 'F'.
    """
    if unit == "C":
        temp_c = temperature
        dp_c = dew_point
    elif unit == "F":
        temp_c = convert_unit(temperature, from_unit="fahrenheit", to_unit="celsius")
        dp_c = convert_unit(dew_point, from_unit="fahrenheit", to_unit="celsius")
    else:
        raise CalculatorError(f"Invalid unit specified: '{unit}'")
    actual_vapor_pressure = saturation_vapor_pressure(dp_c)
    sat_vapor_pressure = saturation_vapor_pressure(temp_c)
    return round((actual_vapor_pressure / sat_vapor_pressure) * 100, 2)


def _simple_heat_index(temp_f: float, rh: float) -> float:
    simple_hi = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (rh * 0.094))
    return (simple_hi + temp_f) / 2


def _rothfusz_heat_index(temp_f: float, rh: float) -> float:
    return (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * rh
        - 0.22475541 * temp_f * rh
        - 0.00683783 * temp_f * temp_f
        - 0.05481717 * rh * rh
        + 0.00122874 * temp_f * temp_f * rh
        + 0.00085282 * temp_f * rh * rh
        - 0.00000199 * temp_f * temp_f * rh * rh
    )


def _adjust_heat_index(hi: float, temp_f: float, rh: float) -> float:
    # Adjustment for low relative humidity
    if rh < 13 and 80 <= temp_f <= 112:
        adjustment = ((13 - rh) / 4) * math.sqrt((17 - abs(temp_f - 95)) / 17)
        return hi - adjustment
    # Adjustment for high relative humidity
    if rh > 85 and 80 <= temp_f <= 87:
        adjustment = ((rh - 85) / 10) * ((87 - temp_f) / 5)
        return hi + adjustment
    return hi


def heat_index(temperature: float, rel_humidity: float, unit: str = "C") -> float:
    """
    Calculates heat index (apparent temperature) given air temperature and
    relative humidity. Loses accuracy below 80F and should not be used below
    50F.

    Based on the NWS heat index "equation" outline by Rothfusz in technical
    attachment SR90-23, and additional adjustments from the NWS.
    https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml

    Parameters:
        * temperature (float) -- Air temperature value in degrees.
        * rel_humidity (float) -- Relative humidity percentage.
        * unit (str) -- Unit of the values, either 'C' (default) or 'F'.
    """
    if unit == "C":
        temp_f = convert_unit(temperature, from_unit="celsius", to_unit="fahrenheit")
    elif unit == "F":
        temp_f = temperature
    else:
        raise CalculatorError(f"Invalid unit specified: '{unit}'")
    # First, use the simple formula, and use it if value is < 80F
    hi_result = _simple_heat_index(temp_f, rel_humidity)
    if hi_result >= 80:
        # Value was >= 80F, use the Rothfusz method
        hi_result = _rothfusz_heat_index(temp_f, rel_humidity)
        # Make adjustments for high and low RH if needed before returning
        hi_result = _adjust_heat_index(hi_result, temp_f, rel_humidity)
    if unit == "F":
        return hi_result
    return convert_unit(hi_result, from_unit="fahrenheit", to_unit="celsius")


def wind_chill(
    temperature: float, wind_speed: float, temp_unit: str = "C", wind_unit: str = "MPH"
) -> float:
    """
    Calculates wind chill (apparent temperature) given air temperature and
    wind speed. Should not be used above 50F.

    Based on the NWS/JAGTI wind chill temperature index formula.
    https://www.weather.gov/media/lsx/wcm/Winter2008/Wind_Chill.pdf

    Parameters:
        * temperature (float) -- Air temperature value in degrees.
        * rel_humidity (float) -- Relative humidity percentage.
        * temp_unit (str) -- Unit of temperature, either 'C' (default) or 'F'.
        * wind_unit (str) -- Unit of wind speed, either 'MPH' (default) or 'KTS'.
    """
    temp_unit = temp_unit.upper()
    wind_unit = wind_unit.upper()
    return 0


def wet_bulb(temperature: float, rel_humidity: float, unit: str = "C") -> float:
    """
    Calculates estimated wet bulb temperature given air temperature and
    relative humidity.

    Based on the Stull approximate formula for wet bulb.
    https://journals.ametsoc.org/view/journals/apme/50/11/jamc-d-11-0143.1.xml

    Parameters:
        * temperature (float) -- Air temperature value in degrees.
        * rel_humidity (float) -- Relative humidity percentage.
        * unit (str) -- Unit of the values, either 'C' (default) or 'F'.
    """
    unit = unit.upper()
    if unit == "C":
        temp_c = temperature
    elif unit == "F":
        temp_c = convert_unit(temperature, from_unit="fahrenheit", to_unit="celsius")
    else:
        raise CalculatorError(f"Invalid unit specified: '{unit}'")
    wb_c: float = (
        (temp_c * math.atan(0.151977 * ((rel_humidity + 8.313659) ** 0.5)))
        + math.atan(temp_c + rel_humidity)
        - math.atan(rel_humidity - 1.676331)
        + (0.00391838 * (rel_humidity**1.5) * math.atan(0.023101 * rel_humidity))
        - 4.686035
    )
    if unit == "C":
        return wb_c
    return convert_unit(wb_c, from_unit="celsius", to_unit="fahrenheit")
