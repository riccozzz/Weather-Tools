"""
WIP discord bot module

https://message.style/app/editor
"""

import discord
from discord.ext import commands

import discord.ext

from wxtools.calculators import wind_chill
from wxtools.common import cardinal_direction
from wxtools.metar import MetarObservations
from wxtools.wip import aviationweather_get_metar
from wxtools.units import convert_unit, unit_by_label

_UNIT_KT = unit_by_label("knot")
_UNIT_MPH = unit_by_label("mile per hour")
_UNIT_C = unit_by_label("celsius")
_UNIT_F = unit_by_label("fahrenheit")
_UNIT_INHG = unit_by_label("inch of mercury")
_UNIT_HPA = unit_by_label("hectopascal")


def _get_wind_str(obs: MetarObservations) -> str:
    if obs.wind is None:
        return "Unspecified"
    if obs.wind.speed_kt == 0 and obs.wind.gust_kt is None:
        return "Calm"
    speed_mph = convert_unit(obs.wind.speed_kt, _UNIT_KT, _UNIT_MPH)
    if obs.wind.direction is None:
        return f"{speed_mph:.1f} mph from varying directions"
    sb = f"{speed_mph:.1f} mph"
    sb = f"{sb} from the {cardinal_direction(obs.wind.direction)}"
    if obs.wind.gust_kt is not None:
        gust_mph = convert_unit(obs.wind.gust_kt, _UNIT_KT, _UNIT_MPH)
        sb = f"{sb}, gusting {gust_mph:.1f} mph"
    if obs.wind.variable_directions is not None:
        v1 = cardinal_direction(obs.wind.variable_directions[0])
        v2 = cardinal_direction(obs.wind.variable_directions[1])
        sb = f"{sb}, varying from {v1} and {v2}"
    return sb


def _get_vis_str(obs: MetarObservations) -> str:
    if obs.visibility is None:
        return "Unspecified"
    return obs.visibility.description()


def _f_c_str(value_c: float | None) -> str:
    if value_c is None:
        return ""
    value_f = convert_unit(value_c, _UNIT_C, _UNIT_F)
    return f"{value_f:.1f} °F ({value_c:.1f} °C)"


def _get_temp_str(obs: MetarObservations) -> str:
    temp_c = obs.temperature.temperature_c
    if temp_c is None:
        return "Unspecified"
    temp_f = convert_unit(temp_c, _UNIT_C, _UNIT_F)
    sb = f"- Air Temp: {temp_f:.1f} °F ({temp_c:.1f} °C)"

    if obs.temperature.dew_point_c is not None:
        sb = f"{sb}\n- Dew Point: {_f_c_str(obs.temperature.dew_point_c)}"

    if obs.temperature.relative_humidity is not None:
        sb = f"{sb}\n- Relative Humidity: {obs.temperature.relative_humidity:.0f}%"

    if obs.temperature.wet_bulb_c is not None:
        sb = f"{sb}\n- Wet Bulb: {_f_c_str(obs.temperature.wet_bulb_c)}"

    if temp_f <= 50:
        if obs.wind is not None:
            wc_c = wind_chill(temp_c, obs.wind.speed_kt, "C", "KTS")
            sb = f"{sb}\n- Wind Chill: {_f_c_str(wc_c)}"
    elif obs.temperature.heat_index_c is not None:
        sb = f"{sb}\n- Heat Index: {_f_c_str(obs.temperature.heat_index_c)}"

    return sb


def _get_pressure_str(obs: MetarObservations) -> str:
    alt_inhg = obs.pressure.altimeter_inhg
    alt_hpa = convert_unit(alt_inhg, _UNIT_INHG, _UNIT_HPA)
    sb = f"- Altimeter: {alt_hpa:.1f} hPa ({alt_inhg:.2f} inHg)"
    if obs.pressure.sea_level_hpa is not None:
        slp_hpa = obs.pressure.sea_level_hpa
        slp_inhg = convert_unit(slp_hpa, _UNIT_HPA, _UNIT_INHG)
        sb = f"{sb}\n- Sea Level: {slp_hpa:.1f} hPa ({slp_inhg:.2f} inHg)"
    return sb


def _get_skycond_str(obs: MetarObservations) -> str:
    if obs.sky_conditions.sky_conditions is None:
        return "Clear skies"
    if len(obs.sky_conditions.sky_conditions) < 1:
        return "Clear skies"
    sb = ""
    for cond in obs.sky_conditions.sky_conditions:
        desc = cond.coverage_description
        if cond.height_ft is not None:
            height_str = f"at {cond.height_ft:.0f} ft"
            if cond.cb_flag:
                height_str = f"{height_str} (Cumulonimbus)"
        else:
            height_str = "below station"
        sb = f"- {desc} {height_str}\n"
    return sb.strip()


def _color_from_temp(temp_c: float | None) -> discord.Colour:
    if temp_c is None:
        return discord.Colour.from_rgb(90, 90, 90)
    if temp_c < -10:
        return discord.Colour.from_rgb(0, 0, 139)  # Dark Blue
    if -10 <= temp_c < 0:
        return discord.Colour.from_rgb(0, 0, 255)  # Blue
    if 0 <= temp_c < 10:
        return discord.Colour.from_rgb(173, 216, 230)  # Light Blue
    if 10 <= temp_c < 20:
        return discord.Colour.from_rgb(0, 255, 0)  # Green
    if 20 <= temp_c < 30:
        return discord.Colour.from_rgb(255, 255, 0)  # Yellow
    if 30 <= temp_c < 40:
        return discord.Colour.from_rgb(255, 165, 0)  # Orange
    return discord.Colour.from_rgb(255, 0, 0)  # Red


# Create an instance of Intents and enable the ones you need
intents = discord.Intents.default()
intents.message_content = True

# Create a bot instance with the intents
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    """When the bot first is launched"""
    print(f"Logged in as {bot.user}")


@bot.command(name="metar", help="Metar lol")  # type: ignore
async def metar(ctx: commands.Context, station_id: str) -> None:
    """METAR command"""

    try:
        raw_metar = aviationweather_get_metar(station_id.strip().upper())
        obs = MetarObservations.from_raw_string(raw_metar)
    except Exception as ex:
        await ctx.send(f"Cannot load station data. {ex}")
        return

    # Create the basic body embed without fields
    embed = discord.Embed(
        title=f"{obs.station_id} ({obs.station_name})",
        url=f"https://www.weather.gov/wrh/timeseries?site={station_id}",
        colour=_color_from_temp(obs.temperature.temperature_c),
        description=f"```{raw_metar}```",
    )

    # Footer = observation timestamp
    embed.set_footer(text=obs.observed_on())

    # Actual observation fields
    embed.add_field(name="__Wind__", value=_get_wind_str(obs), inline=True)
    embed.add_field(name="__Visibility__", value=_get_vis_str(obs), inline=True)
    embed.add_field(name="", value="")
    embed.add_field(name="__Temperature__", value=_get_temp_str(obs), inline=True)
    embed.add_field(name="__Pressure__", value=_get_pressure_str(obs), inline=True)
    embed.add_field(name="", value="")
    embed.add_field(name="__Sky Condition__", value=_get_skycond_str(obs), inline=True)

    await ctx.send(embed=embed)


if __name__ == "__main__":
    bot.run(token="")
