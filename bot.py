import os
import logging
import aiohttp
import asyncio
from telegram import Update, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CATBOX_USERHASH = os.getenv("CATBOX_USERHASH", "")  # optional – leave blank for anonymous uploads
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def upload_to_catbox(file_bytes: bytes, filename: str) -> str | None:
    """Upload raw bytes to catbox.moe and return the direct URL."""
    url = "https://catbox.moe/user/api.php"
    form = aiohttp.FormData()
    form.add_field("reqtype", "fileupload")
    if CATBOX_USERHASH:
        form.add_field("userhash", CATBOX_USERHASH)
    form.add_field(
        "fileToUpload",
        file_bytes,
        filename=filename,
        content_type="image/jpeg",
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                text = await resp.text()
                if resp.status == 200 and text.startswith("https://"):
                    logger.info(f"Catbox upload success: {text.strip()}")
                    return text.strip()
                else:
                    logger.error(f"Catbox error {resp.status}: {text}")
                    return None
    except Exception as e:
        logger.exception(f"Upload failed: {e}")
        return None


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered for every new post (or forward) in channels where bot is admin."""
    message = update.channel_post or update.message
    if not message:
        return

    # We only care about messages that contain a photo
    if not message.photo:
        return

    chat_id = message.chat_id
    message_id = message.message_id
    caption = message.caption or ""

    logger.info(f"New photo post in chat {chat_id}, msg {message_id}")

    # Grab the highest-resolution photo variant
    photo = message.photo[-1]

    try:
        tg_file = await context.bot.get_file(photo.file_id)
        file_bytes = await tg_file.download_as_bytearray()
    except Exception as e:
        logger.exception(f"Could not download photo: {e}")
        return

    filename = f"{photo.file_unique_id}.jpg"
    catbox_url = await upload_to_catbox(bytes(file_bytes), filename)

    if not catbox_url:
        logger.warning("Skipping edit – catbox upload failed.")
        return

    # Build new caption: append the catbox link
    new_caption = f"{caption}\n\n🔗 Image Link: {catbox_url}".strip()

    try:
        await context.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=new_caption,
        )
        logger.info(f"Post edited successfully with catbox URL.")
    except Exception as e:
        # If message has no caption slot (photo-only, no caption allowed in some edge cases)
        # fall back to sending a reply in the channel
        logger.warning(f"edit_message_caption failed ({e}), trying edit_message_text…")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔗 Image Link: {catbox_url}",
                reply_to_message_id=message_id,
            )
        except Exception as e2:
            logger.exception(f"Fallback send also failed: {e2}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Listen for channel posts that contain photos
    app.add_handler(
        MessageHandler(
            filters.PHOTO & (filters.ChatType.CHANNEL | filters.ChatType.GROUPS),
            handle_channel_post,
        )
    )

    logger.info("Bot started. Listening for channel photo posts…")
    app.run_polling(allowed_updates=["channel_post", "message"])


if __name__ == "__main__":
    main()
