import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReactionTypeEmoji
import sqlite3
import yt_dlp
import os
import threading
import random
import hashlib
import time
from pornhub_api import PornhubApi
import logging
import sys
from urllib.parse import urlparse, parse_qs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Bot Configuration
TOKEN = "7565788963:AAEQyRSzb-0zP3q7kE5B1skcwpNwkPWIOX4"
bot = telebot.TeleBot(TOKEN)

# Constants
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
admin_states = {}
admin_messages = {}
api = PornhubApi()

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

def check_user_membership(user_id):
    not_joined = []
    for channel_id, name, link in CHANNELS:
        try:
            chat_member = bot.get_chat_member(channel_id, user_id)
            if chat_member.status not in ["member", "administrator", "creator"]:
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

def send_join_message(user_id, not_joined):
    try:
        markup = InlineKeyboardMarkup()
        message_text = "🚨 To use the bot, you must join the following channels:\n\n"
        for name, link in not_joined:
            message_text += f"🔹 {name}\n"
            btn = InlineKeyboardButton(name, url=link)
            markup.add(btn)
        message_text += "\n✅ After joining, press /start again."
        bot.send_message(user_id, message_text, reply_markup=markup)
    except Exception as e:
        logger.error(f"Error sending join message to user {user_id}: {e}")

def ask_gender(user_id):
    try:
        markup = InlineKeyboardMarkup()
        for gender in genders:
            markup.add(InlineKeyboardButton(gender, callback_data=f"gender_{gender}"))
        bot.send_message(user_id, "💬 What is your gender?", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error asking gender to user {user_id}: {e}")

def ask_orientation(user_id, message_id):
    try:
        bot.delete_message(user_id, message_id)
        markup = InlineKeyboardMarkup()
        for orientation in sexual_orientations:
            markup.add(InlineKeyboardButton(orientation, callback_data=f"orientation_{orientation}"))
        msg = bot.send_message(user_id, "🌈 What is your sexual orientation?", reply_markup=markup)
        return msg.message_id
    except Exception as e:
        logger.error(f"Error asking orientation to user {user_id}: {e}")
        return None

# Main menu setup
main_menu_markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
main_menu_markup.add(
    KeyboardButton("🔍 Find Video"),
    KeyboardButton("💾 Download Video")
)

@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.chat.id
        user = get_user(user_id)

        if user and user[0] == "verified":
            not_joined = check_user_membership(user_id)
            if not_joined:
                send_join_message(user_id, not_joined)
            elif not user[1]:
                ask_gender(user_id)
            elif not user[2]:
                ask_orientation(user_id, message.message_id)
            else:
                bot.send_message(user_id, "😈 Are you ready for some fun?", reply_markup=main_menu_markup)
        elif user and user[0] == "underage":
            bot.send_message(user_id, "🚫 You are under 18! If this is incorrect, use /age to update your status.")
        else:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("✅ I confirm I am 18+", callback_data="verify"),
                InlineKeyboardButton("❌ No, I am under 18", callback_data="underage")
            )
            bot.send_message(user_id, "🔞 You must be 18+ to use this bot. Please confirm:", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in start command for user {message.chat.id}: {e}")
        bot.send_message(message.chat.id, "❌ An error occurred. Please try again later.")

def fetch_video_details(user_id, url, loading_msg_id, waiting_msg_id):
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

            # Delete loading messages with error handling
            for msg_id in [loading_msg_id, waiting_msg_id]:
                if msg_id:
                    try:
                        bot.delete_message(user_id, msg_id)
                    except Exception as e:
                        logger.error(f"Error deleting message {msg_id}: {e}")

            video_requests[user_id] = url

            markup = InlineKeyboardMarkup()
            for q in available_formats:
                markup.add(InlineKeyboardButton(f"{q}p", callback_data=f"quality_{q}"))

            msg = bot.send_photo(user_id, thumbnail, caption=caption, reply_markup=markup, parse_mode='HTML')
            video_requests[f"msg_{user_id}"] = msg.message_id

    except Exception as e:
        logger.error(f"Error fetching video details for user {user_id}: {e}")
        try:
            if loading_msg_id:
                bot.delete_message(user_id, loading_msg_id)
        except Exception as del_e:
            logger.error(f"Error deleting loading message: {del_e}")
        bot.send_message(user_id, f"❌ Error fetching video details: {str(e)}")

def process_download(user_id, url, quality, downloading_msg_id):
    max_retries = MAX_RETRIES
    retry_count = 0
    
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
                    try:
                        bot.delete_message(user_id, downloading_msg_id)
                    except Exception as e:
                        logger.error(f"Error deleting downloading message: {e}")
                    
                    bot.send_message(user_id,
                                 "❌ The selected quality exceeds the allowed limit! Please choose a lower quality.")
                    return

                info = ydl.extract_info(url, download=True)
                video_path = f'video_{user_id}.mp4'
                duration = info.get('duration', 0)

                try:
                    bot.delete_message(user_id, downloading_msg_id)
                except Exception as e:
                    logger.error(f"Error deleting downloading message: {e}")

                with open(video_path, 'rb') as video_file:
                    sent_message = bot.send_video(user_id, video=video_file, duration=duration)

                bot.send_message(user_id, "⚠️ Save the video in your saved messages. It will be deleted in 30 seconds.")
                threading.Thread(target=delete_video_later, args=(user_id, video_path, sent_message.message_id)).start()
                return

        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                try:
                    bot.edit_message_text(
                        f"⏳ Download attempt {retry_count} failed. Retrying... ({retry_count}/{max_retries})",
                        user_id,
                        downloading_msg_id
                    )
                except Exception as edit_e:
                    logger.error(f"Error updating download status message: {edit_e}")
                time.sleep(5)
                continue
            else:
                try:
                    bot.delete_message(user_id, downloading_msg_id)
                except Exception as del_e:
                    logger.error(f"Error deleting downloading message: {del_e}")
                bot.send_message(user_id, f"❌ Error downloading video after {max_retries} attempts: {str(e)}")
                return

def delete_video_later(user_id, video_path, message_id):
    try:
        time.sleep(30)
        if os.path.exists(video_path):
            os.remove(video_path)
        try:
            bot.delete_message(user_id, message_id)
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}")
    except Exception as e:
        logger.error(f"Error in delete_video_later for user {user_id}: {e}")

def search_pornhub_video(user_id, keyword):
    try:
        user = get_user(user_id)
        if not user:
            bot.send_message(user_id, "❌ User not found in database.")
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

        while True:
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
                    bot.send_message(user_id, "❌ No more videos found. Try a different search term.")
                    return

                video = random.choice(videos_list)
                user_seen_videos[user_id].add(video.video_id)

                title = video.title
                video_url = f"https://www.pornhub.com/view_video.php?viewkey={video.video_id}"
                thumb_url = video.default_thumb

                video_requests[video.video_id] = video_url

                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("⬇️ Download", callback_data=f"download_{video.video_id}"))
                markup.add(InlineKeyboardButton("➡️ Next", callback_data="next_video"))

                msg = bot.send_photo(
                    user_id,
                    thumb_url,
                    caption=f"🎬 {title}\n🔗 [Watch Video]({video_url})",
                    parse_mode="Markdown",
                    reply_markup=markup
                )
                video_requests[f"msg_{user_id}"] = msg.message_id
                break

            except Exception as e:
                logger.error(f"Error in video search for user {user_id}: {e}")
                bot.send_message(user_id, "❌ Error searching for videos. Please try again.")
                return

    except Exception as e:
        logger.error(f"Error in search_pornhub_video for user {user_id}: {e}")
        bot.send_message(user_id, "❌ An error occurred. Please try again.")

# Message Handlers
@bot.message_handler(commands=['age'])
def update_age(message):
    try:
        user_id = message.chat.id
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ I confirm I am 18+", callback_data="verify"),
            InlineKeyboardButton("❌ No, I am under 18", callback_data="underage")
        )
        bot.send_message(user_id, "🔄 Update your age confirmation:", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in update_age for user {message.chat.id}: {e}")

@bot.message_handler(commands=['user'])
def update_user_info(message):
    try:
        user_id = message.chat.id
        ask_gender(user_id)
    except Exception as e:
        logger.error(f"Error in update_user_info for user {message.chat.id}: {e}")

@bot.message_handler(func=lambda message: message.text == "🔍 Find Video")
def ask_for_keyword(message):
    try:
        user_id = message.chat.id
        if not is_verified(user_id):
            bot.send_message(user_id, "🚫 You must verify your age to use this feature!")
            return

        not_joined = check_user_membership(user_id)
        if not_joined:
            send_join_message(user_id, not_joined)
            return

        bot.send_message(user_id, "🔎 Enter a keyword to search for videos:")
    except Exception as e:
        logger.error(f"Error in ask_for_keyword for user {message.chat.id}: {e}")

@bot.message_handler(func=lambda message: message.text == "💾 Download Video")
def request_video_link(message):
    try:
        user_id = message.chat.id
        if not is_verified(user_id):
            bot.send_message(user_id, "🚫 You must verify your age to use this feature!")
            return

        not_joined = check_user_membership(user_id)
        if not_joined:
            send_join_message(user_id, not_joined)
            return

        bot.send_message(user_id,
                     "🔗 Please send the Pornhub video link in this format:\nhttps://www.pornhub.com/view_video.php?viewkey=xxx")
    except Exception as e:
        logger.error(f"Error in request_video_link for user {message.chat.id}: {e}")

@bot.message_handler(func=lambda message: "pornhub.com/view_video.php?viewkey=" in message.text)
def process_video_link(message):
    try:
        user_id = message.chat.id
        if not is_verified(user_id):
            bot.send_message(user_id, "🚫 You must verify your age to use this feature!")
            return

        not_joined = check_user_membership(user_id)
        if not_joined:
            send_join_message(user_id, not_joined)
            return

        url = message.text.strip()
        try:
            bot.set_message_reaction(chat_id=user_id, message_id=message.message_id, reaction=[ReactionTypeEmoji("😈")])
        except Exception as e:
            logger.error(f"Error setting reaction: {e}")

        loading_msg = bot.send_message(user_id, "⏳ Fetching video details, please wait...")
        thread = threading.Thread(target=fetch_video_details, args=(user_id, url, loading_msg.message_id, None))
        thread.start()
    except Exception as e:
        logger.error(f"Error in process_video_link for user {message.chat.id}: {e}")

@bot.message_handler(func=lambda message: True)
def process_keyword(message):
    try:
        user_id = message.chat.id
        if user_id in admin_states and admin_states[user_id] == "collecting":
            return

        if not is_verified(user_id):
            bot.send_message(user_id, "🚫 You must verify your age to use this feature!")
            return

        not_joined = check_user_membership(user_id)
        if not_joined:
            send_join_message(user_id, not_joined)
            return

        thread = threading.Thread(target=search_pornhub_video, args=(user_id, message.text.strip()))
        thread.start()
    except Exception as e:
        logger.error(f"Error in process_keyword for user {message.chat.id}: {e}")

# Callback Handlers
@bot.callback_query_handler(func=lambda call: call.data.startswith("verify"))
def verify_callback(call):
    try:
        user_id = call.message.chat.id
        set_user(user_id, status="verified")
        bot.delete_message(user_id, call.message.message_id)
        not_joined = check_user_membership(user_id)
        if not_joined:
            send_join_message(user_id, not_joined)
        else:
            ask_gender(user_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in verify_callback for user {call.message.chat.id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("underage"))
def underage_callback(call):
    try:
        user_id = call.message.chat.id
        set_user(user_id, status="underage")
        bot.delete_message(user_id, call.message.message_id)
        bot.send_message(user_id, "🚫 You are under 18! If this is incorrect, use /age to update your status.")
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in underage_callback for user {call.message.chat.id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("gender_"))
def gender_callback(call):
    try:
        user_id = call.message.chat.id
        gender = call.data.split("_")[1]
        set_user(user_id, gender=gender)
        msg_id = ask_orientation(user_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in gender_callback for user {call.message.chat.id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("orientation_"))
def orientation_callback(call):
    try:
        user_id = call.message.chat.id
        orientation = call.data.split("_")[1]
        set_user(user_id, orientation=orientation)
        bot.delete_message(user_id, call.message.message_id)
        bot.send_message(user_id, "✅ Your information has been saved!\n💡 You can update it anytime with /user", reply_markup=main_menu_markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in orientation_callback for user {call.message.chat.id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("quality_"))
def download_video(call):
    try:
        quality = call.data.split("_")[1]
        user_id = call.message.chat.id
        url = video_requests.get(user_id)

        if not url:
            bot.send_message(user_id, "❌ No video request found.")
            return

        bot.delete_message(user_id, video_requests.get(f"msg_{user_id}"))
        downloading_msg = bot.send_message(user_id, f"⏳ Downloading video in {quality}p...")
        thread = threading.Thread(target=process_download, args=(user_id, url, quality, downloading_msg.message_id))
        thread.start()
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in download_video for user {call.message.chat.id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "next_video")
def next_video(call):
    try:
        user_id = call.message.chat.id
        if f"msg_{user_id}" in video_requests:
            try:
                bot.delete_message(user_id, video_requests[f"msg_{user_id}"])
            except Exception as e:
                logger.error(f"Error deleting message: {e}")

        if user_id in last_search:
            thread = threading.Thread(target=search_pornhub_video, args=(user_id, last_search[user_id]))
            thread.start()
        else:
            bot.send_message(user_id, "❌ No previous search found.")
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in next_video for user {call.message.chat.id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("download_"))
def handle_download_request(call):
    try:
        user_id = call.message.chat.id
        video_id = call.data.replace("download_", "")

        if not is_verified(user_id):
            bot.send_message(user_id, "🚫 You must verify your age to use this feature!")
            return

        video_url = video_requests.get(video_id)
        if not video_url:
            bot.send_message(user_id, "❌ Video not found.")
            return

        waiting_msg = bot.send_message(user_id, "⏳ Fetching video details, please wait...")
        thread = threading.Thread(target=fetch_video_details, args=(user_id, video_url, call.message.message_id, waiting_msg.message_id))
        thread.start()
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in handle_download_request for user {call.message.chat.id}: {e}")

# Set bot commands
bot.set_my_commands([
    telebot.types.BotCommand("start", "Start the bot"),
    telebot.types.BotCommand("age", "Update your age confirmation"),
    telebot.types.BotCommand("user", "Update your gender and orientation")
])

# Start the bot
if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
