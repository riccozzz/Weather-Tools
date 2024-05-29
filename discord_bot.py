"""WIP discord bot module"""

import discord
from discord.ext import commands

import discord.ext

from wxtools.metar import MetarObservations
from wxtools.wip import aviationweather_get_metar

TOKEN = ""

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
    raw_metar = aviationweather_get_metar(station_id)
    obs = MetarObservations.from_raw_string(raw_metar)
    embed = discord.Embed(title=f"{obs.station_id} ({obs.station_name})", colour = discord.Colour.blue())
    embed.add_field(name="name", value="value", inline=False)
    embed.add_field(name="name2", value="value2", inline=True)
    await ctx.send(embed=embed)


if __name__ == "__main__":
    bot.run(TOKEN)
