import os
import logging
import aiohttp
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CATBOX_USERHASH = os.getenv("CATBOX_USERHASH", "")
PORT = int(os.getenv("PORT", 8080))
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Media Group tracking (pehli image process ho, baaki ignore) ───────────────
processed_media_groups: set = set()
media_group_lock = asyncio.Lock()


# ─── Dummy HTTP server (sirf Render ke liye) ──────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        pass


def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"Health server started on port {PORT}")
    server.serve_forever()


# ─── Catbox Upload ─────────────────────────────────────────────────────────────
async def upload_to_catbox(file_bytes: bytes, filename: str):
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


# ─── Telegram Handler ──────────────────────────────────────────────────────────
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post or update.message
    if not message or not message.photo:
        return

    chat_id = message.chat_id
    message_id = message.message_id
    caption = message.caption or ""
    media_group_id = message.media_group_id  # None agar single image hai

    # ── Media group check ──
    # Agar post mein multiple images hain (album), sirf pehli process karo
    if media_group_id:
        async with media_group_lock:
            if media_group_id in processed_media_groups:
                logger.info(f"Media group {media_group_id} already processed — skipping msg {message_id}")
                return
            # Pehli baar aa rahi hai — mark karo
            processed_media_groups.add(media_group_id)

        # Memory leak rokne ke liye 10 min baad group ID hata do
        async def cleanup():
            await asyncio.sleep(600)
            processed_media_groups.discard(media_group_id)
        asyncio.create_task(cleanup())

    logger.info(f"Processing photo in chat {chat_id}, msg {message_id} (group: {media_group_id})")

    # Highest resolution photo lo
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

    new_caption = f"{caption}\n\n🔗 Image Link: {catbox_url}".strip()

    try:
        await context.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=new_caption,
        )
        logger.info("Post edited successfully with catbox URL.")
    except Exception as e:
        logger.warning(f"edit_message_caption failed ({e}), sending reply…")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔗 Image Link: {catbox_url}",
                reply_to_message_id=message_id,
            )
        except Exception as e2:
            logger.exception(f"Fallback send also failed: {e2}")


# ─── Main ──────────────────────────────────────────────────────────────────────
async def run():
    thread = threading.Thread(target=start_health_server, daemon=True)
    thread.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.PHOTO & (filters.ChatType.CHANNEL | filters.ChatType.GROUPS),
            handle_channel_post,
        )
    )

    logger.info("Bot started. Listening for channel photo posts…")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=["channel_post", "message"])

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run())
