# FAST ASYNC STORAGE BOT (FINAL PRODUCTION VERSION)

import os
import logging
import asyncio
import aiosqlite
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 8369307958

if not TOKEN:
    raise ValueError("❌ TOKEN is missing! Set it in Render Environment Variables")

logging.basicConfig(level=logging.INFO)

# ---------------- FOLDERS ----------------
os.makedirs("downloads/audio", exist_ok=True)
os.makedirs("downloads/documents", exist_ok=True)
os.makedirs("downloads/images", exist_ok=True)

# ---------------- DATABASE ----------------
async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_name TEXT,
            file_type TEXT,
            file_size INTEGER,
            tag TEXT,
            date TEXT
        )
        """)
        await db.commit()

async def save_user(user_id, name):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(
            "INSERT OR IGNORE INTO users VALUES (?, ?)",
            (user_id, name)
        )
        await db.commit()

async def save_file(user_id, file_name, file_type, file_size, tag):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        INSERT INTO files (user_id, file_name, file_type, file_size, tag, date)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id, file_name, file_type,
            file_size, tag,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))
        await db.commit()

# ---------------- COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await save_user(update.effective_user.id, update.effective_user.first_name)

    await update.message.reply_text(
        "Welcome!\n\nSend files with caption (tag)\n\n"
        "Commands:\n/search keyword\n/mystats"
    )

async def mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(
            "SELECT COUNT(*) FROM files WHERE user_id=?",
            (update.effective_user.id,)
        ) as cursor:
            count = (await cursor.fetchone())[0]

    await update.message.reply_text(f"You uploaded {count} files")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    keyword = " ".join(context.args).lower()

    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("""
        SELECT file_name, tag FROM files
        WHERE (file_name LIKE ? OR tag LIKE ?) AND user_id=?
        """, (f"%{keyword}%", f"%{keyword}%", update.effective_user.id)) as cursor:

            results = await cursor.fetchall()

    if results:
        text = "\n".join([f"{r[0]} ({r[1]})" for r in results[:10]])
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("No results found")

# ---------------- FILE HANDLERS ----------------
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.document:
        return

    doc = update.message.document
    caption = update.message.caption or "general"
    tag = caption.split()[0].lower()

    file = await doc.get_file()
    file_name = doc.file_name or f"{doc.file_id}.dat"
    file_path = f"downloads/documents/{file_name}"

    await file.download_to_drive(file_path)

    await save_file(
        update.effective_user.id,
        file_name,
        "document",
        doc.file_size,
        tag
    )

    await update.message.reply_text(f"Saved: {file_name}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()

    file_name = f"{photo.file_id}.jpg"
    file_path = f"downloads/images/{file_name}"

    await file.download_to_drive(file_path)

    await save_file(
        update.effective_user.id,
        file_name,
        "image",
        photo.file_size,
        "image"
    )

    await update.message.reply_text("Image saved")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.audio:
        return

    audio = update.message.audio
    file = await audio.get_file()

    file_name = f"{audio.file_id}.mp3"
    file_path = f"downloads/audio/{file_name}"

    await file.download_to_drive(file_path)

    await save_file(
        update.effective_user.id,
        file_name,
        "audio",
        audio.file_size,
        "audio"
    )

    await update.message.reply_text("Audio saved")

# ---------------- ERROR HANDLER ----------------
async def error_handler(update, context):
    logging.error(f"Update {update} caused error {context.error}")

# ---------------- MAIN ----------------
def main():
    # Run DB init safely
    asyncio.run(init_db())

    # Build bot
    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mystats", mystats))
    app.add_handler(CommandHandler("search", search))

    # File handlers
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))

    # Error handler
    app.add_error_handler(error_handler)

    print("Bot running...")

    # Start bot (correct way)
    app.run_polling()

# ---------------- RUN ----------------
if __name__ == "__main__":
    main()
