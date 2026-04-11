# Discord -> Telegram Bridge
Бот пересылает сообщения из выбранного Discord-канала в Telegram-чат или канал.

Поддерживается текст, изображения, видео, аудио, файлы, несколько Telegram-получателей на один Discord-канал, горячая перезагрузка `config.yaml` и логирование.
https://github.com/user-attachments/assets/f6ff57af-57f8-40d9-bb3f-0f4fc07e9ffb
## Что Нужно

- Python 3.10+
- Discord-бот с включенным `Message Content Intent`
- Telegram-бот от `@BotFather`
- Настроить файл `.env` с токенами
- Настроить файл `config.yaml` с каналами

## Установка

Откройте PowerShell в папке проекта:

```powershell
cd ~\Discord-To-Telegram-forwarding  
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Если виртуальное окружение уже создано, достаточно:

```powershell
cd ~\Discord-To-Telegram-forwarding  
.venv\Scripts\Activate.ps1
```

## Настройка Токенов

Токены хранятся только в `.env`.

Формат `.env`:

```env
DISCORD_BOT_TOKEN=ваш_discord_token
TELEGRAM_BOT_TOKEN=ваш_telegram_token
```
## Настройка Каналов

Каналы настраиваются в `config.yaml`.

Пример:

```yaml
reload_interval_seconds: 3
telegram_file_limit_mb: 20
log_level: INFO
send_retries: 5
retry_base_delay_seconds: 1

routes:
  - discord_channel_id: 111
    telegram_targets:
      - "111"
    message_template: "[Discord] {author}: {content}"
    forward_edits: true
    forward_deletes: true
    include_author_avatar_url: false
    filters: []
```

`discord_channel_id` это ID Discord-канала, откуда читать сообщения.

`telegram_targets` это список Telegram-чатов или каналов, куда отправлять сообщения.

Можно указать несколько Telegram-получателей:

```yaml
telegram_targets:
  - "42"
  - "@public_channel_name"
```

## Запуск

Основная команда:

```powershell
python main.py
```

Полный вариант после перезагрузки терминала:

```powershell
cd ~\Discord-To-Telegram-forwarding  
.venv\Scripts\Activate.ps1
python main.py
```

Если запуск успешный, в консоли появится строка:

```text
Discord bridge connected as BotName#0000
```

После этого новые сообщения из Discord будут пересылаться в Telegram.

## Как Получить ID

Discord channel ID:

1. Откройте Discord.
2. Включите `User Settings -> Advanced -> Developer Mode`.
3. Нажмите правой кнопкой по каналу.
4. Выберите `Copy Channel ID`.

Telegram target:

- Для публичного канала можно использовать `@channel_name`.
- Для приватного канала или группы используйте числовой chat id.
- У Telegram-бота должны быть права отправлять сообщения.

## Discord Bot

В Discord Developer Portal проверьте:

- Бот добавлен на сервер.
- Включен `Message Content Intent`.
- У бота есть доступ к нужному каналу.
- У бота есть права `View Channels` и `Read Message History`.

Замените `APPLICATION_ID` на ID вашего Discord-приложения.

## Telegram Bot

В Telegram:

1. Создайте бота через `@BotFather`.
2. Скопируйте токен в `.env`.
3. Добавьте бота в нужный канал или группу.
4. Для канала назначьте бота администратором.
5. Убедитесь, что бот может отправлять сообщения.

## Логи

Логи пишутся:

- В консоль
- В файл `logs/bridge.log`

По логам видно успешные пересылки и ошибки Telegram/Discord API.

## Возможности

- Пересылка текста
- Пересылка изображений, видео, аудио и файлов
- Несколько Telegram-получателей для одного Discord-канала
- Настраиваемый шаблон сообщения
- Уведомления о редактировании сообщений
- Уведомления об удалении сообщений
- Фильтрация по регулярным выражениям
- Горячая перезагрузка `config.yaml`
- Повторные попытки при временных ошибках API

## Ограничения

- Файлы больше `telegram_file_limit_mb` пропускаются.
- Уведомления об изменении и удалении отправляются отдельными сообщениями.
- Голосовые функции Discord не нужны для обычной пересылки сообщений.

