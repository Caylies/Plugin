from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from .countryballs.views import BallSpawnViewOverride, CatchRowOverride, CountryballNamePromptOverride

__all__ = ("get_component",)


@overload
def get_component(component: Literal["BallSpawnView"]) -> type["BallSpawnViewOverride"]: ...
@overload
def get_component(component: Literal["CountryballNamePrompt"]) -> type["CountryballNamePromptOverride"]: ...
@overload
def get_component(component: Literal["CatchRow"]) -> type["CatchRowOverride"]: ...
def get_component(component: Literal["BallSpawnView", "CountryballNamePrompt", "CatchRow"]):
    """
    Looks up one of the plugin system's hookable component classes by name.

    Looking components up this way, rather than importing them directly, defers importing the
    countryballs package (and everything it depends on) until a plugin actually needs one of its
    components.

    Parameters
    ----------
    component: Literal["BallSpawnView", "CountryballNamePrompt", "CatchRow"]
        The name of the component to look up.

    Returns
    -------
    type[BallSpawnViewOverride] | type[CountryballNamePromptOverride] | type[CatchRowOverride]
        The hookable class matching `component`.
    """
    match component:
        case "BallSpawnView":
            from .countryballs.views import BallSpawnViewOverride

            return BallSpawnViewOverride
        case "CountryballNamePrompt":
            from .countryballs.views import CountryballNamePromptOverride

            return CountryballNamePromptOverride
        case "CatchRow":
            from .countryballs.views import CatchRowOverride

            return CatchRowOverride
