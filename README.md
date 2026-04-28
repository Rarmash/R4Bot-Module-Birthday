# R4Bot-Module-Birthday

Внешний модуль дней рождения для [R4Bot](https://github.com/Rarmash/R4Bot).

## Что делает
- добавляет `/birthday set`
- добавляет `/birthday clear`
- добавляет `/birthday upcoming`
- позволяет пользователю сохранить свой день рождения
- показывает ближайшие дни рождения участников сервера
- может автоматически поздравлять участников в заданном канале
- если установлен модуль `profile`, добавляет поле дня рождения в профиль
- использует runtime services из `bot.r4_services`

## Интеграции
- модуль регистрирует provider в hook-канал `profile.fields`
- если `profile` не установлен, это не считается ошибкой и модуль продолжает работать сам по себе

## Конфиг

Основные настройки модуля:

```json
{
  "upcoming_limit": 10,
  "birthday_channel_id": null,
  "announcement_hour": 9,
  "announcement_minute": 0
}
```

Файл должен лежать в:

```txt
config/modules/birthday.json
```

## Требования
- R4Bot >= 2.0
- runtime context с bot.r4_services
- сервисы firebase, config, module_config

## Структура
- `module.json` — метаданные модуля
- `cog.py` — команды дней рождения и основное поведение
- `service.py` — регистрация поля дня рождения для модуля профиля
- `birthday.example.json` — пример модульного конфига
- `requirements.txt` — зависимости для IDE и локальной проверки

## Установка в R4Bot
```powershell
python manage_modules.py install github:Rarmash/R4Bot-Module-Birthday@master --enable
```

## Разработка
Для нормальной подсветки импортов в IDE и локальной проверки модуля рекомендуется установить зависимости:

```powershell
python -m pip install -r requirements.txt
```

