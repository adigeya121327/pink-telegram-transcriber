# Pink Telegram Transcriber

Simple Telegram bot for voice message transcription using the Pink Transcriber service.

## Features

- Receives voice messages from Telegram
- Transcribes using Pink Transcriber service
- Returns transcribed text
- Whitelist-based access control
- Simple and lightweight

## Requirements

- Python 3.12+
- [Pink Transcriber](https://github.com/pinkhairedboy/pink-transcriber) service running
- Telegram Bot Token

## Installation

1. Clone the repository:
```bash
cd ~/
git clone https://github.com/pinkhairedboy/pink-telegram-transcriber.git
cd pink-telegram-transcriber
```

2. Install dependencies with uv:
```bash
uv sync
```

3. Configure the bot:
```bash
cp .env.example .env
nano .env
```

Fill in:
- `TELEGRAM_BOT_TOKEN` - Get from [@BotFather](https://t.me/BotFather)
- `ALLOWED_USER_IDS` - Comma-separated user IDs (get from [@userinfobot](https://t.me/userinfobot))

## Usage

1. Make sure Pink Transcriber service is running:
```bash
pink-transcriber-server
```

2. Start the bot:
```bash
uv run pink-telegram-transcriber
```

3. Send voice messages to your bot on Telegram

### Windows (WSL)

Double-click `Start Pink Telegram Transcriber.bat` on Desktop

## Creating Your Bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow instructions to create bot
4. Copy the token to `.env`

## Getting Your User ID

1. Open [@userinfobot](https://t.me/userinfobot) on Telegram
2. Send any message
3. Copy your user ID to `.env` in `ALLOWED_USER_IDS`

## Architecture

```
Voice Message → Download → Pink Transcriber → Text → Reply
```

The bot:
1. Receives voice message from whitelisted users
2. Downloads .ogg file to temp directory
3. Calls `pink-transcriber` CLI to transcribe
4. Sends transcribed text back to user
5. Cleans up temp files

## License

MIT License - see LICENSE file for details

## Author

pinkhairedboy
