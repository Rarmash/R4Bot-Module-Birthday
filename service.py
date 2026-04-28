from datetime import date
from typing import Any

from r4bot_sdk import register_hook_provider, unregister_hook_provider


PROFILE_FIELDS_HOOK = "profile.fields"
MODULE_ID = "birthday"


class BirthdayService:
    def __init__(self, module):
        self.module = module

    def register_hooks(self):
        register_hook_provider(self.module.bot, PROFILE_FIELDS_HOOK, MODULE_ID, self.build_profile_fields)

    def unregister_hooks(self):
        unregister_hook_provider(self.module.bot, PROFILE_FIELDS_HOOK, MODULE_ID)

    def build_profile_fields(self, ctx, member, user_data, server_data):
        birthday = user_data.get("birthday") if isinstance(user_data, dict) else None
        parsed = self.parse_birthday(birthday)

        if not parsed:
            return []

        day, month, year = parsed
        value = f"{day:02d}.{month:02d}"

        if year:
            age = self.get_current_age(day, month, year)
            value += f".{year} ({age})"

        days_left = self.days_until_birthday(day, month)

        if days_left == 0:
            value += "\nСегодня 🎉"
        elif days_left == 1:
            value += "\nЗавтра"
        else:
            value += f"\nЧерез {days_left} дн."

        return [
            {
                "name": "День рождения",
                "value": value,
            }
        ]

    @staticmethod
    def parse_birthday(value: Any) -> tuple[int, int, int | None] | None:
        if not isinstance(value, dict):
            return None

        try:
            day = int(value["day"])
            month = int(value["month"])

            raw_year = value.get("year")
            year = int(raw_year) if raw_year else None

            date(year or 2000, month, day)

            return day, month, year
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def days_until_birthday(day: int, month: int) -> int:
        today = date.today()
        current_year = today.year

        try:
            next_birthday = date(current_year, month, day)
        except ValueError:
            next_birthday = date(current_year, 2, 28)

        if next_birthday < today:
            try:
                next_birthday = date(current_year + 1, month, day)
            except ValueError:
                next_birthday = date(current_year + 1, 2, 28)

        return (next_birthday - today).days

    @staticmethod
    def get_current_age(day: int, month: int, year: int) -> int:
        today = date.today()
        age = today.year - year

        if (today.month, today.day) < (month, day):
            age -= 1

        return age

    def get_next_age(self, day: int, month: int, year: int | None) -> int | None:
        if not year:
            return None

        current_age = self.get_current_age(day, month, year)

        if self.days_until_birthday(day, month) == 0:
            return current_age

        return current_age + 1
