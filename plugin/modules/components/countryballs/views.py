# pyright: reportIncompatibleMethodOverride=false, reportIncompatibleVariableOverride=false

from __future__ import annotations

import logging
import math
import random
import string
from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord.ui import Button, Item, MediaGallery, TextDisplay, button
from django.utils import timezone

from ballsdex.core.discord import Container, LayoutView
from ballsdex.core.metrics import caught_balls
from ballsdex.core.utils.formatting import format_command_mentions
from ballsdex.core.utils.utils import can_mention
from ballsdex.packages.countryballs.countryball import BallSpawnView, CatchRow, CountryballNamePrompt
from bd_models.models import Ball, BallInstance, GuildConfig, Player, Special, Trade, TradeObject, balls, specials
from settings.models import PromptMessage, Settings, settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

from ...hooking import hookable

log = logging.getLogger("plugin.overrides.countryballs")

_QUOTE_TABLE = str.maketrans({"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"'})


def _random_name() -> str:
    return "".join(random.choices(string.ascii_letters, k=15))


class CountryballNamePromptOverride(CountryballNamePrompt):
    """
    `CountryballNamePrompt` is the modal shown when a user presses the catch button. It validates
    the submitted name and finalizes the catch. `CountryballNamePromptOverride` extends off of
    `CountryballNamePrompt` and provides hookable methods for plugins.
    """

    @hookable
    async def on_error(self, interaction: discord.Interaction["BallsDexBot"], error: Exception) -> None:
        if isinstance(error, discord.NotFound) and error.code == 10062:
            return

        log.exception("An error occurred in countryball catching prompt", exc_info=error)

        message = f"An error occurred with this {settings.collectible_name}."

        if interaction.response.is_done():
            await interaction.followup.send(message)
        else:
            await interaction.response.send_message(message)

    @hookable
    async def resolve_player(self, interaction: discord.Interaction["BallsDexBot"]) -> Player:
        """
        Gets or creates the `Player` submitting this prompt.

        Parameters
        ----------
        interaction: discord.Interaction["BallsDexBot"]
            The interaction tied to the submitted modal.

        Returns
        -------
        Player
            The player submitting this prompt.
        """
        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)

        return player

    @hookable
    def get_slow_message(self, interaction: discord.Interaction["BallsDexBot"]) -> str:
        """
        Builds the message shown when the countryball was already caught by the time of submission.

        Parameters
        ----------
        interaction: discord.Interaction["BallsDexBot"]
            The interaction tied to the submitted modal.

        Returns
        -------
        str
            The message to display.
        """
        return settings.get_formatted_message(
            category=PromptMessage.PromptType.SLOW,
            mention=interaction.user.mention,
            model=self.view.model,
            bot=interaction.client,
        )

    @hookable
    async def send_slow_message(self, interaction: discord.Interaction["BallsDexBot"], player: Player) -> None:
        message = self.get_slow_message(interaction)

        await interaction.followup.send(message, ephemeral=True, allowed_mentions=await can_mention([player]))

    @hookable
    def truncate_wrong_name(self, text: str) -> str:
        """
        Shortens an overly long wrong name so it's safe to display back to the user.

        Parameters
        ----------
        text: str
            The submitted name.

        Returns
        -------
        str
            The name, truncated to 500 characters with an ellipsis if it was longer.
        """
        if len(text) > 500:
            return text[:500] + "..."

        return text

    @hookable
    def get_wrong_message(self, interaction: discord.Interaction["BallsDexBot"], wrong_name: str) -> str:
        """
        Builds the message shown when the submitted name does not match.

        Parameters
        ----------
        interaction: discord.Interaction["BallsDexBot"]
            The interaction tied to the submitted modal.
        wrong_name: str
            The (possibly truncated) name that was submitted.

        Returns
        -------
        str
            The message to display.
        """
        return settings.get_formatted_message(
            category=PromptMessage.PromptType.WRONG,
            mention=interaction.user.mention,
            model=self.view.model,
            bot=interaction.client,
            wrong=wrong_name,
        )

    @hookable
    async def send_wrong_message(
        self, interaction: discord.Interaction["BallsDexBot"], player: Player, wrong_name: str
    ) -> None:
        message = self.get_wrong_message(interaction, wrong_name)

        await interaction.followup.send(message, allowed_mentions=await can_mention([player]), ephemeral=False)

    @hookable
    async def send_catch_result(
        self, interaction: discord.Interaction["BallsDexBot"], player: Player, ball, is_new: bool
    ) -> None:
        await interaction.followup.send(
            self.view.get_catch_message(ball, is_new, interaction.user.mention),
            allowed_mentions=discord.AllowedMentions(users=player.can_be_mentioned),
        )
        await interaction.followup.edit_message(self.view.message.id, view=self.view)

    @hookable
    async def on_submit(self, interaction: discord.Interaction["BallsDexBot"]) -> None:
        await interaction.response.defer(thinking=True)

        player = await self.resolve_player(interaction)

        if self.view.caught:
            await self.send_slow_message(interaction, player)
            return

        if not self.view.is_name_valid(self.name.value):
            wrong_name = self.truncate_wrong_name(self.name.value)
            await self.send_wrong_message(interaction, player, wrong_name)
            return

        ball, is_new = await self.view.catch_ball(interaction.user, player=player, guild=interaction.guild)

        await self.send_catch_result(interaction, player, ball, is_new)


class CatchRowOverride(CatchRow):
    """
    `CatchRow` is the action row holding the catch button. `CatchRowOverride` extends off of
    `CatchRow` and provides hookable methods for plugins.
    """

    def __init__(self, spawn_view: "BallSpawnView") -> None:
        super().__init__(spawn_view)

        self.catch_button.style = self.get_button_style()
        self.catch_button.label = self.get_button_label()

    @hookable
    def get_button_style(self) -> discord.ButtonStyle:
        """
        The catch button's color.

        Returns
        -------
        discord.ButtonStyle
            The style to apply to the catch button.
        """
        return discord.ButtonStyle.primary

    @hookable
    def get_button_label(self) -> str:
        """
        The catch button's label.

        Returns
        -------
        str
            The text shown on the catch button.
        """
        return settings.catch_button_label

    @hookable
    def get_slow_message(self, interaction: discord.Interaction["BallsDexBot"]) -> str:
        """
        Builds the message shown when the catch button is pressed after the countryball was
        already caught.

        Parameters
        ----------
        interaction: discord.Interaction["BallsDexBot"]
            The interaction tied to the button press.

        Returns
        -------
        str
            The message to display.
        """
        return settings.get_formatted_message(
            category=PromptMessage.PromptType.SLOW,
            mention=interaction.user.mention,
            model=self.spawn_view.model,
            bot=interaction.client,
        )

    @hookable
    def create_name_prompt(self) -> CountryballNamePrompt:
        """
        Creates the modal shown when the catch button is pressed.

        Returns
        -------
        CountryballNamePrompt
            The modal to display.
        """
        return CountryballNamePromptOverride(self.spawn_view)

    @button(label="Catch me!")
    @hookable
    async def catch_button(self, interaction: discord.Interaction["BallsDexBot"], button: Button):
        if self.spawn_view.caught:
            await interaction.response.send_message(self.get_slow_message(interaction), ephemeral=True)
        else:
            await interaction.response.send_modal(self.create_name_prompt())


class BallSpawnViewOverride(BallSpawnView):
    """
    `BallSpawnView` is a Discord UI view that represents the spawning and interaction logic for a
    countryball in the BallsDex bot. It handles user interactions, spawning mechanics, and
    countryball catching logic. `BallSpawnViewOverride` extends off of `BallSpawnView` and
    provides hookable methods for plugins.

    Attributes
    ----------
    bot: BallsDexBot
        The bot instance.
    model: Ball
        The countryball being spawned.
    algo: str | None
        The algorithm used for spawning, used for metrics.
    message: discord.Message
        The Discord message associated with this view once created with `spawn`.
    caught: bool
        Whether the countryball has been caught yet.
    ballinstance: BallInstance | None
        If this is set, this ball instance will be spawned instead of creating a new ball instance.
        All properties are preserved, and if successfully caught, the owner is transferred (with
        a trade entry created). Use the `from_existing` constructor to use this.
    special: Special | None
        Force the spawned countryball to have a special event attached. If None, a random one will
        be picked.
    atk_bonus: int | None
        Force a specific attack bonus if set, otherwise random range defined in settings.
    hp_bonus: int | None
        Force a specific health bonus if set, otherwise random range defined in settings.
    """

    catch_row: CatchRowOverride

    @hookable
    def __init__(self, bot: "BallsDexBot", model: Ball):
        super().__init__(bot, model)

        self.catch_row = CatchRowOverride(self)

    @property
    @hookable
    def catch_button(self) -> Button["BallSpawnView"]:
        """
        Returns the view's catch button.

        Returns
        -------
        Button["BallSpawnView"]
            The catch button.
        """
        return self.catch_row.catch_button

    @property
    @hookable
    def name(self) -> str:
        """
        Returns the countryball's name.

        Returns
        -------
        str
            The countryball's name.
        """
        return self.model.country

    @hookable
    async def interaction_check(self, interaction: discord.Interaction["BallsDexBot"], /) -> bool:
        return await interaction.client.blacklist_check(interaction)

    @hookable
    async def on_timeout(self):
        self.catch_button.disabled = True

        await self.refresh_message()
        await self.release_existing_lock()

    @hookable
    async def refresh_message(self) -> None:
        if not self.message:
            return

        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass

    @hookable
    async def release_existing_lock(self) -> None:
        if not self.ballinstance or self.caught:
            return

        await self.ballinstance.unlock()

    @classmethod
    @hookable
    async def from_existing(cls, bot: "BallsDexBot", ball_instance: BallInstance) -> BallSpawnViewOverride:
        """
        Creates a view from an existing `BallInstance`. Instead of creating a new ball instance,
        this will transfer ownership of the existing instance when caught.

        The ball instance must be unlocked from trades, and will be locked until caught or timed
        out.

        Parameters
        ----------
        bot: "BallsDexBot"
            The bot instance.
        ball_instance: BallInstance
            The countryball instance to build the view from.

        Returns
        -------
        BallSpawnViewOverride
            The constructed view based on the countryball instance.
        """
        if await ball_instance.is_locked():
            raise RuntimeError("This countryball is locked for a trade")

        await ball_instance.lock_for_trade()

        view = cls(bot, ball_instance.ball)
        view.ballinstance = ball_instance
        view.og_id = ball_instance.player.discord_id

        return view

    @classmethod
    @hookable
    async def get_random(cls, bot: "BallsDexBot") -> BallSpawnViewOverride:
        countryballs = cls.get_spawnable_balls()  # pyright: ignore[reportCallIssue]

        if not countryballs:
            raise RuntimeError("No ball to spawn")

        return cls(bot, cls.pick_ball(countryballs))  # pyright: ignore[reportCallIssue]

    @classmethod
    @hookable
    def get_spawnable_balls(cls) -> list[Ball]:
        """
        Gets a list of countryballs that can spawn.

        Returns
        -------
        list[Ball]
            A list of countryballs that can spawn.
        """
        return [ball for ball in balls.values() if ball.enabled]

    @classmethod
    @hookable
    def pick_ball(cls, countryballs: list[Ball]) -> Ball:
        """
        Chooses a random countryball out of a list of countryballs.

        Parameters
        ----------
        countryballs: list[Ball]
            The list of countryballs to choose from.

        Returns
        -------
        Ball
            The chosen countryball.
        """
        weights = [x.rarity for x in countryballs]

        return random.choices(population=countryballs, weights=weights, k=1)[0]

    @classmethod
    @hookable
    def get_special_candidates(cls) -> list[Special]:
        """
        Gets a list of specials that can be chosen.

        Returns
        -------
        list[Special]
            A list of specials that can be chosen.
        """
        now = timezone.now()
        tz = timezone.get_current_timezone()

        return [
            x
            for x in specials.values()
            if (x.start_date or datetime.min.replace(tzinfo=tz))
            <= now
            <= (x.end_date or datetime.max.replace(tzinfo=tz))
        ]

    @classmethod
    @hookable
    def get_random_special(cls) -> Special | None:
        population = cls.get_special_candidates()  # pyright: ignore[reportCallIssue]

        if not population:
            return None

        common_weight = max(1 - sum(x.rarity for x in population), 0)
        weights = [x.rarity for x in population] + [common_weight]

        return random.choices(population=[*population, None], weights=weights, k=1)[0]

    @hookable
    def roll_tip(self) -> bool:
        """
        Rolls for a tip to display below the spawn message.

        Returns
        -------
        bool
            Whether the tip can be displayed.
        """
        if not settings.tip_chance:
            return False

        return random.randint(1, 100) <= settings.tip_chance

    @hookable
    async def tips_enabled(self, guild_id: int | None) -> bool:
        """
        Determines if tips are enabled for this view.

        Parameters
        ----------
        guild_id: int | None
            The guild where the countryball spawns. If set, its configuration is checked, as server
            admins may opt out of tips.

        Returns
        -------
        bool
            Whether tips are enabled for this view.
        """
        if guild_id is None:
            return True

        enabled = await GuildConfig.objects.filter(guild_id=guild_id).values_list("tips_enabled", flat=True).afirst()

        return enabled is not False

    @hookable
    async def get_tip(self, guild_id: int | None = None) -> str | None:
        if not self.roll_tip():
            return None

        if not await self.tips_enabled(guild_id):
            return None

        tip = settings.get_formatted_tip()

        return format_command_mentions(tip, self.bot) if tip else None

    @hookable
    def build_image(self, file_name: str) -> Item[LayoutView]:
        return MediaGallery(discord.MediaGalleryItem(f"attachment://{file_name}"))

    @hookable
    async def build_tip_item(self, guild_id: int | None) -> Item[LayoutView] | None:
        tip = await self.get_tip(guild_id)

        if not tip:
            return None

        text = TextDisplay(f"-# \N{ELECTRIC LIGHT BULB} {tip}")

        return Container(text) if settings.tip_container else text

    @hookable
    async def build(self, spawn_message: str, file_name: str, guild_id: int | None = None):
        """
        Populates the components of this view. This must be called once, right before sending the
        spawn message, since the layout depends on the message and the attached image.

        Parameters
        ----------
        spawn_message: str
            The formatted spawn message, displayed above the countryball.
        file_name: str
            The name of the image uploaded alongside this view.
        guild_id: int | None
            The guild where the countryball spawns, used to determine if a tip may be displayed.
        """
        if spawn_message:
            self.add_item(TextDisplay(spawn_message))

        self.add_item(self.build_image(file_name))

        tip_item = await self.build_tip_item(guild_id)

        if tip_item and settings.tip_position == Settings.TipPosition.ABOVE_BUTTON:
            self.add_item(tip_item)

        self.add_item(self.catch_row)

        if tip_item and settings.tip_position == Settings.TipPosition.BELOW_BUTTON:
            self.add_item(tip_item)

    @hookable
    def generate_file_name(self) -> str:
        """
        Generates a random file name.

        Returns
        -------
        str
            The randomly generated file name.
        """
        if not self.model.wild_card.name:
            return ""

        extension = self.model.wild_card.name.split(".")[-1]

        return f"nt_{_random_name()}.{extension}"

    @hookable
    def can_spawn_in(self, channel: discord.TextChannel) -> bool:
        """
        Determines if a countryball can be spawned in the given channel.

        Parameters
        ----------
        channel: discord.TextChannel
            The channel to spawn in.

        Returns
        -------
        bool
            Whether the countryball can spawn.
        """
        permissions = channel.permissions_for(channel.guild.me)

        return permissions.attach_files and permissions.send_messages

    @hookable
    def get_spawn_message(self) -> str:
        """
        Builds the message shown above the countryball when it spawns.

        Returns
        -------
        str
            The message to display.
        """
        return settings.get_formatted_message(
            category=PromptMessage.PromptType.SPAWN, mention="", model=self.model, bot=self.bot
        )

    @hookable
    async def send_spawn(self, channel: discord.TextChannel, file_name: str) -> discord.Message:
        """
        Sends the spawn message to the channel.

        Parameters
        ----------
        channel: discord.TextChannel
            The channel to send the spawn message to.
        file_name: str
            The name of the attached countryball image.

        Returns
        -------
        discord.Message
            The sent spawn message.
        """
        return await channel.send(view=self, file=discord.File(self.model.wild_card.path, filename=file_name))

    @hookable
    async def spawn(self, channel: discord.TextChannel) -> bool:
        """
        Spawn a countryball in a channel.

        Parameters
        ----------
        channel: discord.TextChannel
            The channel where to spawn the countryball. Must have permission to send messages
            and upload files as a bot (not through interactions).

        Returns
        -------
        bool
            `True` if the operation succeeded, otherwise `False`. An error will be displayed
            in the logs if that's the case.
        """
        file_name = self.generate_file_name()

        try:
            if not self.can_spawn_in(channel):
                log.warning("Missing permission to spawn ball in channel %s.", channel)
                return False

            await self.build(self.get_spawn_message(), file_name, channel.guild.id)

            self.message = await self.send_spawn(channel, file_name)

            return True
        except discord.Forbidden:
            log.warning(f"Missing permission to spawn ball in channel {channel}.")
        except discord.HTTPException:
            log.error("Failed to spawn ball", exc_info=True)

        return False

    @hookable
    def get_valid_names(self) -> tuple[str, ...]:
        """
        Gets a tuple with all valid catch names for the view.

        Returns
        -------
        tuple[str, ...]
            A tuple containing valid catch names.
        """
        if not self.model.catch_names:
            return (self.name.lower(),)

        return (self.name.lower(), *self.model.catch_names.split(";"))

    @hookable
    def normalize_name(self, text: str) -> str:
        """
        Normalizes a countryball name.

        Parameters
        ----------
        text: str
            The countryball's name to normalize.

        Returns
        -------
        str
            The normalized countryball name.
        """
        return text.lower().strip().translate(_QUOTE_TABLE)

    @hookable
    def is_name_valid(self, text: str) -> bool:
        """
        Determines if a countryball name is valid.

        Parameters
        ----------
        text: str
            The countryball name to check.

        Returns
        -------
        bool
            Whether the countryball name is valid.
        """
        return self.normalize_name(text) in self.get_valid_names()

    @hookable
    def mark_caught(self) -> None:
        """
        Marks the view as caught.
        """
        if self.caught:
            raise RuntimeError("This ball was already caught!")

        self.caught = True
        self.catch_button.disabled = True

    @hookable
    async def resolve_player(self, user: discord.User | discord.Member, player: Player | None) -> Player:
        """
        Gets or creates the `Player` catching the countryball.

        Parameters
        ----------
        user: discord.User | discord.Member
            The user catching the countryball.
        player: Player | None
            If already fetched, pass the player here to avoid an additional query.

        Returns
        -------
        Player
            The player catching the countryball.
        """
        return player or (await Player.objects.aget_or_create(discord_id=user.id))[0]

    @hookable
    async def is_new_catch(self, player: Player) -> bool:
        """
        Determines if a countryball is a new entry to the given player's completion.

        Parameters
        ----------
        player: Player
            The player to examine their completion for the countryball.

        Returns
        -------
        bool
            Whether the countryball is a new entry to the given player's completion.
        """
        return not await BallInstance.objects.filter(player=player, ball=self.model).aexists()

    @hookable
    def roll_bonuses(self) -> tuple[int, int]:
        """
        Rolls for attack and health bonus and returns them.

        Returns
        -------
        tuple[int, int]
            The attack and health bonuses respectively.
        """
        attack = (
            self.atk_bonus
            if self.atk_bonus is not None
            else random.randint(-settings.max_attack_bonus, settings.max_attack_bonus)
        )

        health = (
            self.hp_bonus
            if self.hp_bonus is not None
            else random.randint(-settings.max_health_bonus, settings.max_health_bonus)
        )

        return attack, health

    @hookable
    def pick_special(self) -> Special | None:
        """
        Chooses a random special or none.

        Returns
        -------
        Special | None
            The chosen special or none.
        """
        return self.special or self.get_random_special()

    @hookable
    async def create_ball(self, player: Player, guild: discord.Guild | None) -> BallInstance:
        """
        Creates a new countryball instance based on the view.

        Parameters
        ----------
        player: Player
            The player to give the countryball instance to.
        guild: discord.Guild | None
            The guild the countryball was caught from, if present.
        """
        attack, health = self.roll_bonuses()

        return await BallInstance.objects.acreate(
            ball=self.model,
            player=player,
            special=self.pick_special(),
            attack_bonus=attack,
            health_bonus=health,
            server_id=guild.id if guild else None,
            spawned_time=self.message.created_at,
            catch_date=timezone.now(),
        )

    @hookable
    async def return_to_owner(self, instance: BallInstance) -> BallInstance:
        """
        Returns a dropped countryball to its original owner, without creating a trade.

        Parameters
        ----------
        instance: BallInstance
            The existing countryball instance being caught back by its owner.

        Returns
        -------
        BallInstance
            The same instance, unlocked.
        """
        instance.locked = None

        await instance.asave(update_fields=("locked",))

        return instance

    @hookable
    async def transfer_existing(self, instance: BallInstance, player: Player) -> BallInstance:
        """
        Transfers a dropped countryball to a new owner, registering it as a trade.

        Parameters
        ----------
        instance: BallInstance
            The existing countryball instance being caught by a new owner.
        player: Player
            The player receiving the countryball.

        Returns
        -------
        BallInstance
            The same instance, now owned by `player` and unlocked.
        """
        trade = await Trade.objects.acreate(player1=instance.player, player2=player)

        await TradeObject.objects.acreate(trade=trade, player=instance.player, ballinstance=instance)

        instance.trade_player = instance.player
        instance.player = player
        instance.locked = None

        await instance.asave(update_fields=("player", "trade_player", "locked"))

        return instance

    @hookable
    async def hand_over_existing(self, player: Player) -> BallInstance:
        """
        Hands over the view's existing countryball instance, either back to its own owner or to a
        new one, depending on who is catching it.

        Parameters
        ----------
        player: Player
            The player catching the countryball.

        Raises
        ------
        RuntimeError
            The view has no existing countryball instance set.

        Returns
        -------
        BallInstance
            The handed-over instance.
        """
        instance = self.ballinstance

        if instance is None:
            raise RuntimeError("'hand_over_existing()' called without an existing ball instance")

        if instance.player_id == player.pk:
            return await self.return_to_owner(instance)

        return await self.transfer_existing(instance, player)

    @hookable
    def log_catch(self, user: discord.User | discord.Member, ball: BallInstance):
        """
        Logs a countryball catch.

        Parameters
        ----------
        user: discord.User | discord.Member
            The user who caught the countryball.
        ball: BallInstance
            The countryball that was caught.
        """
        special = ball.special

        log.log(
            logging.INFO if user.id in self.bot.catch_log else logging.DEBUG,
            f"{user} caught {settings.collectible_name} {self.model}, {special=}",
        )

    @hookable
    async def catch_ball(
        self, user: discord.User | discord.Member, *, player: Player | None, guild: discord.Guild | None
    ) -> tuple[BallInstance, bool]:
        self.mark_caught()

        player = await self.resolve_player(user, player)
        is_new = await self.is_new_catch(player)

        if self.ballinstance:
            return await self.hand_over_existing(player), is_new

        ball = await self.create_ball(player, guild)

        self.log_catch(user, ball)
        self.record_metrics(user, ball)

        return ball, is_new

    @hookable
    def get_catch_text(self, ball: BallInstance, new_ball: bool) -> str:
        """
        Builds extra text seen when a ball is caught.

        Parameters
        ----------
        ball: BallInstance
            The countryball that was caught.
        new_ball: bool
            Whether the countryball is a new entry to the player's completion.

        Returns
        -------
        str
            Extra text displayed when a countryball is caught.
        """
        text = ""

        if ball.specialcard and ball.specialcard.catch_phrase:
            text += f"*{ball.specialcard.catch_phrase}*\n"

        if new_ball:
            text += f"This is a **new {settings.collectible_name}** that has been added to your completion!"

        if self.ballinstance:
            text += f"This {settings.collectible_name} was dropped by <@{self.og_id}>\n"

        return text

    @hookable
    def record_metrics(self, user: discord.User | discord.Member, ball: BallInstance):
        """
        Records a Prometheus metric for the catch.

        Parameters
        ----------
        user: discord.User | discord.Member
            The user who caught the countryball.
        ball: BallInstance
            The countryball that was caught.
        """
        if not isinstance(user, discord.Member) or not user.guild.member_count:
            return

        caught_balls.labels(
            country=self.name,
            special=ball.special,
            guild_size=10 ** math.ceil(math.log(max(user.guild.member_count - 1, 1), 10)),
            spawn_algo=self.algo,
            shard_id=user.guild.shard_id,
        ).inc()

    @hookable
    def get_catch_message(self, ball: BallInstance, new_ball: bool, mention: str) -> str:
        """
        Generate a user-facing message after a ball has been caught.

        Parameters
        ----------
        ball: BallInstance
            The newly created ball instance.
        new_ball: bool
            Whether this is a new countryball in completion (as returned by `catch_ball`).
        mention: str
            The mention string for the user who caught the countryball.

        Returns
        -------
        str
            The full catch message, including the stat line and any extra catch text.
        """
        catch_message = settings.get_formatted_message(
            category=PromptMessage.PromptType.CATCH, mention=mention, model=self.model, bot=self.bot
        )

        text = self.get_catch_text(ball, new_ball)

        return catch_message + f" `(#{ball.pk:0X}, {ball.attack_bonus:+}%/{ball.health_bonus:+}%)`\n\n{text}"
