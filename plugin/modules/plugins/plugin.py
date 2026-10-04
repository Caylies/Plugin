from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol

from ..hooking import hooks

__all__ = ("Plugin", "get")

log = logging.getLogger("plugin.modules.plugins.plugin")

_plugins: dict[str, "Plugin"] = {}


class _HookTarget(Protocol):
    hook_key: str


class _PluginConflict(Exception):
    """
    Raised when a plugin is registered under an ID that's already in use.

    Parameters
    ----------
    id: str
        The ID that was already registered.
    """

    def __init__(self, id: str):
        self.id = id

        super().__init__(f"A plugin with ID '{id}' is already registered")


class Plugin:
    """
    A core component for accessing plugin hooks.

    Parameters
    ----------
    id: str
        A unique ID for the plugin.
    """

    def __init__(self, id: str):
        if id in _plugins:
            raise _PluginConflict(id)

        self.id = id
        _plugins[id] = self

        log.info(f"Registered new plugin: {id}")

    def _remove(self, inputHooks: dict[str, list[tuple[str, Callable]]]):
        for key in list(inputHooks):
            inputHooks[key] = [(pid, fn) for pid, fn in inputHooks[key] if pid != self.id]

            if not inputHooks[key]:
                del inputHooks[key]

    def state(self, instance: object) -> dict:
        """
        Returns a per-plugin storage dictionary stored on `instance`, isolated from
        other plugins.

        Parameters
        ----------
        instance: object
            The object to store the state on.

        Returns
        -------
        dict
            A dictionary unique to this plugin's ID for the given `instance`.
            It is also returned on every call for the same `instance`.
        """
        store = getattr(instance, "_plugin_state", None)

        if store is None:
            store = {}
            setattr(instance, "_plugin_state", store)

        return store.setdefault(self.id, {})

    def unload(self):
        """
        Unloads the plugin by unregistering it and cleaning up its hooks.
        """
        self._remove(hooks.before)
        self._remove(hooks.after)

        del _plugins[self.id]

        log.info(f"Unregistered plugin: {self.id}")

    def before[F: Callable[..., Any]](self, target: _HookTarget) -> Callable[[F], F]:
        """
        Runs a function before the target method runs. Raise `Cancel(value)` to skip the method and return `value`.

        Parameters
        ----------
        target: _HookTarget
            The method to run the function before.

        Returns
        -------
        Callable[[F], F]
            A decorator that registers the function as a before-hook for the target and returns it.
        """

        def decorator(fn: F) -> F:
            hooks.before[target.hook_key].append((self.id, fn))

            return fn

        return decorator

    def after[F: Callable[..., Any]](self, target: _HookTarget) -> Callable[[F], F]:
        """
        Runs a function after the target method runs. Return `Replace(value)` to change the result.

        Parameters
        ----------
        target: _HookTarget
            The method to run the function after.

        Returns
        -------
        Callable[[F], F]
            A decorator that registers the function as an after-hook for the target and returns it.
        """

        def decorator(fn: F) -> F:
            hooks.after[target.hook_key].append((self.id, fn))

            return fn

        return decorator


def get(id: str) -> Plugin | None:
    """
    Looks up a registered plugin by ID. Useful for checking if a plugin is enabled.

    Parameters
    ----------
    id: str
        The ID of the plugin to look up.

    Returns
    -------
    Plugin | None
        The plugin registered under `id`, or `None` if no plugin with that ID is
        currently registered.
    """
    return _plugins.get(id)
