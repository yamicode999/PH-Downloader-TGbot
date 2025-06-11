import os
import time
import logging
import asyncio
import yt_dlp
import sqlite3
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import MessageNotModified, MessageDeleteForbidden
from pornhub_api import PornhubApi
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
API_ID = "23768009"  # Replace with your API ID
API_HASH = "213c50b464e39d3bf8e3727b0201b7df"  # Replace with your API Hash
BOT_TOKEN = "7565788963:AAEQyRSzb-0zP3q7kE5B1skcwpNwkPWIOX4"
FFMPEG_PATH = "/usr/bin/ffmpeg"
MAX_DOWNLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
MAX_RETRIES = 3
DOWNLOAD_TIMEOUT = 300  # 5 minutes
CHUNK_SIZE = 10485760  # 10MB

# Global State Management
video_requests = {}
api = PornhubApi()

# Initialize Pyrogram Client
app = Client(
    "ph_downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Command Handlers
@app.on_message(filters.command("start"))
async def start_command(client, message):
    try:
        user_id = message.from_user.id
        await app.send_message(user_id, "😈 Welcome to the video downloader bot!\nUse /download to start downloading videos.")
    except Exception as e:
        logger.error(f"Error in start command for user {message.from_user.id}: {e}")
        await app.send_message(message.from_user.id, "❌ An error occurred. Please try again later.")

@app.on_message(filters.command("download"))
async def download_video_command(client, message):
    try:
        user_id = message.from_user.id
        await app.send_message(user_id,
                         "🔗 Please send the Pornhub video link in this format:\nhttps://www.pornhub.com/view_video.php?viewkey=xxx")
    except Exception as e:
        logger.error(f"Error in download_video command for user {message.from_user.id}: {e}")

@app.on_message(filters.text & filters.regex("pornhub.com/view_video.php\\?viewkey="))
async def process_video_link_command(client, message):
    try:
        user_id = message.from_user.id
        url = message.text.strip()
        loading_msg = await app.send_message(user_id, "⏳ Fetching video details, please wait...")
        await fetch_video_details(user_id, url, loading_msg.id)
    except Exception as e:
        logger.error(f"Error in process_video_link command for user {message.from_user.id}: {e}")

@app.on_callback_query(filters.regex("^quality_"))
async def quality_callback(client, callback_query):
    try:
        quality = callback_query.data.split("_")[1]
        user_id = callback_query.from_user.id
        url = video_requests.get(user_id)

        if not url:
            await app.send_message(user_id, "❌ No video request found.")
            return

        await callback_query.message.delete()
        status_msg = await app.send_message(user_id, f"⏳ Downloading video in {quality}p...")
        await process_download(user_id, url, quality, status_msg.id)
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in quality callback for user {callback_query.from_user.id}: {e}")

# Start the bot
if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        app.run()
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
