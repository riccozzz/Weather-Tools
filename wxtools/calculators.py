"""
Common calculations for different weather parameters
"""

from __future__ import annotations

import math

from .units import convert_unit


class CalculatorError(Exception):
    """Exception for calculator related errors."""


def _convert_temperature(
    temperature: float, current_unit: str, to_unit: str, error_check: bool = True
) -> float:
    """
    Helper method for converting temperature values to C and F. Also will raise
    CalculatorError if specified units are incorrect or not usable.
    """
    valid_units = ("C", "F")
    conv_from = current_unit.upper().strip()
    conv_to = to_unit.upper().strip()
    if error_check:
        if conv_from not in valid_units:
            raise CalculatorError(f"Invalid current unit specified: '{conv_from}'")
        if conv_to not in valid_units:
            raise CalculatorError(f"Invalid convert to unit specified: '{conv_to}'")
    if conv_from == conv_to:
        return temperature
    if conv_from == "F" and conv_to == "C":
        return convert_unit(temperature, from_unit="fahrenheit", to_unit="celsius")
    return convert_unit(temperature, from_unit="celsius", to_unit="fahrenheit")


def _convert_wind_speed(
    wind_speed: float, current_unit: str, to_unit: str, error_check: bool = True
) -> float:
    """
    Helper method for converting wind speed values to MPH and KTS. Also will
    raise CalculatorError if specified units are incorrect or not usable.
    """
    valid_units = ("KTS", "MPH")
    conv_from = current_unit.upper().strip()
    conv_to = to_unit.upper().strip()
    if error_check:
        if conv_from not in valid_units:
            raise CalculatorError(f"Invalid current unit specified: '{conv_from}'")
        if conv_to not in valid_units:
            raise CalculatorError(f"Invalid convert to unit specified: '{conv_to}'")
    if conv_from == conv_to:
        return wind_speed
    if conv_from == "MPH" and conv_to == "KTS":
        return convert_unit(wind_speed, from_unit="mile per hour", to_unit="knot")
    return convert_unit(wind_speed, from_unit="knot", to_unit="mile per hour")


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


def saturation_vapor_pressure(temperature: float, unit: str) -> float:
    """
    Calculates saturation vapour pressure of water given the specified
    temperature in degrees using Tetens equation. Will return the pressure in
    hPa.

    https://en.wikipedia.org/wiki/Tetens_equation

    Parameters:
        * temperature (float) -- Temperature value in degrees.
        * unit (str) -- Unit of the values, either 'C' or 'F'.
    """
    temp_c = _convert_temperature(temperature, current_unit=unit, to_unit="C")
    if temp_c >= 0:
        return 6.1078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    return 6.1078 * math.exp((21.875 * temp_c) / (temp_c + 265.5))


def relative_humidity(temperature: float, dew_point: float, unit: str) -> float:
    """
    Calculates relative humidity given air temperature and dew point values in
    degrees. Unit of both values must be the same, specified by either 'C'
    (celsius) or 'F' (fahrenheit) as the specified unit. Returns
    percentage rounded to 2 decimal places.

    Based on the Clausius-Clapeyron relation and empirical approximations.

    Parameters:
        * temperature (float) -- Air temperature value in degrees.
        * dew_point (float) -- Dew point temperature value in degrees.
        * unit (str) -- Unit of the values, either 'C' or 'F'.
    """
    temp_c = _convert_temperature(temperature, current_unit=unit, to_unit="C")
    dp_c = _convert_temperature(dew_point, current_unit=unit, to_unit="C")
    actual_vapor_pressure = saturation_vapor_pressure(dp_c, "C")
    sat_vapor_pressure = saturation_vapor_pressure(temp_c, "C")
    return round((actual_vapor_pressure / sat_vapor_pressure) * 100, 2)


def heat_index(temperature: float, rel_humidity: float, unit: str) -> float:
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
        * unit (str) -- Unit of the values, either 'C' or 'F'.
    """
    temp_f = _convert_temperature(temperature, current_unit=unit, to_unit="F")
    # First, use the simple formula, and use it if value is < 80F
    hi_result = _simple_heat_index(temp_f, rel_humidity)
    if hi_result >= 80:
        # Value was >= 80F, use the Rothfusz method
        hi_result = _rothfusz_heat_index(temp_f, rel_humidity)
        # Make adjustments for high and low RH if needed before returning
        hi_result = _adjust_heat_index(hi_result, temp_f, rel_humidity)
    return _convert_temperature(
        hi_result, current_unit="F", to_unit=unit, error_check=False
    )


def wind_chill(
    temperature: float, wind_speed: float, temp_unit: str, wind_unit: str
) -> float:
    """
    Calculates wind chill (apparent temperature) given air temperature and
    wind speed. Should not be used above air temps of 50F.

    Based on the NWS/JAGTI wind chill temperature index formula.
    https://www.weather.gov/media/lsx/wcm/Winter2008/Wind_Chill.pdf

    Parameters:
        * temperature (float) -- Air temperature value in degrees.
        * rel_humidity (float) -- Relative humidity percentage.
        * wind_speed (float) -- Speed of wind value.
        * temp_unit (str) -- Unit of temperature, either 'C' or 'F'.
        * wind_unit (str) -- Unit of wind speed, either 'KTS' or 'MPH'.
    """
    temp_f = _convert_temperature(temperature, current_unit=temp_unit, to_unit="F")
    wind_mph = _convert_wind_speed(wind_speed, current_unit=wind_unit, to_unit="MPH")
    wind_chill_f: float = (
        35.74
        + 0.6215 * temp_f
        - 35.75 * (wind_mph**0.16)
        + 0.4275 * temp_f * (wind_mph**0.16)
    )
    return _convert_temperature(
        wind_chill_f, current_unit="F", to_unit=temp_unit, error_check=False
    )


def wet_bulb(temperature: float, rel_humidity: float, unit: str) -> float:
    """
    Calculates estimated wet bulb temperature given air temperature and
    relative humidity.

    Based on the Stull approximate formula for wet bulb.
    https://journals.ametsoc.org/view/journals/apme/50/11/jamc-d-11-0143.1.xml

    Parameters:
        * temperature (float) -- Air temperature value in degrees.
        * rel_humidity (float) -- Relative humidity percentage.
        * unit (str) -- Unit of the values, either 'C' or 'F'.
    """
    temp_c = _convert_temperature(temperature, current_unit=unit, to_unit="C")
    wb_c: float = (
        (temp_c * math.atan(0.151977 * ((rel_humidity + 8.313659) ** 0.5)))
        + math.atan(temp_c + rel_humidity)
        - math.atan(rel_humidity - 1.676331)
        + (0.00391838 * (rel_humidity**1.5) * math.atan(0.023101 * rel_humidity))
        - 4.686035
    )
    return _convert_temperature(wb_c, current_unit="C", to_unit=unit, error_check=False)


def apparent_temperature(
    temperature: float,
    rel_humidity: float,
    wind_speed: float,
    temp_unit: str,
    wind_unit: str,
) -> float:
    """
    Calculates estimated apparent temperature given air temperature, relative
    humidity, and wind speed. Ideal for the 50F -> 80F temperature range,
    where wind chill and heat index lose accuracy.

    A simplified formula based on Steadmans original apparent temperature.

    Parameters:
        * temperature (float) -- Air temperature value in degrees.
        * rel_humidity (float) -- Relative humidity percentage.
        * wind_speed (float) -- Speed of wind value.
        * temp_unit (str) -- Unit of temperature, either 'C' or 'F'.
        * wind_unit (str) -- Unit of wind speed, either 'KTS' or 'MPH'.
    """
    temp_f = _convert_temperature(temperature, current_unit=temp_unit, to_unit="F")
    wind_mph = _convert_wind_speed(wind_speed, current_unit=wind_unit, to_unit="MPH")
    apparent_temp = temp_f + 0.33 * rel_humidity - 0.7 * wind_mph - 4
    return _convert_temperature(
        apparent_temp, current_unit="F", to_unit=temp_unit, error_check=False
    )


def feels_like(
    temperature: float,
    rel_humidity: float,
    wind_speed: float,
    temp_unit: str,
    wind_unit: str,
) -> float:
    """
    Calculates estimated "feels like" temperature given air temperature,
    relative humidity, and wind speed. For temperatures below 50F, the result
    will be wind chill. Between 50F and 80F will be estimated apparent
    temperature. Above 80F will be heat index.

    Parameters:
        * temperature (float) -- Air temperature value in degrees.
        * rel_humidity (float) -- Relative humidity percentage.
        * wind_speed (float) -- Speed of wind value.
        * temp_unit (str) -- Unit of temperature, either 'C' or 'F'.
        * wind_unit (str) -- Unit of wind speed, either 'KTS' or 'MPH'.
    """
    temp_f = _convert_temperature(temperature, current_unit=temp_unit, to_unit="F")
    wind_mph = _convert_wind_speed(wind_speed, current_unit=wind_unit, to_unit="MPH")
    if temp_f <= 50:
        feeling_f = wind_chill(temp_f, wind_mph, "F", "MPH")
    elif temp_f > 50 and temp_f < 80:
        feeling_f = apparent_temperature(temp_f, rel_humidity, wind_mph, "F", "MPH")
    else:
        feeling_f = heat_index(temp_f, rel_humidity, "F")
    return _convert_temperature(
        feeling_f, current_unit="F", to_unit=temp_unit, error_check=False
    )
