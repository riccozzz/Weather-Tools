"""Random work in progress stuff for development"""

from __future__ import annotations
from typing import Any

import requests


def aviationweather_get_metar(station_id: str) -> str:
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
            raise RuntimeError(f"Could not retrieve data for '{station_id}.'")
        return metar_raw
    except requests.RequestException as ex:
        raise RuntimeError(ex) from None


def aviationweather_get_info(station_id: str) -> dict[str, Any]:
    """Returns the latest info from the given station."""

    url = (
        "https://aviationweather.gov/api/data/stationinfo"
        f"?ids={station_id}&format=json"
    )
    try:
        resp = requests.get(url=url, timeout=5)
        resp.raise_for_status()
        jdata = resp.json()
        if isinstance(jdata, list):
            if len(jdata) > 0 and isinstance(jdata[0], dict):
                return jdata[0]
        raise RuntimeError("Unknown payload data in response.")
    except requests.RequestException as ex:
        raise RuntimeError(ex) from None


def avwx_get_metar(station_id: str) -> str:
    """Returns the latest METAR from the given station."""
    avwx_url = f"https://avwx.rest/api/metar/{station_id}?filter=raw"
    headers = {"Authorization": "2PxTWvsyTeLuyv4AIoemQMflKXEE3MFy_Ubl58rtVs0"}
    try:
        resp = requests.get(url=avwx_url, timeout=5, headers=headers)
        if resp.status_code >= 400:
            jdata = resp.json()
            if isinstance(jdata, dict):
                if "error" in jdata:
                    raise RuntimeError(jdata["error"])
        resp.raise_for_status()
        jdata = resp.json()
        if isinstance(jdata, dict):
            if "raw" in jdata:
                if isinstance(jdata["raw"], str):
                    return jdata["raw"]
        raise RuntimeError("Unknown payload data in response.")
    except requests.RequestException as ex:
        raise RuntimeError(ex) from None


def synopticdata_get(station_id: str) -> str:
    """Returns the latest METAR from the given station."""
    token = "a75410c49a0a4814ac9839408dd30ecf"
    params = f"&stid={station_id}&vars=metar&hfmetars=1&output=json"
    url = f"https://api.synopticdata.com/v2/stations/latest?token={token}{params}"
    try:
        resp = requests.get(url=url, timeout=5)
        resp.raise_for_status()
        jdata = resp.json()
        summary = jdata.get("SUMMARY")
        if not isinstance(summary, dict):
            raise RuntimeError("No summary found in data.")
        response_code = summary.get("RESPONSE_CODE")
        if not isinstance(response_code, int):
            raise RuntimeError("No response code found in data.")
        if response_code == 2:
            response = summary.get("RESPONSE_MESSAGE")
            if isinstance(response, str) and len(response) > 0:
                raise RuntimeError(response)
            raise RuntimeError("Unknown error.")
        metar = jdata["STATION"][0]["OBSERVATIONS"]["metar_value_1"]["value"]
        if not isinstance(metar, str):
            raise RuntimeError("Invalid metar string (data type).")
        return metar.strip().upper()
    except requests.RequestException as ex:
        raise RuntimeError(ex) from None


# def _rvr_parse(reportable_value: str) -> str:
#     if reportable_value[0] == "M":
#         return f"< {int(reportable_value[1:])} ft"
#     if reportable_value[0] == "P":
#         return f"> {int(reportable_value[1:])} ft"
#     return f"{int(reportable_value)} ft"

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
