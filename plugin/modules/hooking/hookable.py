from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Callable, Coroutine
from typing import Any, Concatenate, Protocol, cast, overload

from .hooks import after, before

__all__ = ("hookable", "Cancel", "Replace", "Hookable", "HookableCoroutine")

log = logging.getLogger("plugin.modules.hooking.hookable")


class Replace:
    """
    Return `Replace` from an `after` hook to replace the method's result.

    Parameters
    ----------
    value: Any
        The value to replace the method's result with.
    """

    def __init__(self, value: Any):
        self.value = value


class Cancel(Exception):
    """
    Raise `Cancel` from a `before` hook to skip the method and return `value` instead.

    Parameters
    ----------
    value: Any
        The value to return instead.
    """

    def __init__(self, value: Any = None):
        super().__init__()
        self.value = value


class Hookable[**P, R](Protocol):
    """
    The type `hookable` returns for a sync function: callable like the original, plus the
    `hook_key` attribute.
    """

    hook_key: str

    def __call__(self, inst: Any, *args: P.args, **kwargs: P.kwargs) -> R: ...
    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> Hookable[P, R]: ...
    @overload
    def __get__(self, obj: object, objtype: type | None = None) -> Callable[P, R]: ...


class HookableCoroutine[**P, R](Protocol):
    """
    The type `hookable` returns for an async function. Same as `Hookable`, but callable as a
    coroutine function.
    """

    hook_key: str

    def __call__(self, inst: Any, *args: P.args, **kwargs: P.kwargs) -> Coroutine[Any, Any, R]: ...
    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> HookableCoroutine[P, R]: ...
    @overload
    def __get__(self, obj: object, objtype: type | None = None) -> Callable[P, Coroutine[Any, Any, R]]: ...


def _reject_coroutine(out: Any, plugin_id: str, key: str) -> None:
    if not inspect.iscoroutine(out):
        return

    out.close()
    log.error(f"Plugin '{plugin_id}' registered an async hook on sync method '{key}'; it was not run")


@overload
def hookable[**P, R](fn: Callable[Concatenate[Any, P], Coroutine[Any, Any, R]]) -> HookableCoroutine[P, R]: ...
@overload
def hookable[**P, R](fn: Callable[Concatenate[Any, P], R]) -> Hookable[P, R]: ...
def hookable[**P, R](
    fn: Callable[Concatenate[Any, P], Coroutine[Any, Any, R]] | Callable[Concatenate[Any, P], R],
) -> HookableCoroutine[P, R] | Hookable[P, R]:
    """
    Allows a function to be hooked onto.

    Parameters
    ----------
    fn: Callable[Concatenate[Any, P], R] | Callable[Concatenate[Any, P], Coroutine[Any, Any, R]]
        The function to mark as hookable.

    Returns
    -------
    Hookable[P, R] | HookableCoroutine[P, R]
        A wrapper around `fn` that takes the same parameters and returns the
        same type, and runs registered `before` and `after` hooks around every call.
    """
    key = f"{fn.__module__}.{fn.__qualname__}"

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            for plugin_id, hook in list(before[key]):
                try:
                    out = hook(*args, **kwargs)

                    if inspect.isawaitable(out):
                        await out
                except Cancel as cancel:
                    return cancel.value
                except Exception:
                    log.exception(f"Plugin '{plugin_id}' failed in a before-hook of '{key}'")

            result = await fn(*args, **kwargs)

            for plugin_id, hook in list(after[key]):
                try:
                    out = hook(result, *args, **kwargs)

                    if inspect.isawaitable(out):
                        out = await out
                except Exception:
                    log.exception(f"Plugin '{plugin_id}' failed in an after-hook of '{key}'")
                    continue

                if isinstance(out, Replace):
                    result = out.value

            return result

        setattr(async_wrapper, "hook_key", key)

        return cast(HookableCoroutine[P, R], async_wrapper)

    else:

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            for plugin_id, hook in list(before[key]):
                try:
                    _reject_coroutine(hook(*args, **kwargs), plugin_id, key)
                except Cancel as cancel:
                    return cancel.value
                except Exception:
                    log.exception(f"Plugin '{plugin_id}' failed in a before-hook of '{key}'")

            result = fn(*args, **kwargs)

            for plugin_id, hook in list(after[key]):
                try:
                    out = hook(result, *args, **kwargs)

                    _reject_coroutine(out, plugin_id, key)
                except Exception:
                    log.exception(f"Plugin '{plugin_id}' failed in a after-hook of '{key}'")
                    continue

                if isinstance(out, Replace):
                    result = out.value

            return result

        setattr(sync_wrapper, "hook_key", key)

        return cast(Hookable[P, R], sync_wrapper)
