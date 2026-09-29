import functools
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar, overload

from .hooks import after, before

__all__ = ("hookable", "Cancel", "Replace")

log = logging.getLogger("plugin.modules.hooking.hookable")

_P = ParamSpec("_P")
_R = TypeVar("_R")


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


def _reject_coroutine(out: Any, plugin_id: str, key: str) -> None:
    if not inspect.iscoroutine(out):
        return

    out.close()
    log.error(f"Plugin '{plugin_id}' registered an async hook on sync method '{key}'; it was not run")


@overload
def hookable(fn: Callable[_P, Awaitable[_R]]) -> Callable[_P, Awaitable[_R]]: ...
@overload
def hookable(fn: Callable[_P, _R]) -> Callable[_P, _R]: ...
def hookable(fn: Callable[_P, _R] | Callable[_P, Awaitable[_R]]) -> Callable[_P, Any]:
    """
    Allows a function to be hooked onto.

    Parameters
    ----------
    fn: Callable[_P, _R] | Callable[_P, Awaitable[_R]]
        The function to mark as hookable.

    Returns
    -------
    Callable[_P, _R] | Callable[_P, Awaitable[_R]]
        A wrapper around `fn` that takes the same parameters and returns the
        same type, and runs registered `before` and `after` hooks around every call.
    """
    key = f"{fn.__module__}.{fn.__qualname__}"

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):  # pyright: ignore[reportRedeclaration]
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

    else:

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
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

    setattr(wrapper, "hook_key", key)

    return wrapper
