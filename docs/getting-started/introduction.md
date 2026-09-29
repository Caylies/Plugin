# Introduction

**Plugin** is a package framework for Ballsdex that was made for package developers. It gives packages extra capabilities, and a consistent structure for building on them. Package developers can use Plugin to completely override features such as countryball catching. Plugin is currently in beta. 

---

```py title="crates/plugin.py"
from ..models import Crate
from plugin import Plugin, Replace, get_component

BallSpawnView = get_component("BallSpawnView")


async def setup_plugin(plugin: Plugin):

    @plugin.after(BallSpawnView.catch_ball)
    async def roll_crate(result, self, user, **kwargs):
        state = plugin.state(self)
        crate = await Crate.objects.all().order_by("?").afirst()

        if crate is None:
            return

        state["crate_text"] = f"You got one **{await crate.describe(self.bot)}**!"

    @plugin.after(BallSpawnView.get_catch_text)
    def add_text(text, self, ball, new_ball):
        state = plugin.state(self)
        crate_text = state["crate_text"]

        if not crate_text:
            return

        return Replace(f"{text}{crate_text}")
```

This is an example of a plugin for Crates, a separate Ballsdex package. It allows crates to be caught along with balls whilst working alongside other packages that modify the spawn view, such as bd-labelmaker.
