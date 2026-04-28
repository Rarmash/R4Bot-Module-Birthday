from datetime import date, datetime
from typing import Any

import discord
from discord.commands import SlashCommandGroup
from discord.ext import tasks

from core.sdk import R4BotModule
from .service import BirthdayService

CONFIG_NOT_INITIALIZED_MESSAGE = (
    "Сервер ещё не настроен. Владелец сервера может выполнить `/service initserver`."
)


class Birthday(R4BotModule):
    module_id = "birthday"

    birthday = SlashCommandGroup("birthday", "Дни рождения участников")

    def __init__(self, bot):
        super().__init__(bot)

        if not hasattr(self.services, "firebase"):
            raise RuntimeError("Firebase service is required for birthday module")

        self.service = BirthdayService(self)
        self.service.register_hooks()

        self.announcement_loop.start()

    def cog_unload(self):
        self.service.unregister_hooks()
        self.announcement_loop.cancel()

    def _get_guild_id(self, ctx: discord.ApplicationContext) -> str:
        return str(ctx.guild.id)

    def _get_author_id(self, ctx: discord.ApplicationContext) -> str:
        return str(ctx.author.id)

    async def _get_server_data_or_notify(self, ctx: discord.ApplicationContext) -> dict | None:
        server_data = self.get_server_data(ctx.guild.id)
        if server_data:
            return server_data

        await ctx.respond(CONFIG_NOT_INITIALIZED_MESSAGE, ephemeral=True)
        return None

    @staticmethod
    def _get_upcoming_limit(module_config: dict, requested_limit: int | None) -> int:
        if requested_limit is not None:
            return requested_limit

        try:
            default_limit = int(module_config.get("upcoming_limit", 10))
        except (TypeError, ValueError):
            default_limit = 10

        return min(max(default_limit, 1), 25)

    def _get_users_collection(self, guild_id: str) -> dict[str, dict[str, Any]]:
        firebase = self.services.firebase

        for method_name in (
            "get_collection",
            "get_records",
            "get_all_records",
            "get_all_from_collection",
        ):
            method = getattr(firebase, method_name, None)
            if not method:
                continue

            try:
                data = method(guild_id, "Users")
                if isinstance(data, dict):
                    return data
            except TypeError:
                continue

        return {}

    def _get_announcement_record(self, guild_id: str, record_id: str) -> dict[str, Any] | None:
        try:
            record = self.services.firebase.get_from_record(guild_id, "BirthdayAnnouncements", record_id)
            return record if isinstance(record, dict) else None
        except Exception:
            return None

    def _mark_announced(self, guild_id: str, record_id: str):
        self.services.firebase.update_record(
            guild_id,
            "BirthdayAnnouncements",
            record_id,
            {
                "announced_at": datetime.now().isoformat(timespec="seconds"),
            },
        )

    @staticmethod
    def _validate_date(day: int, month: int, year: int | None) -> None:
        if year is None:
            date(2000, month, day)
            return

        today = date.today()

        if year < 1900 or year > today.year:
            raise ValueError("Год должен быть в диапазоне от 1900 до текущего года.")

        birthday = date(year, month, day)

        if birthday > today:
            raise ValueError("Дата рождения не может быть в будущем.")

    @staticmethod
    def _format_birthday(day: int, month: int, year: int | None = None) -> str:
        if year:
            return f"{day:02d}.{month:02d}.{year}"

        return f"{day:02d}.{month:02d}"

    @birthday.command(description="Указать свой день рождения")
    @discord.option("day", description="День", min_value=1, max_value=31)
    @discord.option("month", description="Месяц", min_value=1, max_value=12)
    @discord.option("year", description="Год рождения", required=False, min_value=1900)
    @discord.guild_only()
    async def set(
        self,
        ctx: discord.ApplicationContext,
        day: int,
        month: int,
        year: int | None = None,
    ):
        if not await self._get_server_data_or_notify(ctx):
            return

        try:
            self._validate_date(day, month, year)
        except ValueError as error:
            await ctx.respond(str(error), ephemeral=True)
            return

        guild_id = self._get_guild_id(ctx)
        author_id = self._get_author_id(ctx)

        self.services.firebase.update_record(
            guild_id,
            "Users",
            author_id,
            {
                "birthday": {
                    "day": day,
                    "month": month,
                    "year": year,
                }
            },
        )

        await ctx.respond(
            f"День рождения сохранён: **{self._format_birthday(day, month, year)}**.",
            ephemeral=True,
        )

    @birthday.command(description="Удалить свой день рождения")
    @discord.guild_only()
    async def clear(self, ctx: discord.ApplicationContext):
        if not await self._get_server_data_or_notify(ctx):
            return

        guild_id = self._get_guild_id(ctx)
        author_id = self._get_author_id(ctx)

        self.services.firebase.update_record(
            guild_id,
            "Users",
            author_id,
            {
                "birthday": None,
            },
        )

        await ctx.respond("День рождения удалён.", ephemeral=True)

    @birthday.command(description="Показать ближайшие дни рождения на сервере")
    @discord.option("limit", description="Сколько участников показать", required=False, min_value=1, max_value=25)
    @discord.guild_only()
    async def upcoming(self, ctx: discord.ApplicationContext, limit: int | None = None):
        if not await self._get_server_data_or_notify(ctx):
            return

        await ctx.defer()

        guild_id = self._get_guild_id(ctx)
        users = self._get_users_collection(guild_id)

        module_config = self.get_module_config(ctx.guild.id) or {}
        limit = self._get_upcoming_limit(module_config, limit)

        upcoming = []

        for user_id, user_data in users.items():
            if not isinstance(user_data, dict):
                continue

            parsed = self.service.parse_birthday(user_data.get("birthday"))
            if not parsed:
                continue

            member = ctx.guild.get_member(int(user_id))
            if not member:
                continue

            day, month, year = parsed
            days_left = self.service.days_until_birthday(day, month)
            age = self.service.get_next_age(day, month, year)

            upcoming.append(
                {
                    "member": member,
                    "day": day,
                    "month": month,
                    "year": year,
                    "days_left": days_left,
                    "age": age,
                }
            )

        upcoming.sort(key=lambda item: item["days_left"])
        upcoming = upcoming[:limit]

        if not upcoming:
            await ctx.respond("На сервере пока нет сохранённых дней рождения.")
            return

        embed = discord.Embed(
            title="Ближайшие дни рождения",
            color=discord.Color.blurple(),
        )

        lines = []

        for item in upcoming:
            date_text = self._format_birthday(item["day"], item["month"])

            if item["days_left"] == 0:
                when = "сегодня 🎉"
            elif item["days_left"] == 1:
                when = "завтра"
            else:
                when = f"через {item['days_left']} дн."

            age_text = f", исполнится {item['age']}" if item["age"] else ""

            lines.append(
                f"{item['member'].mention} — **{date_text}**, {when}{age_text}"
            )

        embed.description = "\n".join(lines)

        await ctx.respond(embed=embed)

    @tasks.loop(minutes=1)
    async def announcement_loop(self):
        now = datetime.now()

        for guild in self.bot.guilds:
            module_config = self.get_module_config(guild.id) or {}

            channel_id = module_config.get("birthday_channel_id")
            if not channel_id:
                continue

            announcement_hour = int(module_config.get("announcement_hour", 9))
            announcement_minute = int(module_config.get("announcement_minute", 0))

            if now.hour != announcement_hour or now.minute != announcement_minute:
                continue

            await self._announce_today_birthdays(guild, int(channel_id))

    @announcement_loop.before_loop
    async def before_announcement_loop(self):
        await self.bot.wait_until_ready()

    async def _announce_today_birthdays(self, guild: discord.Guild, channel_id: int):
        today = date.today()
        guild_id = str(guild.id)

        record_id = today.isoformat()
        if self._get_announcement_record(guild_id, record_id):
            return

        users = self._get_users_collection(guild_id)

        birthday_members = []

        for user_id, user_data in users.items():
            if not isinstance(user_data, dict):
                continue

            parsed = self.service.parse_birthday(user_data.get("birthday"))
            if not parsed:
                continue

            day, month, year = parsed

            if day != today.day or month != today.month:
                continue

            member = guild.get_member(int(user_id))
            if not member:
                continue

            age = self.service.get_current_age(day, month, year) if year else None

            birthday_members.append(
                {
                    "member": member,
                    "age": age,
                }
            )

        if not birthday_members:
            self._mark_announced(guild_id, record_id)
            return

        channel = guild.get_channel(channel_id)

        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.DiscordException:
                return

        mentions = ", ".join(item["member"].mention for item in birthday_members)

        embed = discord.Embed(
            title="Сегодня день рождения 🎉",
            color=discord.Color.gold(),
        )

        lines = []

        for item in birthday_members:
            age_text = f" — исполняется **{item['age']}**" if item["age"] else ""
            lines.append(f"{item['member'].mention}{age_text}")

        embed.description = "\n".join(lines)
        embed.set_footer(text=f"{today.strftime('%d.%m.%Y')}")

        await channel.send(
            content=f"Поздравляем {mentions} с днём рождения! 🎂",
            embed=embed,
        )

        self._mark_announced(guild_id, record_id)


def setup(bot):
    bot.add_cog(Birthday(bot))
