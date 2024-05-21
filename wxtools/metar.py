"""
Experimenting with parsing METAR data into a python object.
"""

from __future__ import annotations

from .common import quotify


class MetarObservation:
    """
    Python object for storing a METAR/SPECI string. Splits the groups out into
    variables but does no further decoding. str(self) will return the raw coded
    string.
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
