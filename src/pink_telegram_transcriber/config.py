"""Configuration for Pink Telegram Transcriber."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Verbose mode flag (enable detailed logging)
VERBOSE_MODE = os.getenv('VERBOSE') == '1'

# Process identifiers for singleton detection
SINGLETON_IDENTIFIERS = [
    'pink-telegram-transcriber',
    'pink_telegram_transcriber',
    'Pink Telegram Transcriber'
]

# Bot token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not set in .env file", file=sys.stderr)
    sys.exit(1)

# Whitelist of allowed user IDs (comma-separated in .env)
ALLOWED_USER_IDS_STR = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS = set()

if ALLOWED_USER_IDS_STR:
    try:
        ALLOWED_USER_IDS = {int(uid.strip()) for uid in ALLOWED_USER_IDS_STR.split(",") if uid.strip()}
    except ValueError:
        print("ERROR: Invalid ALLOWED_USER_IDS format. Must be comma-separated integers.", file=sys.stderr)
        sys.exit(1)

if not ALLOWED_USER_IDS:
    print("WARNING: No user IDs in whitelist. Bot will not respond to anyone.", file=sys.stderr)


def is_user_allowed(user_id: int) -> bool:
    """Check if user ID is in whitelist."""
    return user_id in ALLOWED_USER_IDS


# Supported audio MIME types for transcription
SUPPORTED_AUDIO_MIMES = {
    'audio/mpeg',      # MP3
    'audio/mp4',       # M4A
    'audio/x-m4a',     # M4A (alternative)
    'audio/mp3',       # MP3 (alternative)
    'audio/wav',       # WAV
    'audio/x-wav',     # WAV (alternative)
    'audio/wave',      # WAV (alternative)
    'audio/ogg',       # OGG
    'audio/opus',      # OPUS
    'audio/flac',      # FLAC
    'audio/x-flac',    # FLAC (alternative)
    'audio/aac',       # AAC
    'audio/aacp',      # AAC (alternative)
    'audio/amr',       # AMR
    'audio/3gpp',      # 3GPP
    'audio/webm',      # WEBM
    'audio/wma',       # WMA
    'audio/x-ms-wma',  # WMA (alternative)
}

# Supported video MIME types (audio will be extracted)
SUPPORTED_VIDEO_MIMES = {
    'video/mp4',
    'video/mpeg',
    'video/quicktime',  # MOV
    'video/x-matroska', # MKV
    'video/webm',
    'video/x-msvideo',  # AVI
    'video/x-flv',      # FLV
    'video/3gpp',       # 3GP
    'video/3gpp2',      # 3G2
}

# File extensions for audio formats (fallback if MIME type not available)
AUDIO_EXTENSIONS = {
    '.mp3', '.m4a', '.wav', '.ogg', '.opus',
    '.flac', '.aac', '.amr', '.wma', '.webm'
}

# File extensions for video formats
VIDEO_EXTENSIONS = {
    '.mp4', '.avi', '.mov', '.mkv', '.webm',
    '.flv', '.3gp', '.3g2', '.mpeg', '.mpg'
}
