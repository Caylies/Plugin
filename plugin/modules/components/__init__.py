from typing import Literal


def get_component(component: Literal["BallSpawnView"]):
    match component:
        case "BallSpawnView":
            from .countryballs.views import BallSpawnViewOverride

            return BallSpawnViewOverride
