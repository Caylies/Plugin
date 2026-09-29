from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

HookEntry = tuple[str, Callable[..., Any | Awaitable[Any]]]

before: defaultdict[str, list[HookEntry]] = defaultdict(list)
after: defaultdict[str, list[HookEntry]] = defaultdict(list)
