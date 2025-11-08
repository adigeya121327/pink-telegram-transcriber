#!/usr/bin/env python3
"""
Pink Telegram Transcriber - Simple voice transcription bot.

Receives voice messages, transcribes them using pink-transcriber service,
and sends back the transcribed text.
"""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional

from telegram import Update, Message
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

from pink_telegram_transcriber.config import (
    TELEGRAM_BOT_TOKEN, is_user_allowed, ALLOWED_USER_IDS,
    SUPPORTED_AUDIO_MIMES, SUPPORTED_VIDEO_MIMES,
    AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
)
from pink_telegram_transcriber.transcriber import check_service, transcribe

# Queue for sequential media processing
media_queue: asyncio.Queue = None
media_worker_task: asyncio.Task = None


def is_audio_file(mime_type: Optional[str], file_name: Optional[str]) -> bool:
    """Check if file is a supported audio format."""
    if mime_type and mime_type in SUPPORTED_AUDIO_MIMES:
        return True

    if file_name:
        ext = Path(file_name).suffix.lower()
        return ext in AUDIO_EXTENSIONS

    return False


def is_video_file(mime_type: Optional[str], file_name: Optional[str]) -> bool:
    """Check if file is a supported video format."""
    if mime_type and mime_type in SUPPORTED_VIDEO_MIMES:
        return True

    if file_name:
        ext = Path(file_name).suffix.lower()
        return ext in VIDEO_EXTENSIONS

    return False


def extract_audio_from_video(video_path: Path, output_path: Path) -> bool:
    """
    Extract audio from video file using ffmpeg.

    Args:
        video_path: Path to video file
        output_path: Path to save extracted audio

    Returns:
        True if extraction successful, False otherwise
    """
    try:
        result = subprocess.run(
            [
                'ffmpeg',
                '-i', str(video_path),
                '-vn',  # No video
                '-acodec', 'libmp3lame',  # MP3 codec
                '-ar', '16000',  # 16kHz sample rate (optimal for Whisper)
                '-ac', '1',  # Mono
                '-y',  # Overwrite output file
                str(output_path)
            ],
            capture_output=True,
            text=True
            # No timeout - allow processing of large files
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[Error] Failed to extract audio: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user_id = update.effective_user.id

    if not is_user_allowed(user_id):
        await update.message.reply_text(
            "⛔ Access denied. This bot is private."
        )
        return

    await update.message.reply_text(
        "🎤 Pink Telegram Transcriber\n\n"
        "Send me audio or video and I'll transcribe it to text.\n\n"
        "Supported formats:\n"
        "• Voice messages\n"
        "• Video notes (circles/кружочки)\n"
        "• Audio files (MP3, M4A, WAV, OGG, FLAC, etc.)\n"
        "• Video files (audio will be extracted)\n\n"
        "Just send - I'll handle the rest!"
    )


async def media_worker(bot):
    """Worker that processes media files (voice, audio, video, video_note) from queue sequentially."""
    global media_queue

    while True:
        try:
            # Get next media file from queue
            file_id, message, status_msg, is_video, file_name = await media_queue.get()

            message_id = message.message_id
            temp_dir = Path(tempfile.gettempdir()) / "pink-telegram-transcriber"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Get file extension from file_name
            file_ext = Path(file_name).suffix if file_name else ""
            if not file_ext:
                file_ext = ".mp4" if is_video else ".mp3"

            # Determine file paths
            if is_video:
                download_path = temp_dir / f"{message_id}{file_ext}"
                audio_path = temp_dir / f"{message_id}_audio.mp3"
            else:
                download_path = temp_dir / f"{message_id}{file_ext}"
                audio_path = download_path

            try:
                # Download media file
                file = await bot.get_file(file_id)
                await file.download_to_drive(download_path)

                # Extract audio from video if needed
                if is_video:
                    try:
                        await status_msg.edit_text("🎬 Extracting audio from video...")
                    except BadRequest:
                        pass  # Message not modified

                    loop = asyncio.get_event_loop()
                    success = await loop.run_in_executor(
                        None, extract_audio_from_video, download_path, audio_path
                    )
                    if not success:
                        raise RuntimeError("Failed to extract audio from video")

                    # Clean up video file
                    os.remove(download_path)

                    # Update status for transcription
                    try:
                        await status_msg.edit_text("🎧 Transcribing...")
                    except BadRequest:
                        pass  # Message not modified

                # For audio files, status is already "🎧 Transcribing..." - no need to update

                # Transcribe (blocking call, but sequential)
                loop = asyncio.get_event_loop()
                transcribed_text = await loop.run_in_executor(None, transcribe, str(audio_path))

                # Clean up audio file
                if audio_path.exists():
                    os.remove(audio_path)

                # Send transcription (plain text, no emoji)
                try:
                    await status_msg.edit_text(transcribed_text)
                except BadRequest:
                    # If edit fails, send as new message
                    await message.reply_text(transcribed_text)

            except Exception as e:
                # Clean up temp files on error
                if download_path.exists():
                    os.remove(download_path)
                if is_video and audio_path.exists():
                    os.remove(audio_path)

                await status_msg.edit_text(f"❌ Error: {str(e)}")

            finally:
                media_queue.task_done()

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Worker] Error: {e}")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming media (voice, audio, video, video_note, documents) by adding to queue."""
    global media_queue

    user_id = update.effective_user.id

    # Check whitelist
    if not is_user_allowed(user_id):
        await update.message.reply_text("⛔ Access denied.")
        return

    message = update.message
    file_id = None
    is_video = False
    file_name = None

    # Determine media type and get file_id
    if message.voice:
        file_id = message.voice.file_id
        file_name = "voice.ogg"
        is_video = False

    elif message.video_note:
        # Video notes (кружочки)
        file_id = message.video_note.file_id
        file_name = "video_note.mp4"
        is_video = True

    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "audio.mp3"
        is_video = False

    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "video.mp4"
        is_video = True

    elif message.document:
        doc = message.document
        mime_type = doc.mime_type
        file_name = doc.file_name

        # Check if document is audio or video
        if is_audio_file(mime_type, file_name):
            file_id = doc.file_id
            is_video = False
        elif is_video_file(mime_type, file_name):
            file_id = doc.file_id
            is_video = True
        else:
            # Not a supported format
            await message.reply_text(
                "⚠️ Unsupported file format.\n\n"
                "Supported formats: audio (MP3, WAV, M4A, OGG, FLAC, etc.) "
                "and video files (audio will be extracted)."
            )
            return

    if not file_id:
        # Unknown media type
        return

    # Send processing indicator
    if is_video:
        status_msg = await message.reply_text("🎬 Processing video...")
    else:
        status_msg = await message.reply_text("🎧 Transcribing...")

    # Add to queue for sequential processing
    await media_queue.put((file_id, message, status_msg, is_video, file_name))


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages (just inform user to send media)."""
    user_id = update.effective_user.id

    if not is_user_allowed(user_id):
        return

    await update.message.reply_text(
        "🎤 Please send audio or video for transcription.\n\n"
        "Supported formats:\n"
        "• Voice messages\n"
        "• Video notes (circles/кружочки)\n"
        "• Audio files (MP3, M4A, WAV, OGG, FLAC, etc.)\n"
        "• Video files (audio will be extracted)"
    )


def create_application() -> Application:
    """Create and configure the bot application."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))

    # Media handlers (voice, audio, video, video_note, documents)
    application.add_handler(MessageHandler(filters.VOICE, handle_media))
    application.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_media))
    application.add_handler(MessageHandler(filters.AUDIO, handle_media))
    application.add_handler(MessageHandler(filters.VIDEO, handle_media))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_media))

    # Text handler (fallback)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    return application


async def post_init(application: Application) -> None:
    """Called after bot initialization."""
    global media_queue, media_worker_task

    # Initialize media queue
    media_queue = asyncio.Queue()

    # Start media worker
    media_worker_task = asyncio.create_task(media_worker(application.bot))

    # Get bot info
    bot_info = await application.bot.get_me()
    bot_name = bot_info.first_name

    print(f"[Bot] {bot_name} started")
    print(f"[Bot] Allowed users: {', '.join(map(str, ALLOWED_USER_IDS))}")

    # Check transcriber service
    if not check_service():
        print("[Warning] pink-transcriber service is not available")
        print("[Warning] Media transcription will fail until service starts")


async def run_bot():
    """Run the bot with proper async shutdown."""
    import signal

    application = create_application()
    stop_event = asyncio.Event()

    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    # Initialize
    await application.initialize()
    await post_init(application)

    # Start polling
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    # Run until stopped
    try:
        await stop_event.wait()
    finally:
        # Cleanup
        global media_worker_task
        if media_worker_task:
            media_worker_task.cancel()
            await asyncio.gather(media_worker_task, return_exceptions=True)

        await application.updater.stop()
        await application.stop()
        await application.shutdown()


def main() -> None:
    """Entry point for the bot."""
    import sys

    # Ensure only one instance runs
    from pink_telegram_transcriber.daemon.singleton import ensure_single_instance
    ensure_single_instance('pink-telegram-transcriber')

    print("[Bot] Starting Pink Telegram Transcriber...")

    # Check transcriber service
    if not check_service():
        print("[Warning] pink-transcriber service is not running")
        print("[Warning] Start the service with: pink-transcriber-server")

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\n[Bot] Shutting down...")

    sys.exit(0)


if __name__ == "__main__":
    main()
