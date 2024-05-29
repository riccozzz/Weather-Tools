"""
WIP discord bot module

https://message.style/app/editor
"""

import discord
from discord.ext import commands

import discord.ext

from wxtools.common import cardinal_direction
from wxtools.metar import MetarObservations
from wxtools.wip import aviationweather_get_metar
from wxtools.units import convert_unit, unit_by_label

_UNIT_KT = unit_by_label("knot")
_UNIT_MPH = unit_by_label("mile per hour")


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


def _color_from_temp(temp_c: float | None) -> discord.Colour:
    if temp_c is None:
        return discord.Colour.dark_gray()
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


@bot.command(name="metar", help="Metar lol")
async def metar(ctx: commands.Context, station_id: str) -> None:
    """METAR command"""
    # TODO: error checking lol
    # Load the obs
    raw_metar = aviationweather_get_metar(station_id)
    obs = MetarObservations.from_raw_string(raw_metar)

    # Create the basic body embed without fields
    embed = discord.Embed(
        title=f"{obs.station_id} ({obs.station_name})",
        url=f"https://www.weather.gov/wrh/timeseries?site={station_id}",
        colour=_color_from_temp(obs.temperature.temperature_c),
        description=f"`{raw_metar}`",
    )

    # Footer = observation timestamp
    embed.set_footer(text=obs.observed_on())

    # Actual observation fields
    # TODO how does inline look?
    embed.add_field(name="__Wind__", value=_get_wind_str(obs), inline=False)
    embed.add_field(name="__Visibility__", value=_get_vis_str(obs), inline=False)

    await ctx.send(embed=embed)


if __name__ == "__main__":
    bot.run(token="")
