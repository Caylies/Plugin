# Plugins

A plugin is how a package attaches to *hooks*. Any package that wants to react to or change behavior needs one. Create a plugin with the `Plugin` class and a unique ID.

```py
currency = Plugin("currency")
```

*Every package must use a unique ID.* Hooks are tracked by ID, so two packages sharing one would remove each other's hooks when either unloads.

## Registering hooks

Use `before` and `after` as decorators, passing the method you want to hook. This plugin will add "Thanks for playing!" at the end of every ball catch message.

```py title="currency/plugin.py"
from plugin import Plugin, Replace, get_component

BallSpawnView = get_component("BallSpawnView")


async def setup_plugin(plugin: Plugin):

    @plugin.after(BallSpawnView.get_catch_text)
    def add_text(text, self, ball, new_ball):
        return Replace(f"{text}\nThanks for playing!")
```

| Decorator | Called                 | Arguments                               | Effect                                                      |
|-----------|------------------------|-----------------------------------------|-------------------------------------------------------------|
| `before`  | Before the method runs | Same as the method                      | Raise `Cancel(value)` to skip the method and return `value` |
| `after`   | After the method runs  | The result, then the method's arguments | Return `Replace(value)` to change the result                |

- A hook that returns nothing leaves the result unchanged.
- A hook can be asynchronous only if the method it targets is also asynchronous.
- A hook that raises an error is logged with its plugin ID and skipped, so it cannot break the method for other plugins.

## State

Hooks often need to remember variables between calls, for example data attached to one specific view instance. Use `Plugin.state`, which returns a dictionary unique to your plugin's ID for a given object. The same dictionary is returned every time you call it with that object, so hooks can share data across a spawn view without touching each other's data.

```py title="currency/plugin.py"
@plugin.after(BallSpawnView.__init__)
def store_bonus(_, self, bot, model):
    plugin.state(self)["bonus_rolled"] = False


@plugin.after(BallSpawnView.mark_caught)
def apply_bonus(_, self):
    state = plugin.state(self)

    if state["bonus_rolled"]:
        return

    state["bonus_rolled"] = True

    # ...
```

- `plugin.state(instance)` creates a store on first use, so there's no need to initialize it separately.
- State is isolated per plugin ID, so two plugins storing data on the same view can't overwrite each other, even if they happen to use the same key.
- State is stored on the given instance. It disappears when the object does, and is not affected by `unload`.

## Unloading

Plugins can be unloaded with the `unload` method, which removes every hook the plugin registered. Unload a plugin when its package's extension is unloaded.

```py
currency.unload()
```

`unload` only removes hooks. If your package also started tasks, changed other state, or stored data with `plugin.state`, clean that up in the same place.

## Example

A package's `__init__` file that creates a plugin on setup and unloads it on teardown:

```py title="currency/__init__.py"
from typing import TYPE_CHECKING

from plugin import Plugin

from .cog import Currency
from .plugin import setup_plugin

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

currency: Plugin | None = None


async def setup(bot: "BallsDexBot"):
    global currency

    currency = Plugin("currency")

    await setup_plugin(currency)

    await bot.add_cog(Currency(bot))


async def teardown(bot: "BallsDexBot"):
    if currency:
        currency.unload()
```

The `global` statement is required. Without it, `setup` creates a local variable and `teardown` never sees the plugin.
