# Discord -> Telegram Bridge

Асинхронный сервис на Python 3.10+ для пересылки сообщений из каналов Discord в каналы Telegram.

## Возможности

- Пересылка текста, изображений, видео, аудио и файлов.
- Несколько Telegram-каналов на один Discord-канал.
- Настраиваемый шаблон сообщения: `"[Discord] {author}: {content}"`.
- Опциональные уведомления о редактировании и удалении сообщений.
- Фильтрация сообщений по регулярным выражениям.
- Горячая перезагрузка `config.yaml` без перезапуска процесса.
- Логирование в консоль и `logs/bridge.log`.
- Повторные попытки отправки в Telegram с exponential backoff.

## Установка

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux/macOS:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Быстрый запуск на Windows

1. Перевыпустите токены, если они уже были где-то опубликованы.
2. Откройте `.env` и впишите токены:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

3. Откройте `config.yaml` и настройте каналы:

```yaml
routes:
  - discord_channel_id: 123456789012345678
    telegram_targets:
      - "-1001234567890"
```

4. Запустите сервис:

```powershell
python main.py
```

Если нужно запустить в фоне на Windows, можно использовать планировщик задач Windows или NSSM.

## Конфигурация

`config.yaml`:

```yaml
reload_interval_seconds: 3
telegram_file_limit_mb: 20
log_level: INFO

routes:
  - discord_channel_id: 123456789012345678
    telegram_targets:
      - "-1001234567890"
      - "@channel_name"
    message_template: "[Discord] {author}: {content}"
    forward_edits: true
    forward_deletes: true
    include_author_avatar_url: false
    filters:
      - "urgent"
      - "release\\s+note"
```

Поддерживаемые плейсхолдеры шаблона:

- `{author}`
- `{content}`
- `{author_avatar_url}`
- `{discord_channel_id}`
- `{discord_message_id}`

## Ограничения

- Файлы больше лимита Telegram пропускаются и пишутся в лог.
- Для чтения текста сообщений в Discord боту нужен privileged intent `Message Content Intent`.
- Уведомления об edit/delete отправляются как новые сообщения, а не редактируют уже пересланные.
