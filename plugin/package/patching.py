from typing import TYPE_CHECKING, cast

import ballsdex.packages.countryballs.cog as countryballs_cog
import ballsdex.packages.countryballs.countryball as countryball
from ballsdex.packages.countryballs.cog import CountryBallsSpawner

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


def patch_spawn_view(bot: "BallsDexBot", view: type[countryball.BallSpawnView]):
    cog = cast("CountryBallsSpawner", bot.get_cog("CountryBallsSpawner"))

    cog.countryball_cls = view

    setattr(countryballs_cog, "BallSpawnView", view)
