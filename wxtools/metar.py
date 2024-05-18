"""
Experimenting with parsing METAR data into a python object.
"""

from __future__ import annotations
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any

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


class MetarWind:
    """Dataclass for grouping of various wind observations."""

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
        """
        VRB04KT
        27020G35KT 020V120
        00000KT
        """
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
        "FEW": "Few",
        "SCT": "Scattered",
        "BKN": "Broken",
        "OVC": "Overcast",
        "VV": "Vertical Visibility",
        "SKC": "Clear",
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
        sb = f"{sb} {self._wind} {self._visibility}"
        if self._runway_visual_range is not None:
            sb = f"{sb} {self._runway_visual_range}"
        if self._weather_phenomena is not None:
            sb = f"{sb} {self._weather_phenomena}"
        sb = f"{sb} {self._sky_condition} {self._temperature} {self._altimeter}"
        if self._remarks is not None:
            sb = f"{sb} RMK {self._remarks}"
        return sb

    def report_type(self) -> str:
        if self._report_type is None:
            return "Unspecified"
        rtype = self._report_types.get(self._report_type, "Unknown")
        return f"{self._report_type} ({rtype})"

    def station_id(self) -> str:
        icao_name = _ICAOS.get(self._station_id)
        if icao_name is None:
            return self._station_id
        return f"{self._station_id} ({icao_name})"

    def date_time(self) -> str:
        """
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
        if self._report_modifier is None:
            return "Unspecified"
        report_mod = self._report_mods.get(self._report_modifier)
        if report_mod is None:
            return self._report_modifier
        return f"{self._report_modifier} ({report_mod})"

    def wind(self) -> str:
        return str(MetarWind(self._wind))

    def visibility(self) -> str:
        vis_short = self._visibility[0:-2]
        if vis_short.startswith("M"):
            return f"Less than {_fraction_to_float(vis_short[1:])} mi"
        return f"{_fraction_to_float(vis_short)} mi"

    def runway_visual_range(self) -> str:
        if self._runway_visual_range is None:
            return "Unspecified"
        return ""

    def decode(self) -> str:
        return (
            f"Report Type -- {self.report_type()}\n"
            f"Station Identifier -- {self.station_id()}\n"
            f"Timestamp -- {self.date_time()}\n"
            f"Report Modifier -- {self.report_modifier()}\n"
            f"Wind -- {self.wind()}\n"
            f"Visibility -- {self.visibility()}\n"
            f"Runway Visual Range -- {self.runway_visual_range()}\n"
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

    def _pop_wind(self, observations: list[str]) -> str:
        wind_dir_spd = observations.pop(0)
        if len(wind_dir_spd) < 7:
            raise RuntimeError(
                f"Invalid wind speed/direction '{wind_dir_spd}',"
                f" length is too short ({len(wind_dir_spd)} < 7)."
            )
        if not wind_dir_spd.endswith("KT"):
            raise RuntimeError(
                f"Invalid wind speed/direction '{wind_dir_spd}',"
                " string does not end in KT."
            )
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
        if observations[0].endswith("FT"):
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

    def _pop_temp_dew(self, observations: list[str]) -> str:
        temp_dew = observations.pop()
        if temp_dew[2] != "/" and temp_dew[3] != "/":
            raise RuntimeError(
                f"Invalid temperature/dew point '{temp_dew}', '/' in wrong position."
            )
        return temp_dew

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
