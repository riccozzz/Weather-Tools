"""
Experimenting with parsing METAR data into a python object.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any

import requests

from .errors import AviationWeatherError
from .icaos import _ICAOS


def _quotify(value: Any) -> str:
    """
    Returns str(value), if input value is already a string we wrap it in single
    quotes.
    """
    return f"'{value}'" if isinstance(value, str) else str(value)


def _fraction_to_float(fractional: str) -> float:
    parts = fractional.split()
    if len(parts) == 2:
        return round(int(parts[0]) + float(Fraction(parts[1])), 2)
    return round(float(Fraction(parts[0])), 2)


def _to_mph(knots: int | float) -> float:
    return round(knots * 1.15, 1)


def _rvr_parse(reportable_value: str) -> str:
    if reportable_value[0] == "M":
        return f"< {int(reportable_value[1:])} ft"
    if reportable_value[0] == "P":
        return f"> {int(reportable_value[1:])} ft"
    return f"{int(reportable_value)} ft"


def _saturation_vapor_pressure(temperature: float) -> float:
    return 6.112 * math.exp((17.67 * temperature) / (temperature + 243.5))


def aviationweather_get_metar(station_id: str) -> MetarObservation:
    """Returns the latest METAR from the given station."""

    url = (
        "https://aviationweather.gov/api/data/metar"
        f"?ids={station_id}&format=raw&taf=false"
    )
    try:
        resp = requests.get(url=url, timeout=5)
        resp.raise_for_status()
        metar_raw = resp.text.strip().upper()
        if len(metar_raw) == 0:
            raise AviationWeatherError(f"Could not retrieve data for '{station_id}.'")
        return MetarObservation(metar_raw)
    except requests.RequestException as ex:
        raise AviationWeatherError(ex) from None


# def avwx_get_metar(station_id: str) -> MetarObservation:
#     """Returns the latest METAR from the given station."""
#     avwx_url = f"https://avwx.rest/api/metar/{station_id}?filter=raw"
#     headers = {"Authorization": "2PxTWvsyTeLuyv4AIoemQMflKXEE3MFy_Ubl58rtVs0"}
#     try:
#         resp = requests.get(url=avwx_url, timeout=5, headers=headers)
#         if resp.status_code >= 400:
#             jdata = resp.json()
#             if isinstance(jdata, dict):
#                 if "error" in jdata:
#                     raise AvwxResponseError(jdata["error"])
#         resp.raise_for_status()
#         jdata = resp.json()
#         if isinstance(jdata, dict):
#             if "raw" in jdata:
#                 if isinstance(jdata["raw"], str):
#                     return MetarObservation(jdata["raw"])
#         raise AvwxDataError("Unknown payload data in response.")
#     except requests.RequestException as ex:
#         raise AvwxResponseError(ex) from None


# def synopticdata_get(station_id: str) -> MetarObservation:
#     """Returns the latest METAR from the given station."""
#     token = "a75410c49a0a4814ac9839408dd30ecf"
#     params = f"&stid={station_id}&vars=metar&hfmetars=1&output=json"
#     url = f"https://api.synopticdata.com/v2/stations/latest?token={token}{params}"
#     try:
#         resp = requests.get(url=url, timeout=5)
#         resp.raise_for_status()
#         jdata = resp.json()
#         summary = jdata.get("SUMMARY")
#         if not isinstance(summary, dict):
#             raise SynopticDataError("No summary found in data.")
#         response_code = summary.get("RESPONSE_CODE")
#         if not isinstance(response_code, int):
#             raise SynopticDataError("No response code found in data.")
#         if response_code == 2:
#             response = summary.get("RESPONSE_MESSAGE")
#             if isinstance(response, str) and len(response) > 0:
#                 raise SynopticDataError(response)
#             raise SynopticDataError("Unknown error.")
#         metar = jdata["STATION"][0]["OBSERVATIONS"]["metar_value_1"]["value"]
#         if not isinstance(metar, str):
#             raise SynopticDataError("Invalid metar string (data type).")
#         return MetarObservation(metar.strip().upper())
#     except requests.RequestException as ex:
#         raise SynopticDataError(ex) from None


class MetarTemperature:
    """Object for parsing temperature from a METAR string."""

    def __init__(self, metar_temp: str) -> None:
        self._raw_metar = metar_temp.upper().strip()
        self._temp_c: float = 0
        self._dew_point_c: float | None = None
        if len(self._raw_metar) == 9:
            # Remarks data
            self._temp_c = int(self._raw_metar[2:5]) / 10
            if self._raw_metar[1] == "1":
                self._temp_c *= -1
            self._dew_point_c = int(self._raw_metar[6:9]) / 10
            if self._raw_metar[5] == "1":
                self._dew_point_c *= -1
        else:
            # Normal metar data
            parts = self._raw_metar.replace("M", "-").split("/")
            self._temp_c = float(parts[0])
            if len(parts) > 1 and len(parts[1]) > 0:
                self._dew_point_c = float(parts[1])

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}("
        sb = f"{sb}_raw_metar={_quotify(self._raw_metar)},"
        sb = f"{sb} _temp_c={_quotify(self._temp_c)},"
        sb = f"{sb} _dew_point_c={_quotify(self._dew_point_c)})"
        return sb

    def __str__(self) -> str:
        sb = f"{self.temperature('C')}°C ({self.temperature('F')}°F)"
        if self._dew_point_c is not None:
            sb = f"{sb}, DP {self.dew_point('C')}°C ({self.dew_point('F')}°F)"
            sb = f"{sb}, RH {self.relative_humidity()}%"
            sb = f"{sb}, Heat Index {self.heat_index('C')}°C ({self.heat_index('F')}°F)"
            sb = f"{sb}, Wet Bulb {self.wet_bulb('C')}°C ({self.wet_bulb('F')}°F)"
        return sb

    def temperature(self, unit: str = "C") -> float:
        if unit == "C":
            return round(self._temp_c, 1)
        return round((self._temp_c * 9 / 5) + 32, 1)

    def dew_point(self, unit: str = "C") -> float | None:
        if self._dew_point_c is None:
            return None
        if unit == "C":
            return round(self._dew_point_c, 1)
        return round((self._dew_point_c * 9 / 5) + 32, 1)

    def relative_humidity(self) -> float | None:
        if self._dew_point_c is None:
            return None
        air_sat_vapor = _saturation_vapor_pressure(self._temp_c)
        dp_sat_vapor = _saturation_vapor_pressure(self._dew_point_c)
        return round((dp_sat_vapor / air_sat_vapor) * 100, 1)

    def heat_index(self, unit: str = "F") -> float | None:
        temp_f = self.temperature("F")
        rh = self.relative_humidity()
        if rh is None:
            return None
        heat_index = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (rh * 0.094))
        if heat_index >= 80:
            heat_index = (
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
            if rh < 13.0 and temp_f >= 80.0 and temp_f <= 112.0:
                heat_index -= ((13 - rh) / 4) * math.sqrt(
                    (17 - abs(temp_f - 95.0)) / 17
                )
            elif rh > 85 and temp_f >= 80.0 and temp_f <= 87:
                heat_index += ((rh - 85) / 10) * ((87 - temp_f) / 5)
        if unit == "F":
            return round(heat_index, 1)
        return round((temp_f - 32) * 5 / 9, 1)

    def wet_bulb(self, unit: str = "C") -> float | None:
        rh = self.relative_humidity()
        if rh is None:
            return None
        wet_bulb = (
            self._temp_c * math.atan(0.151977 * math.sqrt(rh + 8.313659))
            + 0.00391838 * math.sqrt(rh**3) * math.atan(0.023101 * rh)
            - math.atan(rh - 1.676331)
            + math.atan(self._temp_c + rh)
            - 4.686035
        )
        if unit == "C":
            return round(wet_bulb, 1)
        return round((wet_bulb * 9 / 5) + 32, 1)


class MetarWind:
    """Object for parsing wind from a METAR string."""

    _CARDINAL_DIRECTIONS = (
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

    _CARDINAL_DIRECTIONS_ARROW = (
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

    _CARDINAL_DIRECTIONS_ABBR = (
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

    def __init__(self, metar_wind: str) -> None:
        self.undecoded = metar_wind.upper()
        # Default values indicate calm wind
        self.speed: int = 0
        self.gust: int | None = None
        self.direction: int | None = None
        self.variable_directions: tuple[int, int] | None = None
        self.is_low_variable: bool = False
        # Parse the string
        if self.undecoded.startswith("VRB"):
            # Variable wind < 6kts, indicated by keeping direction None
            self.speed = int(self.undecoded[3:5])
        elif self.undecoded != "00000KT":
            groups = self.undecoded.split()
            gust_spl = groups[0][0:-2].split("G")
            self.direction = int(gust_spl[0][0:3])
            self.speed = int(gust_spl[0][3:])
            if len(gust_spl) > 1:
                self.gust = int(gust_spl[1])
            if len(groups) > 1:
                var_spl = groups[1].split("V")
                self.variable_directions = (int(var_spl[0]), int(var_spl[1]))

    def __str__(self) -> str:
        if self.speed == 0:
            return "Calm"
        speed_mph = _to_mph(self.speed)
        if self.direction is None:
            return f"{speed_mph} mph, variable directions"
        card_dir = self.cardinal_direction(self.direction)
        sb = f"{speed_mph} mph, {card_dir}"
        if self.gust is not None:
            gust_mph = _to_mph(self.gust)
            sb = f"{sb}, gusting {gust_mph} mph"
        if self.variable_directions is not None:
            var1 = self.cardinal_direction(self.variable_directions[0])
            var2 = self.cardinal_direction(self.variable_directions[1])
            sb = f"{sb}, variable {var1} {var2}"
        return sb

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}("
        sb = f"{sb}undecoded={_quotify(self.undecoded)},"
        sb = f"{sb} speed={_quotify(self.speed)},"
        sb = f"{sb} gust={_quotify(self.gust)},"
        sb = f"{sb} direction={_quotify(self.direction)},"
        sb = f"{sb} variable_directions={_quotify(self.variable_directions)})"
        return sb

    @staticmethod
    def cardinal_direction(direction: int, style: str = "arrowdir") -> str:
        """
        The cardinal direction of the specified wind direction value.

        Parameters:
        * direction (int) -- Direction of wind in 0-360 degrees.
        * style (str) -- The style of string to be returned. Possible values are
        'short', 'long', 'arrow', 'arrowdir', 'degrees'. Defaults to 'arrowdir'.

        Examples of each style for northeasterly wind:
        * 'short' -> 'NE'
        * 'long' -> 'Northeast'
        * 'arrow' -> '⬋'
        """
        cfstyle = style.casefold()
        cardinal_index = int(round(direction / 22.5) % 16)
        if cfstyle == "arrow":
            return MetarWind._CARDINAL_DIRECTIONS_ARROW[cardinal_index]
        if cfstyle == "long":
            return MetarWind._CARDINAL_DIRECTIONS[cardinal_index]
        if cfstyle == "arrowdir":
            arrow = MetarWind._CARDINAL_DIRECTIONS_ARROW[cardinal_index]
            return f"{arrow}  ({direction}°)"
        if cfstyle == "degrees":
            return f"{direction}°"
        return MetarWind._CARDINAL_DIRECTIONS_ABBR[cardinal_index]


class MetarObservation:
    """
    Python object for storing and decoding a standard METAR message.
    """

    _report_types = {
        "METAR": "Hourly, scheduled report",
        "SPECI": "Special, unscheduled report",
    }

    _report_mods = {
        "AUTO": "Fully automated report",
        "COR": "Correction of previous report",
    }

    _sky_conditions = {
        "CLR": "Clear",
        "SKC": "Clear",
        "FEW": "Few",
        "SCT": "Scattered",
        "BKN": "Broken",
        "OVC": "Overcast",
        "VV": "Vertical Visibility",
    }

    def __init__(self, metar_observation: str) -> None:
        """
        Creates a MetarObservation object with the given observation string.

        Parameters:
        * metar_observation (str) -- Full METAR observation string
        """
        # Split off remarks section
        split_obs = metar_observation.upper().split(" RMK ", maxsplit=2)
        # Split observations out into a list and quickly check length
        observations = split_obs[0].split()
        if len(observations) < 7:
            raise RuntimeError(
                "Invalid METAR string, not enough parts "
                f"({len(observations)} < 7) to be valid."
            )
        # These must be sequential
        self._report_type = self._pop_report_type(observations)
        self._station_id = self._pop_station(observations)
        self._date_time = self._pop_date_time(observations)
        self._report_modifier = self._pop_report_mod(observations)
        self._wind = self._pop_wind(observations)
        self._visibility = self._pop_visibility(observations)
        self._runway_visual_range = self._pop_runway_visual(observations)
        # We now start from the back of the remaining list
        self._altimeter = self._pop_altimeter(observations)
        self._temperature = self._pop_temp_dew(observations)
        self._sky_condition = self._pop_sky_condition(observations)
        # We handled everything but weather phenomena, so combine the rest
        self._weather_phenomena = self._pop_weather_phenom(observations)
        # Remarks
        if len(split_obs) > 1:
            self._remarks: str | None = split_obs[1]
        else:
            self._remarks = None

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    _report_type={_quotify(self._report_type)},\n"
        sb = f"{sb}    _station_id={_quotify(self._station_id)},\n"
        sb = f"{sb}    _date_time={_quotify(self._date_time)},\n"
        sb = f"{sb}    _report_modifier={_quotify(self._report_modifier)},\n"
        sb = f"{sb}    _wind={_quotify(self._wind)},\n"
        sb = f"{sb}    _visibility={_quotify(self._visibility)},\n"
        sb = f"{sb}    _runway_visual_range={_quotify(self._runway_visual_range)},\n"
        sb = f"{sb}    _weather_phenomena={_quotify(self._weather_phenomena)},\n"
        sb = f"{sb}    _sky_condition={_quotify(self._sky_condition)},\n"
        sb = f"{sb}    _temperature={_quotify(self._temperature)},\n"
        sb = f"{sb}    _altimeter={_quotify(self._altimeter)},\n"
        sb = f"{sb}    _remarks={_quotify(self._remarks)},\n"
        return f"{sb})"

    def __str__(self) -> str:
        if self._report_type is not None:
            sb = f"{self._report_type} "
        else:
            sb = ""
        sb = f"{sb}{self._station_id} {self._date_time}"
        if self._report_modifier is not None:
            sb = f"{sb} {self._report_modifier}"
        if self._wind is not None:
            sb = f"{sb} {self._wind}"
        sb = f"{sb} {self._visibility}"
        if self._runway_visual_range is not None:
            sb = f"{sb} {self._runway_visual_range}"
        if self._weather_phenomena is not None:
            sb = f"{sb} {self._weather_phenomena}"
        sb = f"{sb} {self._sky_condition}"
        if self._temperature is not None:
            sb = f"{sb} {self._temperature}"
        sb = f"{sb} {self._altimeter}"
        if self._remarks is not None:
            sb = f"{sb} RMK {self._remarks}"
        return sb

    def report_type(self) -> str:
        """Type of Report (METAR and SPECI)"""
        if self._report_type is None:
            return "Unspecified"
        rtype = self._report_types.get(self._report_type, "Unknown")
        return f"{self._report_type} ({rtype})"

    def station_id(self) -> str:
        """Station Identifier"""
        icao_name = _ICAOS.get(self._station_id)
        if icao_name is None:
            return self._station_id
        return f"{self._station_id} ({icao_name})"

    def date_time(self) -> str:
        """
        Date and Time of Report

        Note: the decoded version of this method will assume that the month
        and year of the data is the current month and year.
        """
        metar_day_of_month = int(self._date_time[0:2])
        metar_hour = int(self._date_time[2:4])
        metar_minute = int(self._date_time[4:6])
        current_dt = datetime.now(tz=timezone.utc)
        metar_dt = datetime(
            year=current_dt.year,
            month=current_dt.month,
            day=metar_day_of_month,
            hour=metar_hour,
            minute=metar_minute,
            tzinfo=timezone.utc,
        )
        delta = round((current_dt - metar_dt).seconds / 60)
        return f"{metar_dt.strftime('%m-%d-%Y %H:%M UTC')} ({delta} minutes ago)"

    def report_modifier(self) -> str:
        """Report Modifier"""
        if self._report_modifier is None:
            return "Unspecified"
        report_mod = self._report_mods.get(self._report_modifier)
        if report_mod is None:
            return self._report_modifier
        return f"{self._report_modifier} ({report_mod})"

    def wind(self) -> str:
        """Wind Group"""
        if self._wind is None:
            return "Unspecified"
        return str(MetarWind(self._wind))

    def visibility(self) -> str:
        """Visibility Group"""
        vis_short = self._visibility[0:-2]
        if vis_short.startswith("M"):
            return f"Less than {_fraction_to_float(vis_short[1:])} mi"
        return f"{_fraction_to_float(vis_short)} mi"

    def runway_visual_range(self) -> str:
        """Runway Visual Range Group"""
        if self._runway_visual_range is None:
            return "Unspecified"
        parts = self._runway_visual_range[1:-2].split("/")
        sb = f"Runway {parts[0]}"
        if "V" not in parts[1]:
            sb = f"{sb} {_rvr_parse(parts[1])}"
        else:
            var_parts = parts[1].split("V")
            sb = (
                f"{sb} varrying between {_rvr_parse(var_parts[0])}"
                f" and {_rvr_parse(var_parts[1])}"
            )
        return sb

    def present_weather(self) -> str:
        """
        Present Weather Group

        TODO: Implement parsing
        """
        if self._weather_phenomena is None:
            return "Unspecified"
        return self._weather_phenomena

    def sky_condition(self) -> str:
        """Sky Condition Group"""
        if self._sky_condition == "CLR" or self._sky_condition == "SKC":
            return "Clear skies"
        sb = ""
        for cond in self._sky_condition.split():
            contraction = self._sky_conditions[cond[0:3]]
            if "/" in cond:
                height = "[below station]"
            else:
                height = f"{int(cond[3:]) * 100}"
            sb = f"{sb}, {contraction} at {height} ft"
        return sb.strip(" ,")

    def temperature(self) -> str:
        """Temperature/Dew Point Group"""
        remarks_temp = self._remarks_temp()
        if remarks_temp is not None:
            return str(MetarTemperature(remarks_temp))
        if self._temperature is not None:
            return str(MetarTemperature(self._temperature))
        return "Unspecified"

    def decode(self) -> str:
        """Decodes the entire observation and outputs a pretty report."""
        return (
            f"{str(self)}\n\n"
            f"Report Type -- {self.report_type()}\n"
            f"Station Identifier -- {self.station_id()}\n"
            f"Timestamp -- {self.date_time()}\n"
            f"Report Modifier -- {self.report_modifier()}\n"
            f"Wind -- {self.wind()}\n"
            f"Visibility -- {self.visibility()}\n"
            f"Runway Visual Range -- {self.runway_visual_range()}\n"
            f"Present Weather -- {self.present_weather()}\n"
            f"Sky Conditions -- {self.sky_condition()}\n"
            f"Temperature -- {self.temperature()}\n"
        )

    def _pop_report_type(self, observations: list[str]) -> str | None:
        if observations[0] in self._report_types:
            return observations.pop(0)
        return None

    def _pop_station(self, observations: list[str]) -> str:
        station_id = observations.pop(0)
        if len(station_id) != 4:
            raise RuntimeError(
                f"Invalid station ID '{station_id}', "
                "should be the 4 character ICAO location id."
            )
        return station_id

    def _pop_date_time(self, observations: list[str]) -> str:
        date_time = observations.pop(0)
        if len(date_time) != 7:
            raise RuntimeError(
                f"Invalid date/time '{date_time}', not 7 ({len(date_time)}) characters."
            )
        if date_time[-1] != "Z":
            raise RuntimeError(f"Invalid date/time '{date_time}', does not end in 'Z'.")
        return date_time

    def _pop_report_mod(self, observations: list[str]) -> str | None:
        if observations[0] in self._report_mods:
            return observations.pop(0)
        return None

    def _pop_wind(self, observations: list[str]) -> str | None:
        if len(observations[0]) < 7:
            return None
        if not observations[0].endswith("KT"):
            return None
        wind_dir_spd = observations.pop(0)
        # If variable wind exists, it needs to be immediatly after
        if len(observations[0]) == 7 and observations[0][3] == "V":
            wind_dir_spd = f"{wind_dir_spd} {observations.pop(0)}"
        return wind_dir_spd

    def _pop_visibility(self, observations: list[str]) -> str:
        visibility = observations.pop(0)
        if not visibility.endswith("SM"):
            # There could be spaces in this group, for fractional numbers
            if observations[0].endswith("SM"):
                visibility = f"{visibility} {observations.pop(0)}"
            else:
                raise RuntimeError(
                    f"Invalid visibility '{visibility}', string does not end in SM."
                )
        return visibility

    def _pop_runway_visual(self, observations: list[str]) -> str | None:
        if observations[0].startswith("R") and observations[0].endswith("FT"):
            return observations.pop(0)
        return None

    def _pop_altimeter(self, observations: list[str]) -> str:
        altimeter = observations.pop()
        if len(altimeter) < 3:
            raise RuntimeError(f"Invalid altimeter '{altimeter}', invalid length.")
        if altimeter[0] != "A":
            raise RuntimeError(
                f"Invalid altimeter '{altimeter}', does not start in 'A'."
            )
        return altimeter

    def _pop_temp_dew(self, observations: list[str]) -> str | None:
        if observations[-1][2] != "/" and observations[-1][3] != "/":
            return None
        return observations.pop()

    def _pop_sky_condition(self, observations: list[str]) -> str:
        sky_condition = ""
        for group in reversed(observations):
            if len(group) < 3:
                break
            if group[0:3] not in self._sky_conditions:
                break
            sky_condition = f"{observations.pop()} {sky_condition}"
        return sky_condition.strip()

    def _pop_weather_phenom(self, observations: list[str]) -> str | None:
        if len(observations) < 1:
            return None
        return " ".join(observations)

    def _remarks_temp(self) -> str | None:
        if self._remarks is None:
            return None
        for remark in self._remarks.split():
            if remark.startswith("T1") or remark.startswith("T0"):
                if len(remark) == 9:
                    if remark[5] == "0" or remark[5] == "1":
                        return remark
        return None

    def _remarks_slp(self) -> str | None:
        if self._remarks is None:
            return None
        for remark in self._remarks.split():
            if remark.startswith("SLP") and len(remark) == 6:
                return remark
        return None


# class MetarRemarks:
#     """
#     Python object for storing and decoding remarks in a standard METAR message.
#     """

#     def __init__(self, metar_remarks: str) -> None:
#         """
#         Creates a MetarRemarks object with the given string of remarks from a
#         standard METAR message.

#         Parameters:
#         * metar_remarks (str) -- METAR remarks
#         """
#         self.remarks = metar_remarks.upper()
#         self.type_of_station = "AO2" if "AO2" in self.remarks else None
#         self.peak_wind = self._get_by_search(self.remarks, "PK WND ")
#         self.wind_shift = self._get_by_search(self.remarks, "WSHFT ")
#         self.tower_visibility = self._get_by_search(self.remarks, "TWR VIS ")
#         self.surface_visibility = self._get_by_search(self.remarks, "SFC VIS ")
#         self.variable_visibility, self.alternate_visibility = self._get_visibilities(
#             self.remarks
#         )
#         self.lightning = self._get_lightning(self.remarks)

#     def __repr__(self) -> str:
#         sb = f"{self.__class__.__name__}("
#         sb = f"{sb}type_of_station={_quotify(self.type_of_station)}"
#         sb = f"{sb}, peak_wind={_quotify(self.peak_wind)}"
#         sb = f"{sb}, wind_shift={_quotify(self.wind_shift)}"
#         sb = f"{sb}, tower_visibility={_quotify(self.tower_visibility)}"
#         sb = f"{sb}, surface_visibility={_quotify(self.surface_visibility)}"
#         sb = f"{sb}, variable_visibility={_quotify(self.variable_visibility)}"
#         sb = f"{sb}, alternate_visibility={_quotify(self.alternate_visibility)}"
#         sb = f"{sb}, lightning={_quotify(self.lightning)}"
#         return f"{sb})"

#     def __str__(self) -> str:
#         return self.remarks

#     def _get_by_search(self, metar_remarks: str, search_str: str) -> str | None:
#         index = metar_remarks.find(search_str)
#         if index == -1:
#             return None
#         index += len(search_str)
#         end_index = metar_remarks[index:].find(" ") + index
#         return metar_remarks[index:end_index]

#     def _get_visibilities(self, metar_remarks: str) -> tuple[str | None, str | None]:
#         # Set both as None by default
#         variable_vis = None
#         alternate_vis = None
#         # Need to loop across the string since the two signatures are similar
#         vis_index = 0
#         while True:
#             vis_index = metar_remarks.find("VIS ", vis_index)
#             if vis_index == -1:
#                 break
#             vis_index += 4
#             rmks_split = metar_remarks[vis_index:].split(maxsplit=2)
#             rmks_len = len(rmks_split)
#             if rmks_len < 1:
#                 break
#             if "V" in rmks_split[0]:
#                 variable_vis = rmks_split[0]
#                 if rmks_len > 1 and _is_fraction(rmks_split[1]):
#                     variable_vis = f"{variable_vis} {rmks_split[1]}"
#             else:
#                 if rmks_len < 2:
#                     continue
#                 alternate_vis = f"{rmks_split[0]} {rmks_split[1]}"
#         return (variable_vis, alternate_vis)

#     def _get_lightning(self, metar_remarks: str) -> str | None:
#         ltg_index = metar_remarks.find("LTG")
#         if ltg_index == -1:
#             return None
#         # Handle special case of automated distant lightning first
#         # Format is LTG DSNT <DIR>
#         if "LTG DSNT " in metar_remarks:
#             end_index = metar_remarks.find(" ", ltg_index + 9)
#             return metar_remarks[ltg_index:end_index]
#         # Handle manual station lightning
#         freq_index = metar_remarks.rfind(" ", 0, ltg_index - 1) + 1
#         if freq_index == 0:
#             return None
#         loc_index = metar_remarks.find(" ", ltg_index) + 1
#         if loc_index == 0:
#             return None
#         end_loc_index = metar_remarks.find(" ", loc_index)
#         if end_loc_index == -1:
#             return metar_remarks[freq_index:]
#         return metar_remarks[freq_index:end_loc_index]
