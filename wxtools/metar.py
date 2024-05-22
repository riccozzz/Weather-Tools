"""
Experimenting with parsing METAR data into a python object.
"""

from __future__ import annotations
from datetime import datetime, timezone

from .common import cardinal_direction, quotify, get_icao_name, fraction_str_to_float
from .units import _ALL_UNITS, UnitInfo, convert_unit


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

    def _pop_present_weather(self, observations: list[str]) -> str | None:
        if len(observations) < 1:
            return None
        return " ".join(observations)

    def _remarks_temp(self) -> str | None:
        if self.remarks is None:
            return None
        for remark in self.remarks.split():
            if remark.startswith("T1") or remark.startswith("T0"):
                if len(remark) == 9:
                    if remark[5] == "0" or remark[5] == "1":
                        return remark
        return None

    def _remarks_slp(self) -> str | None:
        if self.remarks is None:
            return None
        for remark in self.remarks.split():
            if remark.startswith("SLP") and len(remark) == 6:
                return remark
        return None

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
            self.wind = MetarWind(self.coded_metar.wind, "mph")
        self.visibility = MetarVisibility(self.coded_metar.visibility)
        # Pressure, temp, sky coverage

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    coded_metar={quotify(self.coded_metar)},\n"
        sb = f"{sb}    station_id={quotify(self.station_id)},\n"
        sb = f"{sb}    station_name={quotify(self.station_name)},\n"
        sb = f"{sb}    timestamp={quotify(self.timestamp)},\n"
        sb = f"{sb}    wind={quotify(self.wind)},\n"
        sb = f"{sb}    visibility={quotify(self.visibility)},\n"
        return f"{sb})"

    def __str__(self) -> str:
        return repr(self)

    @classmethod
    def from_raw_string(cls, metar: str) -> MetarObservations:
        """Constructs a MetarObservations object using just the raw METAR."""
        return cls(CodedMetar(metar))

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

    Possible unit values (case insensitive):
        * 'kt' -- Knots (default)
        * 'mph' -- Miles per hour
        * 'kph' -- Kilometers per hours
        * 'mps' -- Meters per second
    """

    _unit_kts = _ALL_UNITS["knot"]
    _unit_mph = _ALL_UNITS["mile per hour"]
    _unit_mps = _ALL_UNITS["meter per second"]
    _unit_kph = _ALL_UNITS["kilometer per hour"]

    def __init__(self, metar_wind_group: str, unit: str = "kt") -> None:
        self.wind_group = metar_wind_group.upper()
        # Default values indicate calm wind
        self.speed: float = 0
        self.gust: float | None = None
        self.direction: int | None = None
        self.variable_directions: tuple[int, int] | None = None
        # Parse the string
        if self.wind_group.startswith("VRB"):
            # Variable wind < 6kts, indicated by keeping direction None
            self.speed = float(self.wind_group[3:5])
        elif self.wind_group != "00000KT":
            groups = self.wind_group.split()
            gust_spl = groups[0][0:-2].split("G")
            self.direction = int(gust_spl[0][0:3])
            self.speed = float(gust_spl[0][3:])
            if len(gust_spl) > 1:
                self.gust = float(gust_spl[1])
            if len(groups) > 1:
                var_spl = groups[1].split("V")
                self.variable_directions = (int(var_spl[0]), int(var_spl[1]))
        # Set the unit and convert if required
        self._speed_unit = self._unit_kts
        self._convert_unit(self._uinfo_from_str(unit))

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    wind_group={quotify(self.wind_group)},\n"
        sb = f"{sb}    speed={quotify(self.speed)},\n"
        sb = f"{sb}    gust={quotify(self.gust)},\n"
        sb = f"{sb}    direction={quotify(self.direction)},\n"
        sb = f"{sb}    variable_directions={quotify(self.variable_directions)},\n"
        sb = f"{sb}    speed_unit={quotify(self.speed_unit)},\n"
        return f"{sb})"

    def __str__(self) -> str:
        return self.description()

    def _uinfo_from_str(self, unit: str) -> UnitInfo:
        unit_str = unit.lower().strip()
        if unit_str == "kt":
            return self._unit_kts
        if unit_str == "mph":
            return self._unit_mph
        if unit_str == "kph":
            return self._unit_kph
        if unit_str == "mps":
            return self._unit_mps
        raise RuntimeError(f"Invalid unit specified: '{unit}'")

    def _convert_unit(self, to_unit: UnitInfo) -> None:
        if to_unit == self._speed_unit:
            return
        self.speed = convert_unit(self.speed, self._speed_unit, to_unit)
        if self.gust is not None:
            self.gust = convert_unit(self.gust, self._speed_unit, to_unit)
        self._speed_unit = to_unit

    def description(self) -> str:
        """
        Outputs a human readable description of the decoded wind observations.
        """
        if self.speed == 0 and self.gust is None:
            return "Calm"
        if self.direction is None:
            return f"{self.speed:.0f} {self.speed_unit} from varying directions"
        sb = f"{self.speed:.0f} {self.speed_unit}"
        sb = f"{sb} from the {cardinal_direction(self.direction)}"
        if self.gust is not None:
            sb = f"{sb}, gusting {self.gust:.0f} {self.speed_unit}"
        if self.variable_directions is not None:
            v1 = cardinal_direction(self.variable_directions[0])
            v2 = cardinal_direction(self.variable_directions[1])
            sb = f"{sb}, varying from {v1} and {v2}"
        return sb

    @property
    def speed_unit(self) -> UnitInfo:
        """
        The current unit (UnitInfo object) of the wind speeds. If set to one
        of the below strings, will convert the values in place and set the new
        UnitInfo appropriately.

        Possible set values (case insensitive):
        * 'kt' -- Knots (default from METAR)
        * 'mph' -- Miles per hour
        * 'kph' -- Kilometers per hours
        * 'mps' -- Meters per second
        """
        return self._speed_unit

    @speed_unit.setter
    def speed_unit(self, unit: str) -> None:
        to_unit = self._uinfo_from_str(unit)
        from_unit = self._speed_unit
        self.speed = convert_unit(self.speed, from_unit, to_unit)
        if self.gust is not None:
            self.gust = convert_unit(self.gust, from_unit, to_unit)
        self._speed_unit = to_unit

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

    Possible unit values (case insensitive):
        * 'miles' -- Statuate miles (default)
        * 'ft' -- Feet
    """

    _unit_miles = _ALL_UNITS["mile us statute"]
    _unit_ft = _ALL_UNITS["foot"]

    def __init__(self, metar_vis_group: str, unit: str = "miles") -> None:
        self.visibility_group = metar_vis_group.upper().strip()
        if self.visibility_group[0] == "M":
            self.distance = fraction_str_to_float(self.visibility_group[1:-2])
            self.less_than_flag = True
        else:
            self.distance = fraction_str_to_float(self.visibility_group[0:-2])
            self.less_than_flag = False
        # Set the unit and convert if required
        self._unit = self._unit_miles
        self._convert_unit(self._uinfo_from_str(unit))

    def __repr__(self) -> str:
        sb = f"{self.__class__.__name__}(\n"
        sb = f"{sb}    visibility_group={quotify(self.visibility_group)},\n"
        sb = f"{sb}    distance={quotify(self.distance)},\n"
        sb = f"{sb}    less_than_flag={quotify(self.less_than_flag)},\n"
        sb = f"{sb}    unit={quotify(self.unit)},\n"
        return f"{sb})"

    def __str__(self) -> str:
        return self.description()

    def _uinfo_from_str(self, unit: str) -> UnitInfo:
        unit_str = unit.lower().strip()
        if unit_str == "miles":
            return self._unit_miles
        if unit_str == "ft":
            return self._unit_ft
        raise RuntimeError(f"Invalid unit specified: '{unit}'")

    def _convert_unit(self, to_unit: UnitInfo) -> None:
        if to_unit == self._unit:
            return
        self.distance = convert_unit(self.distance, self._unit, to_unit)
        self._unit = to_unit

    def description(self) -> str:
        """
        Outputs a human readable description of the decoded wind observations.
        """
        distance_str = f"{self.distance:.2f}"
        if self.unit.label == "foot":
            distance_str = f"{self.distance:.0f}"
        if self.less_than_flag:
            return f"Less than {distance_str} {self.unit}"
        return f"{distance_str} {self.unit}"

    @property
    def unit(self) -> UnitInfo:
        """
        The current unit (UnitInfo object) of the wind speeds. If set to one
        of the below strings, will convert the values in place and set the new
        UnitInfo appropriately.

        Possible unit values (case insensitive):
            * 'miles' -- Statuate miles (default)
            * 'ft' -- Feet
        """
        return self._unit

    @unit.setter
    def unit(self, unit: str) -> None:
        to_unit = self._uinfo_from_str(unit)
        from_unit = self._unit
        self.distance = convert_unit(self.distance, from_unit, to_unit)
        self._unit = to_unit

    @classmethod
    def from_coded_metar(cls, metar: CodedMetar) -> MetarVisibility:
        """
        Creates a decoded MetarVisibility object from a CodedMetar. This will
        simply use CodedMetar.visibility to construct the object.
        """
        return cls(metar.visibility)
