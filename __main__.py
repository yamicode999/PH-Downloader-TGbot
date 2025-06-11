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

# Channel Configuration
CHANNELS = [
    ("-1002618499760", "IVR PH", "https://t.me/ivrph3629")
]

# User Preferences
genders = ["♂️ Male", "♀️ Female"]
sexual_orientations = ["💑 Straight", "🏳️‍🌈 Gay", "💜 Bisexual"]

# Admin Configuration
ADMINS = [1684007473]

# Global State Management
video_requests = {}
last_search = {}
user_seen_videos = {}
api = PornhubApi()

# Initialize Pyrogram Client
app = Client(
    "ph_downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Database Setup
def setup_database():
    try:
        conn = sqlite3.connect("users.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            status TEXT,
            gender TEXT,
            orientation TEXT,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        return conn, cursor
    except Exception as e:
        logger.error(f"Database setup error: {e}")
        raise

conn, cursor = setup_database()

# Database Functions
def get_user(user_id):
    try:
        cursor.execute("SELECT status, gender, orientation FROM users WHERE user_id=?", (user_id,))
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None

def set_user(user_id, status=None, gender=None, orientation=None):
    try:
        if get_user(user_id) is None:
            cursor.execute(
                "INSERT INTO users (user_id, status, gender, orientation) VALUES (?, ?, ?, ?)",
                (user_id, status, gender, orientation)
            )
        else:
            updates = []
            params = []
            if status:
                updates.append("status=?")
                params.append(status)
            if gender:
                updates.append("gender=?")
                params.append(gender)
            if orientation:
                updates.append("orientation=?")
                params.append(orientation)
            if updates:
                params.append(user_id)
                cursor.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE user_id=?",
                    params
                )
        conn.commit()
    except Exception as e:
        logger.error(f"Error setting user {user_id}: {e}")
        conn.rollback()

# Helper Functions
async def check_user_membership(user_id):
    not_joined = []
    for channel_id, name, link in CHANNELS:
        try:
            member = await app.get_chat_member(channel_id, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                not_joined.append((name, link))
        except Exception as e:
            logger.error(f"Error checking membership for user {user_id} in channel {channel_id}: {e}")
    return not_joined

def is_verified(user_id):
    try:
        cursor.execute("SELECT status FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        return result and result[0] == "verified"
    except Exception as e:
        logger.error(f"Error checking verification for user {user_id}: {e}")
        return False

async def send_join_message(user_id, not_joined):
    try:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(name, url=link)]
            for name, link in not_joined
        ])
        message_text = "🚨 To use the bot, you must join the following channels:\n\n"
        message_text += "\n".join(f"🔹 {name}" for name, _ in not_joined)
        message_text += "\n\n✅ After joining, press /start again."
        await app.send_message(user_id, message_text, reply_markup=markup)
    except Exception as e:
        logger.error(f"Error sending join message to user {user_id}: {e}")

async def ask_gender(user_id):
    try:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(gender, callback_data=f"gender_{gender}")]
            for gender in genders
        ])
        await app.send_message(user_id, "💬 What is your gender?", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error asking gender to user {user_id}: {e}")

async def ask_orientation(user_id, message_id):
    try:
        await app.delete_messages(user_id, message_id)
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(orientation, callback_data=f"orientation_{orientation}")]
            for orientation in sexual_orientations
        ])
        msg = await app.send_message(user_id, "🌈 What is your sexual orientation?", reply_markup=markup)
        return msg.id
    except Exception as e:
        logger.error(f"Error asking orientation to user {user_id}: {e}")
        return None

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

                await update_status(f"⏳ Downloading video in {quality}p... (Attempt {retry_count + 1}/{max_retries})")
                info = ydl.extract_info(url, download=True)
                video_path = f'video_{user_id}.mp4'
                duration = info.get('duration', 0)

                await update_status("⏳ Uploading video to Telegram...")
                sent_message = await app.send_video(
                    user_id,
                    video_path,
                    duration=duration,
                    progress=lambda current, total: update_status(
                        f"⏳ Uploading: {current * 100 / total:.1f}%"
                    ) if current_msg_id else None
                )

                await app.send_message(user_id, "⚠️ Save the video in your saved messages. It will be deleted in 30 seconds.")
                asyncio.create_task(delete_video_later(user_id, video_path, sent_message.id))
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

async def delete_video_later(user_id, video_path, message_id):
    try:
        await asyncio.sleep(30)
        if os.path.exists(video_path):
            os.remove(video_path)
        try:
            await app.delete_messages(user_id, message_id)
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}")
    except Exception as e:
        logger.error(f"Error in delete_video_later for user {user_id}: {e}")

async def search_pornhub_video(user_id, keyword):
    try:
        user = get_user(user_id)
        if not user:
            await app.send_message(user_id, "❌ User not found in database.")
            return

        gender, orientation = user[1], user[2]
        search_query = keyword
        search_tags = []

        if gender == "♂️ Male":
            if orientation == "🏳️‍🌈 Gay":
                search_tags = ["gay"]
            elif orientation == "💜 Bisexual":
                if random.choice([True, False]):
                    search_tags = ["gay"]
        elif gender == "♀️ Female":
            if orientation == "🏳️‍🌈 Gay":
                search_tags = ["lesbian"]
            elif orientation == "💜 Bisexual":
                if random.choice([True, False]):
                    search_tags = ["lesbian"]

        last_search[user_id] = search_query

        if user_id not in user_seen_videos:
            user_seen_videos[user_id] = set()

        try:
            if search_tags:
                search_result = api.search.search_videos(
                    search_query,
                    tags=search_tags,
                    ordering="mostviewed",
                    period="weekly"
                )
            else:
                search_result = api.search.search_videos(
                    search_query,
                    ordering="mostviewed",
                    period="weekly"
                )

            videos_list = [v for v in search_result if v.video_id not in user_seen_videos[user_id]]

            if not videos_list:
                await app.send_message(user_id, "❌ No more videos found. Try a different search term.")
                return

            video = random.choice(videos_list)
            user_seen_videos[user_id].add(video.video_id)

            title = video.title
            video_url = f"https://www.pornhub.com/view_video.php?viewkey={video.video_id}"
            thumb_url = video.default_thumb

            video_requests[video.video_id] = video_url

            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬇️ Download", callback_data=f"download_{video.video_id}")],
                [InlineKeyboardButton("➡️ Next", callback_data="next_video")]
            ])

            msg = await app.send_photo(
                user_id,
                thumb_url,
                caption=f"🎬 {title}\n🔗 [Watch Video]({video_url})",
                reply_markup=markup
            )
            video_requests[f"msg_{user_id}"] = msg.id

        except Exception as e:
            logger.error(f"Error in video search for user {user_id}: {e}")
            await app.send_message(user_id, "❌ Error searching for videos. Please try again.")

    except Exception as e:
        logger.error(f"Error in search_pornhub_video for user {user_id}: {e}")
        await app.send_message(user_id, "❌ An error occurred. Please try again.")

# Command Handlers
@app.on_message(filters.command("start"))
async def start_command(client, message):
    try:
        user_id = message.from_user.id
        user = get_user(user_id)

        if user and user[0] == "verified":
            not_joined = await check_user_membership(user_id)
            if not_joined:
                await send_join_message(user_id, not_joined)
            elif not user[1]:
                await ask_gender(user_id)
            elif not user[2]:
                await ask_orientation(user_id, message.id)
            else:
                await app.send_message(user_id, "😈 Are you ready for some fun?")
        elif user and user[0] == "underage":
            await app.send_message(user_id, "🚫 You are under 18! If this is incorrect, use /age to update your status.")
        else:
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ I confirm I am 18+", callback_data="verify"),
                    InlineKeyboardButton("❌ No, I am under 18", callback_data="underage")
                ]
            ])
            await app.send_message(user_id, "🔞 You must be 18+ to use this bot. Please confirm:", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in start command for user {message.from_user.id}: {e}")
        await app.send_message(message.from_user.id, "❌ An error occurred. Please try again later.")

@app.on_message(filters.command("age"))
async def update_age_command(client, message):
    try:
        user_id = message.from_user.id
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ I confirm I am 18+", callback_data="verify"),
                InlineKeyboardButton("❌ No, I am under 18", callback_data="underage")
            ]
        ])
        await app.send_message(user_id, "🔄 Update your age confirmation:", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in update_age command for user {message.from_user.id}: {e}")

@app.on_message(filters.command("user"))
async def update_user_command(client, message):
    try:
        user_id = message.from_user.id
        await ask_gender(user_id)
    except Exception as e:
        logger.error(f"Error in update_user command for user {message.from_user.id}: {e}")

@app.on_message(filters.text & filters.regex("^🔍 Find Video$"))
async def find_video_command(client, message):
    try:
        user_id = message.from_user.id
        if not is_verified(user_id):
            await app.send_message(user_id, "🚫 You must verify your age to use this feature!")
            return

        not_joined = await check_user_membership(user_id)
        if not_joined:
            await send_join_message(user_id, not_joined)
            return

        await app.send_message(user_id, "🔎 Enter a keyword to search for videos:")
    except Exception as e:
        logger.error(f"Error in find_video command for user {message.from_user.id}: {e}")

@app.on_message(filters.text & filters.regex("^💾 Download Video$"))
async def download_video_command(client, message):
    try:
        user_id = message.from_user.id
        if not is_verified(user_id):
            await app.send_message(user_id, "🚫 You must verify your age to use this feature!")
            return

        not_joined = await check_user_membership(user_id)
        if not_joined:
            await send_join_message(user_id, not_joined)
            return

        await app.send_message(user_id,
                         "🔗 Please send the Pornhub video link in this format:\nhttps://www.pornhub.com/view_video.php?viewkey=xxx")
    except Exception as e:
        logger.error(f"Error in download_video command for user {message.from_user.id}: {e}")

@app.on_message(filters.text & filters.regex("pornhub.com/view_video.php\\?viewkey="))
async def process_video_link_command(client, message):
    try:
        user_id = message.from_user.id
        if not is_verified(user_id):
            await app.send_message(user_id, "🚫 You must verify your age to use this feature!")
            return

        not_joined = await check_user_membership(user_id)
        if not_joined:
            await send_join_message(user_id, not_joined)
            return

        url = message.text.strip()
        loading_msg = await app.send_message(user_id, "⏳ Fetching video details, please wait...")
        await fetch_video_details(user_id, url, loading_msg.id)
    except Exception as e:
        logger.error(f"Error in process_video_link command for user {message.from_user.id}: {e}")

@app.on_message(filters.text)
async def process_keyword_command(client, message):
    try:
        user_id = message.from_user.id
        if not is_verified(user_id):
            await app.send_message(user_id, "🚫 You must verify your age to use this feature!")
            return

        not_joined = await check_user_membership(user_id)
        if not_joined:
            await send_join_message(user_id, not_joined)
            return

        await search_pornhub_video(user_id, message.text.strip())
    except Exception as e:
        logger.error(f"Error in process_keyword command for user {message.from_user.id}: {e}")

# Callback Query Handlers
@app.on_callback_query(filters.regex("^verify"))
async def verify_callback(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        set_user(user_id, status="verified")
        await callback_query.message.delete()
        not_joined = await check_user_membership(user_id)
        if not_joined:
            await send_join_message(user_id, not_joined)
        else:
            await ask_gender(user_id)
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in verify callback for user {callback_query.from_user.id}: {e}")

@app.on_callback_query(filters.regex("^underage"))
async def underage_callback(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        set_user(user_id, status="underage")
        await callback_query.message.delete()
        await app.send_message(user_id, "🚫 You are under 18! If this is incorrect, use /age to update your status.")
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in underage callback for user {callback_query.from_user.id}: {e}")

@app.on_callback_query(filters.regex("^gender_"))
async def gender_callback(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        gender = callback_query.data.split("_")[1]
        set_user(user_id, gender=gender)
        await ask_orientation(user_id, callback_query.message.id)
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in gender callback for user {callback_query.from_user.id}: {e}")

@app.on_callback_query(filters.regex("^orientation_"))
async def orientation_callback(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        orientation = callback_query.data.split("_")[1]
        set_user(user_id, orientation=orientation)
        await callback_query.message.delete()
        await app.send_message(user_id, "✅ Your information has been saved!\n💡 You can update it anytime with /user")
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in orientation callback for user {callback_query.from_user.id}: {e}")

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

@app.on_callback_query(filters.regex("^next_video$"))
async def next_video_callback(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        if f"msg_{user_id}" in video_requests:
            try:
                await callback_query.message.delete()
            except Exception as e:
                logger.error(f"Error deleting message: {e}")

        if user_id in last_search:
            await search_pornhub_video(user_id, last_search[user_id])
        else:
            await app.send_message(user_id, "❌ No previous search found.")
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in next_video callback for user {callback_query.from_user.id}: {e}")

@app.on_callback_query(filters.regex("^download_"))
async def download_callback(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        video_id = callback_query.data.replace("download_", "")

        if not is_verified(user_id):
            await app.send_message(user_id, "🚫 You must verify your age to use this feature!")
            return

        video_url = video_requests.get(video_id)
        if not video_url:
            await app.send_message(user_id, "❌ Video not found.")
            return

        waiting_msg = await app.send_message(user_id, "⏳ Fetching video details, please wait...")
        await fetch_video_details(user_id, video_url, waiting_msg.id)
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in download callback for user {callback_query.from_user.id}: {e}")

# Start the bot
if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        app.run()
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
