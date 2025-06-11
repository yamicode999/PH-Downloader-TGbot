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

# Video Processing Functions
async def fetch_video_details(user_id, url, loading_msg_id):
    try:
        ydl_opts = {
            'quiet': True,
            'noplaylist': True,
            'skip_download': True,
            'ffmpeg_location': FFMPEG_PATH,
            'socket_timeout': 30,
            'extractor_retries': 3
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown Title')
            views = info.get('view_count', 0)
            likes = info.get('like_count', 0)
            uploader = info.get('uploader', 'Unknown')
            duration = info.get('duration', 0)
            thumbnail = info.get('thumbnail', '')
            available_formats = sorted(set([fmt.get('height') for fmt in info.get('formats', []) if fmt.get('height')]), reverse=True)

            minutes, seconds = divmod(duration, 60)
            duration_text = f"{minutes}:{seconds:02d}"
            caption = f"<b>{title}</b>\n⏳ Duration: {duration_text}\n👀 Views: {views}\n👍 Likes: {likes}\n🎥 Uploader: {uploader}"

            try:
                await app.delete_messages(user_id, loading_msg_id)
            except Exception as e:
                logger.error(f"Error deleting loading message: {e}")

            video_requests[user_id] = url

            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{q}p", callback_data=f"quality_{q}")]
                for q in available_formats
            ])

            msg = await app.send_photo(user_id, thumbnail, caption=caption, reply_markup=markup)
            video_requests[f"msg_{user_id}"] = msg.id

    except Exception as e:
        logger.error(f"Error fetching video details for user {user_id}: {e}")
        try:
            await app.delete_messages(user_id, loading_msg_id)
        except Exception as del_e:
            logger.error(f"Error deleting loading message: {del_e}")
        await app.send_message(user_id, f"❌ Error fetching video details: {str(e)}")

async def process_download(user_id, url, quality, status_msg_id):
    max_retries = MAX_RETRIES
    retry_count = 0
    current_msg_id = status_msg_id
    last_progress = 0

    async def update_status(text):
        nonlocal current_msg_id
        try:
            if current_msg_id:
                await app.edit_message_text(user_id, current_msg_id, text)
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            try:
                msg = await app.send_message(user_id, text)
                current_msg_id = msg.id
            except Exception as send_e:
                logger.error(f"Error sending new status: {send_e}")
                current_msg_id = None

    def sanitize_filename(filename):
        # Remove invalid characters and limit length
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')
        # Limit length to 100 characters
        return filename[:100]

    while retry_count < max_retries:
        try:
            ydl_opts = {
                'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
                'outtmpl': f'video_{user_id}.mp4',
                'quiet': True,
                'retries': 3,
                'socket_timeout': DOWNLOAD_TIMEOUT,
                'http_chunk_size': CHUNK_SIZE,
                'ffmpeg_location': FFMPEG_PATH,
                'extractor_retries': 3,
                'fragment_retries': 3,
                'file_access_retries': 3,
                'retry_sleep_functions': {
                    'http': lambda x: 5,
                    'fragment': lambda x: 5,
                    'file_access': lambda x: 5,
                }
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                selected_format = next(
                    (f for f in info['formats'] if f.get('height') == int(quality)), None
                )

                filesize = selected_format.get('filesize') if selected_format else None

                if filesize and filesize > MAX_DOWNLOAD_SIZE:
                    await app.send_message(user_id,
                                     "❌ The selected quality exceeds the allowed limit! Please choose a lower quality.")
                    return

                # Get original title and sanitize it
                original_title = info.get('title', 'Unknown Title')
                sanitized_title = sanitize_filename(original_title)
                video_filename = f"{sanitized_title}.mp4"

                await update_status(f"⏳ Downloading video in {quality}p... (Attempt {retry_count + 1}/{max_retries})")
                info = ydl.extract_info(url, download=True)
                video_path = f'video_{user_id}.mp4'
                duration = info.get('duration', 0)
                thumbnail = info.get('thumbnail', '')

                # Download thumbnail if available
                thumb_path = None
                if thumbnail:
                    try:
                        thumb_path = f'thumb_{user_id}.jpg'
                        response = requests.get(thumbnail)
                        if response.status_code == 200:
                            with open(thumb_path, 'wb') as f:
                                f.write(response.content)
                    except Exception as e:
                        logger.error(f"Error downloading thumbnail: {e}")
                        thumb_path = None

                await update_status("⏳ Uploading video to Telegram...")
                
                async def progress_callback(current, total):
                    nonlocal last_progress
                    if current_msg_id:
                        progress = int((current * 100) / total)
                        if progress >= last_progress + 20 or progress == 100:
                            await update_status(f"⏳ Uploading: {progress}%")
                            last_progress = progress

                sent_message = await app.send_video(
                    user_id,
                    video_path,
                    duration=duration,
                    progress=progress_callback,
                    thumb=thumb_path if thumb_path else None,
                    supports_streaming=True,
                    file_name=video_filename  # Use original video title as filename
                )

                # Clean up temporary files
                if os.path.exists(video_path):
                    os.remove(video_path)
                if thumb_path and os.path.exists(thumb_path):
                    os.remove(thumb_path)

                return

        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                await update_status(f"⏳ Download attempt {retry_count} failed. Retrying... ({retry_count}/{max_retries})")
                await asyncio.sleep(5)
                continue
            else:
                await app.send_message(user_id, f"❌ Error downloading video after {max_retries} attempts: {str(e)}")
                return

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
if __name__ == "main":
    try:
        logger.info("Starting bot...")
        app.run()
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
