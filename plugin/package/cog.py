from typing import TYPE_CHECKING

from discord.ext import commands

import ballsdex.packages.countryballs.countryball as countryball

from ..modules.components import get_component
from .patching import patch_spawn_view

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class PluginCog(commands.Cog):
    """
    Manages plugins.
    """

    original_spawn_view: type[countryball.BallSpawnView]

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self.original_spawn_view = countryball.BallSpawnView

        self._patch()

    def _patch(self):
        BallSpawnViewOverride = get_component("BallSpawnView")

        patch_spawn_view(self.bot, BallSpawnViewOverride)

    @commands.command()
    @commands.is_owner()
    async def plugin_restore(self, ctx: commands.Context["BallsDexBot"]):
        """
        Restores all plugin components to their originals.
        """
        patch_spawn_view(self.bot, self.original_spawn_view)
        await ctx.reply("Restored all overriden components to their originals")

    @commands.command()
    @commands.is_owner()
    async def plugin_reload(self, ctx: commands.Context["BallsDexBot"]):
        """
        Reloads all plugin components.
        """
        self._patch()
        await ctx.reply("Reloaded all plugin components")
