"""
Experimenting with parsing METAR data into a python object.
"""

from __future__ import annotations
from datetime import datetime, timezone
from dataclasses import dataclass

from .common import cardinal_direction, quotify, get_icao_name, fraction_str_to_float
from . import calculators


def _remarks_slp(metar_remarks: str) -> str | None:
    for remark in metar_remarks.upper().split():
        if remark.startswith("SLP") and len(remark) == 6:
            return remark
    return None


def _remarks_temp(metar_remarks: str) -> str | None:
    for remark in metar_remarks.upper().split():
        if remark.startswith("T1") or remark.startswith("T0"):
            if len(remark) == 9:
                if remark[5] == "0" or remark[5] == "1":
                    return remark
    return None


@dataclass
class SkyLayer:
    """Dataclass for a sky condition layer from a METAR."""

    descriptions = {
        "CLR": "Clear",
        "SKC": "Clear",
        "FEW": "Few",
        "SCT": "Scattered",
        "BKN": "Broken",
        "OVC": "Overcast",
        "VV": "Vertical Visibility",
    }

    coverage: str
    height_ft: int | None
    cb_flag: bool = False

    @property
    def coverage_description(self) -> str:
        """A descriptive string for the corresponding METAR abbreviation."""
        return self.descriptions[self.coverage]


class CodedMetar:
    """
    Python object for storing a METAR/SPECI string. Splits the groups out into
    variables but does no further parsing. str(self) will return the raw coded
    string back. Each group can be accessed via variables, which will be None
    if they are not present.
    """

    _report_types = {
        "METAR": "Hourly, scheduled report",
        "SPECI": "Special, unscheduled report",
    }

    _report_mods = {
        "AUTO": "Fully automated report",
        "COR": "Correction of previous report",
    }

    def __init__(self, metar_observation: str) -> None:
        """
        Creates a CodedMetar object with the given observation string.

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
        self.report_type = self._pop_report_type(observations)
        self.station_id = self._pop_station(observations)
        self.date_time = self._pop_date_time(observations)
        self.report_modifier = self._pop_report_mod(observations)
        self.wind = self._pop_wind(observations)
        self.visibility = self._pop_visibility(observations)
        self.runway_visual_range = self._pop_runway_visual(observations)
        # We now start from the back of the remaining list
        self.altimeter = self._pop_altimeter(observations)
        self.temperature = self._pop_temp_dew(observations)
        self.sky_condition = self._pop_sky_condition(observations)
        # We handled everything but weather phenomena, so combine the rest
        self.present_weather = self._pop_present_weather(observations)
        # Just keep remarks as a single unsplit string
        self.remarks = None
        if len(split_obs) > 1:
            self.remarks = split_obs[1]

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    report_type={quotify(self.report_type)},\n"
        sb = f"{sb}    station_id={quotify(self.station_id)},\n"
        sb = f"{sb}    date_time={quotify(self.date_time)},\n"
        sb = f"{sb}    report_modifier={quotify(self.report_modifier)},\n"
        sb = f"{sb}    wind={quotify(self.wind)},\n"
        sb = f"{sb}    visibility={quotify(self.visibility)},\n"
        sb = f"{sb}    runway_visual_range={quotify(self.runway_visual_range)},\n"
        sb = f"{sb}    present_weather={quotify(self.present_weather)},\n"
        sb = f"{sb}    sky_condition={quotify(self.sky_condition)},\n"
        sb = f"{sb}    temperature={quotify(self.temperature)},\n"
        sb = f"{sb}    altimeter={quotify(self.altimeter)},\n"
        sb = f"{sb}    remarks={quotify(self.remarks)},\n"
        return f"{sb})"

    def __str__(self) -> str:
        if self.report_type is not None:
            sb = f"{self.report_type} "
        else:
            sb = ""
        sb = f"{sb}{self.station_id} {self.date_time}"
        if self.report_modifier is not None:
            sb = f"{sb} {self.report_modifier}"
        if self.wind is not None:
            sb = f"{sb} {self.wind}"
        if self.visibility is not None:
            sb = f"{sb} {self.visibility}"
        if self.runway_visual_range is not None:
            sb = f"{sb} {self.runway_visual_range}"
        if self.present_weather is not None:
            sb = f"{sb} {self.present_weather}"
        sb = f"{sb} {self.sky_condition}"
        if self.temperature is not None:
            sb = f"{sb} {self.temperature}"
        sb = f"{sb} {self.altimeter}"
        if self.remarks is not None:
            sb = f"{sb} RMK {self.remarks}"
        return sb

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

    def _pop_visibility(self, observations: list[str]) -> str | None:
        if not observations[0].endswith("SM"):
            if not observations[1].endswith("SM"):
                return None
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
            if group[0:3] not in SkyLayer.descriptions:
                break
            sky_condition = f"{observations.pop()} {sky_condition}"
        return sky_condition.strip()

    def _pop_present_weather(self, observations: list[str]) -> str | None:
        if len(observations) < 1:
            return None
        return " ".join(observations)

    def decode(self) -> MetarObservations:
        """
        Uses this METAR and returns a MetarObservations object, which will aid
        in decoding the string.
        """
        return MetarObservations(self)


class MetarObservations:
    """
    Object for a observation stations data, specifically extracted and decoded
    from a METAR.
    """

    def __init__(self, coded_metar: CodedMetar) -> None:
        self.coded_metar = coded_metar
        self.station_id = self.coded_metar.station_id
        self.station_name = get_icao_name(self.coded_metar.station_id)
        self.timestamp = self._parse_date_time(self.coded_metar.date_time)
        self.wind = None
        if self.coded_metar.wind is not None:
            self.wind = MetarWind(self.coded_metar.wind)
        self.visibility = None
        if self.coded_metar.visibility is not None:
            self.visibility = MetarVisibility(self.coded_metar.visibility)
        self.pressure = MetarPressure.from_coded_metar(self.coded_metar)
        self.temperature = MetarTemperature.from_coded_metar(self.coded_metar)
        self.sky_conditions = MetarSkyCondition(self.coded_metar.sky_condition)

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    coded_metar={quotify(self.coded_metar)},\n"
        sb = f"{sb}    station_id={quotify(self.station_id)},\n"
        sb = f"{sb}    station_name={quotify(self.station_name)},\n"
        sb = f"{sb}    timestamp={quotify(self.timestamp)},\n"
        sb = f"{sb}    wind={quotify(self.wind)},\n"
        sb = f"{sb}    visibility={quotify(self.visibility)},\n"
        sb = f"{sb}    pressure={quotify(self.pressure)},\n"
        sb = f"{sb}    temperature={quotify(self.temperature)},\n"
        sb = f"{sb}    sky_conditions={quotify(self.sky_conditions)}\n"
        return f"{sb})"

    def __str__(self) -> str:
        return self.report()

    @classmethod
    def from_raw_string(cls, metar: str) -> MetarObservations:
        """Constructs a MetarObservations object using just the raw METAR."""
        return cls(CodedMetar(metar))

    def report(self) -> str:
        """Creates a full human readable report."""
        # Header, station id and name
        if self.station_name is not None:
            sb = f"{self.station_id} ({self.station_name})"
        else:
            sb = self.station_id
        # Raw METAR
        sb = f"{sb}\n\nMETAR (via aviationweather.gov):\n'{self.coded_metar}'"
        # Timestamp (acts as data header)
        ts = self.timestamp.strftime("%B %d, %Y at %H:%M UTC")
        sb = f"{sb}\n\nObserved on {ts} ({self._minutes_since()} minutes ago)\n"
        # Wind
        if self.wind is None:
            sb = f"{sb}\nWind: Unspecified"
        else:
            sb = f"{sb}\nWind: {self.wind}"
        # Visibility
        if self.visibility is None:
            sb = f"{sb}\nVisibility: Unspecified"
        else:
            sb = f"{sb}\nVisibility: {self.visibility}"
        # Pressure
        sb = f"{sb}\nPressure:\n"
        sb = f"{sb}  Altimeter -- {self.pressure.altimeter_inhg:.2f} inHg"
        if self.pressure.sea_level_hpa is not None:
            sb = f"{sb}  Sea Level -- {self.pressure.sea_level_hpa:.1f} hPa"
        else:
            sb = f"{sb}  Sea Level -- Unspecified"
        # Temperature
        sb = f"{sb}\nTemperature:\n"
        if self.temperature.temperature_c is None:
            sb = f"{sb}  Unspecified"
        else:
            # Air temperature
            temp_str = "Unspecified"
            if self.temperature.temperature_c is not None:
                temp_str = f"{self.temperature.temperature_c:.1f} °C"
            sb = f"{sb}  Air Temp -- {temp_str}"
            # Dew point
            temp_str = "Unspecified"
            if self.temperature.dew_point_c is not None:
                temp_str = f"{self.temperature.dew_point_c:.1f} °C"
                sb = f"{sb}\n  Dew Point -- {temp_str}"
                # Relative humidity
                sb = f"{sb}\n  Relative Humidity -- "
                sb = f"{sb}{self.temperature.relative_humidity:.0f}%"
                # Wet bulb
                temp_str = f"{self.temperature.wet_bulb_c:.1f} °C"
                sb = f"{sb}\n  Wet Bulb -- {temp_str}"
                # Wind chill/heat index
                if self.temperature.temperature_c is not None:
                    if self.temperature.temperature_c <= 10:
                        wspeed = 0.0
                        if self.wind is not None:
                            wspeed = self.wind.speed_kt
                        wc_c = calculators.wind_chill(
                            temperature=self.temperature.temperature_c,
                            wind_speed=wspeed,
                            temp_unit="C",
                            wind_unit="kt",
                        )
                        sb = f"{sb}\n  Wind Chill -- {wc_c:.1f} °C"
                    else:
                        temp_str = f"{self.temperature.heat_index_c:.1f} °C"
                        sb = f"{sb}\n  Heat Index -- {temp_str}"
        # Sky cover
        sb = f"{sb}\nSky Cover:\n"
        if (
            self.sky_conditions.sky_conditions is None
            or len(self.sky_conditions.sky_conditions) < 1
        ):
            sb = f"{sb}  Clear skies\n"
        else:
            for cond in self.sky_conditions.sky_conditions:
                desc = cond.coverage_description
                if cond.height_ft is not None:
                    height_str = f"at {cond.height_ft:.0f} ft"
                    if cond.cb_flag:
                        height_str = f"{height_str} (Cumulonimbus)"
                else:
                    height_str = "below station"
                sb = f"{sb}  {desc} {height_str}\n"
        return sb

    def _parse_date_time(self, date_group: str) -> datetime:
        """
        Note: the decoded version of this method will assume that the month
        and year of the data is the current month and year.
        """
        metar_day_of_month = int(date_group[0:2])
        metar_hour = int(date_group[2:4])
        metar_minute = int(date_group[4:6])
        current_dt = datetime.now(tz=timezone.utc)
        metar_dt = datetime(
            year=current_dt.year,
            month=current_dt.month,
            day=metar_day_of_month,
            hour=metar_hour,
            minute=metar_minute,
            tzinfo=timezone.utc,
        )
        return metar_dt

    def _minutes_since(self) -> int:
        seconds = (datetime.now(tz=timezone.utc) - self.timestamp).seconds
        return round(seconds / 60)


class MetarWind:
    """
    Object for parsing/decoding the wind group from a coded METAR.
    """

    def __init__(self, metar_wind_group: str) -> None:
        self.wind_group = metar_wind_group.upper()
        # Default values indicate calm wind
        self.speed_kt: float = 0
        self.gust_kt: float | None = None
        self.direction: int | None = None
        self.variable_directions: tuple[int, int] | None = None
        # Parse the string
        if self.wind_group.startswith("VRB"):
            # Variable wind < 6kts, indicated by keeping direction None
            self.speed_kt = float(self.wind_group[3:5])
        elif self.wind_group != "00000KT":
            groups = self.wind_group.split()
            gust_spl = groups[0][0:-2].split("G")
            self.direction = int(gust_spl[0][0:3])
            self.speed_kt = float(gust_spl[0][3:])
            if len(gust_spl) > 1:
                self.gust_kt = float(gust_spl[1])
            if len(groups) > 1:
                var_spl = groups[1].split("V")
                self.variable_directions = (int(var_spl[0]), int(var_spl[1]))

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    wind_group={quotify(self.wind_group)},\n"
        sb = f"{sb}    speed_kt={quotify(self.speed_kt)},\n"
        sb = f"{sb}    gust_kt={quotify(self.gust_kt)},\n"
        sb = f"{sb}    direction={quotify(self.direction)},\n"
        sb = f"{sb}    variable_directions={quotify(self.variable_directions)},\n"
        return f"{sb})"

    def __str__(self) -> str:
        return self.description()

    def description(self) -> str:
        """
        Outputs a human readable description of the decoded wind observations.
        """
        if self.speed_kt == 0 and self.gust_kt is None:
            return "Calm"
        if self.direction is None:
            return f"{self.speed_kt:.0f} kt from varying directions"
        sb = f"{self.speed_kt:.0f} kt"
        sb = f"{sb} from the {cardinal_direction(self.direction)}"
        if self.gust_kt is not None:
            sb = f"{sb}, gusting {self.gust_kt:.0f} kt"
        if self.variable_directions is not None:
            v1 = cardinal_direction(self.variable_directions[0])
            v2 = cardinal_direction(self.variable_directions[1])
            sb = f"{sb}, varying from {v1} and {v2}"
        return sb

    @classmethod
    def from_coded_metar(cls, metar: CodedMetar) -> MetarWind | None:
        """
        Creates a decoded MetarWind object from a CodedMetar. This will simply
        use CodedMetar.wind to construct the object. If wind is not present,
        this method will return None.
        """
        if metar.wind is None:
            return None
        return cls(metar.wind)


class MetarVisibility:
    """
    Object for parsing/decoding the visibility group from a coded METAR.
    """

    def __init__(self, metar_vis_group: str) -> None:
        self.visibility_group = metar_vis_group.upper().strip()
        if self.visibility_group[0] == "M":
            self.distance_mi = fraction_str_to_float(self.visibility_group[1:-2])
            self.less_than_flag = True
        else:
            self.distance_mi = fraction_str_to_float(self.visibility_group[0:-2])
            self.less_than_flag = False

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    visibility_group={quotify(self.visibility_group)},\n"
        sb = f"{sb}    distance_mi={quotify(self.distance_mi)},\n"
        sb = f"{sb}    less_than_flag={quotify(self.less_than_flag)},\n"
        return f"{sb})"

    def __str__(self) -> str:
        return self.description()

    def description(self) -> str:
        """
        Outputs a human readable description of the decoded wind observations.
        """
        if self.less_than_flag:
            return f"Less than {self.distance_mi:.2f} mi"
        return f"{self.distance_mi:.2f} mi"

    @classmethod
    def from_coded_metar(cls, metar: CodedMetar) -> MetarVisibility | None:
        """
        Creates a decoded MetarVisibility object from a CodedMetar. This will
        simply use CodedMetar.visibility to construct the object.
        """
        if metar.visibility is None:
            return None
        return cls(metar.visibility)


class MetarPressure:
    """
    Object for parsing/decoding the altimeter/pressure groups from a coded
    METAR.
    """

    def __init__(
        self, metar_altimeter_group: str, metar_slp_remark: str | None = None
    ) -> None:
        # Altimeter always exists and always inHg
        self.altimeter_group = metar_altimeter_group.upper().strip()
        self.altimeter_inhg = float(
            f"{self.altimeter_group[1:3]}.{self.altimeter_group[3:5]}"
        )
        # SLP in remarks if present
        self.remarks_slp = None
        if metar_slp_remark is not None:
            self.remarks_slp = metar_slp_remark.upper().strip()
        self.sea_level_hpa = self._parse_slp()

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    altimeter_group={quotify(self.altimeter_group)},\n"
        sb = f"{sb}    remarks_slp={quotify(self.remarks_slp)},\n"
        sb = f"{sb}    altimeter_inhg={quotify(self.altimeter_inhg)},\n"
        sb = f"{sb}    sea_level_hpa={quotify(self.sea_level_hpa)},\n"
        return f"{sb})"

    def __str__(self) -> str:
        return self.description()

    def _parse_slp(self) -> float | None:
        if self.remarks_slp is None:
            return None
        slp_only = self.remarks_slp[3:]
        if slp_only == "NO":
            return None
        if "/" in slp_only:
            return None
        if slp_only[0] in ("0", "1", "2", "3", "4", "5"):
            slp_only = f"10{slp_only[0:2]}.{slp_only[2]}"
        else:
            slp_only = f"9{slp_only[0:2]}.{slp_only[2]}"
        return float(slp_only)

    def description(self) -> str:
        """
        Outputs a human readable description of the decoded wind observations.
        """
        sb = f"Altimeter {self.altimeter_inhg:.2f} inHg"
        if self.sea_level_hpa is not None:
            sb = f"{sb}, SLP {self.sea_level_hpa:.1f} hPa"
        return sb

    @classmethod
    def from_coded_metar(cls, metar: CodedMetar) -> MetarPressure:
        """
        Creates a decoded MetarPressure object from a CodedMetar.
        """
        slp_from_remarks = None
        if metar.remarks is not None:
            slp_from_remarks = _remarks_slp(metar.remarks)
        return cls(metar.altimeter, slp_from_remarks)


class MetarTemperature:
    """
    Object for parsing/decoding the temperature group from a coded METAR.
    """

    def __init__(
        self, metar_temp_group: str | None, metar_temp_remark: str | None
    ) -> None:
        self.temperature_group = (
            None if metar_temp_group is None else metar_temp_group.upper().strip()
        )
        self.temperature_remarks = (
            None if metar_temp_remark is None else metar_temp_remark.upper().strip()
        )
        self.temperature_c = None
        self.dew_point_c = None
        if self.temperature_remarks is not None:
            # Remarks group
            self.temperature_c = int(self.temperature_remarks[2:5]) / 10
            if self.temperature_remarks[1] == "1":
                self.temperature_c *= -1
            self.dew_point_c = int(self.temperature_remarks[6:9]) / 10
            if self.temperature_remarks[5] == "1":
                self.dew_point_c *= -1
        elif self.temperature_group is not None:
            # Normal temperature group
            parts = self.temperature_group.replace("M", "-").split("/")
            self.temperature_c = float(parts[0])
            if len(parts) > 1 and len(parts[1]) > 0:
                self.dew_point_c = float(parts[1])
        # If we have dew point, we can calculate RH, HI, and WB
        self.relative_humidity = None
        self.heat_index_c = None
        self.wet_bulb_c = None
        if self.temperature_c is not None and self.dew_point_c is not None:
            self.relative_humidity = calculators.relative_humidity(
                self.temperature_c, self.dew_point_c, unit="C"
            )
            self.heat_index_c = calculators.heat_index(
                self.temperature_c, self.relative_humidity, unit="C"
            )
            self.wet_bulb_c = calculators.wet_bulb(
                self.temperature_c, self.relative_humidity, unit="C"
            )

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    temperature_group={quotify(self.temperature_group)},\n"
        sb = f"{sb}    temperature_remarks={quotify(self.temperature_remarks)},\n"
        sb = f"{sb}    temperature_c={quotify(self.temperature_c)},\n"
        sb = f"{sb}    dew_point_c={quotify(self.dew_point_c)},\n"
        sb = f"{sb}    relative_humidity={quotify(self.relative_humidity)},\n"
        sb = f"{sb}    heat_index_c={quotify(self.heat_index_c)},\n"
        sb = f"{sb}    wet_bulb_c={quotify(self.wet_bulb_c)},\n"
        return f"{sb})"

    def __str__(self) -> str:
        return self.description()

    def description(self) -> str:
        """
        Outputs a human readable description of the decoded wind observations.
        """
        if self.temperature_c is None:
            return "Unspecified"
        sb = f"{self.temperature_c:.1f} °C"
        if self.dew_point_c is not None:
            sb = f"{sb}, DP {self.dew_point_c:.1f} °C"
        if self.heat_index_c is not None:
            sb = f"{sb}, HI {self.heat_index_c:.1f} °C"
        if self.wet_bulb_c is not None:
            sb = f"{sb}, WB {self.wet_bulb_c:.1f} °C"
        return sb

    @classmethod
    def from_coded_metar(cls, metar: CodedMetar) -> MetarTemperature:
        """
        Creates a decoded MetarTemperature object from a CodedMetar.
        """
        if metar.remarks is not None:
            return cls(metar.temperature, _remarks_temp(metar.remarks))
        return cls(metar.temperature, None)


class MetarSkyCondition:
    """
    Object for parsing/decoding the sky condition group from a coded METAR.
    """

    def __init__(self, metar_sky_group: str) -> None:
        self.sky_condition_group = metar_sky_group.upper().strip()
        self.sky_conditions = self._sky_metar_parse()

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    sky_condition_group={quotify(self.sky_condition_group)},\n"
        sb = f"{sb}    sky_conditions={quotify(self.sky_conditions)},\n"
        return f"{sb})"

    def __str__(self) -> str:
        return self.description()

    def _sky_metar_parse(self) -> list[SkyLayer] | None:
        if self.sky_condition_group in ("CLR", "SKC"):
            return None
        sky: list[SkyLayer] = []
        for cond in self.sky_condition_group.split():
            contraction = cond[0:3]
            if "/" in cond:
                height = None
            else:
                height = int(cond[3:6]) * 100
            cb_flag = True if "CB" in cond else False
            sky.append(SkyLayer(contraction, height, cb_flag))
        return sky

    def description(self) -> str:
        """
        Outputs a human readable description of the decoded wind observations.
        """
        if self.sky_conditions is None or len(self.sky_conditions) < 1:
            return "Clear skies"
        sb = ""
        for cond in self.sky_conditions:
            desc = cond.coverage_description
            if cond.height_ft is not None:
                height_str = f"at {cond.height_ft:.0f} ft"
                if cond.cb_flag:
                    height_str = f"{height_str} (Cumulonimbus)"
            else:
                height_str = "below station"
            sb = f"{sb}, {desc} {height_str}"
        return sb[2:]

    @classmethod
    def from_coded_metar(cls, metar: CodedMetar) -> MetarSkyCondition:
        """
        Creates a decoded MetarSkyCondition object from a CodedMetar. This
        will simply use CodedMetar.sky_condition to construct the object.
        """
        return cls(metar.sky_condition)
