# 🔞 Adult Video Downloader Telegram Bot

This is a Telegram bot built using Python and `pyTelegramBotAPI` (Telebot) that allows **18+ users** to download videos from **Pornhub**. It includes **age verification**, **channel subscription checks**, and allows users to set **gender** and **sexual orientation preferences**. 

> ⚠️ **This bot is for educational purposes only.** Ensure you comply with all applicable laws and Telegram's terms of service before deploying such a bot publicly.

---

## 🚀 Features

- 🔞 Age verification system
- 📺 Download videos from Pornhub in various resolutions
- ✅ User data stored in SQLite (status, gender, orientation)
- 📢 Channel membership enforcement
- 🌈 Collects gender and sexual orientation for future personalized recommendations
- 🧠 Uses `yt-dlp` to fetch video info and handle downloads
- 🗑️ Deletes video after 30 seconds to save storage and ensure privacy

---

## 📦 Requirements

- Python 3.8+
- [FFmpeg](https://ffmpeg.org/) (must be installed and accessible)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

---

## 📂 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/DV-XD2028/PH-Downloader-TGbot.git
cd PH-Downloader-TGbot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the Bot

Open the Python file and edit the following variables:

```python
TOKEN = "YOUR_BOT_TOKEN_HERE"
FFMPEG_PATH = "YOUR_FFMPEG_PATH_HERE"
CHANNELS = [
    ("-100XXXXXXXXX", "Channel Name", "https://t.me/your_channel")
]
```

> 🔧 Make sure the `FFMPEG_PATH` points to the actual path of the FFmpeg binary. On most systems, it's simply `"ffmpeg"` if added to your system's PATH.

### 4. Run the Bot

```bash
python your_bot_script.py
```

---

## 🛠 Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and verify age |
| `/age` | Reconfirm age if needed |
| `/user` | Update gender or orientation |

---

## 💬 Buttons

After successful verification, the bot provides the following options:

- `🔍 Find Video` – (Coming Soon) Personalized recommendations
- `💾 Download Video` – Input a Pornhub URL and download in preferred resolution

---

## 🔐 Data Privacy

- User information is stored in a local `SQLite` database (`users.db`)
- Downloaded videos are removed 30 seconds after sending
- No data is shared or sent to third parties

---

## ❗ Disclaimer

This bot is designed for **educational and personal use only**. Distribution or use of adult content may be restricted in some countries. Please use responsibly and ensure compliance with local laws and Telegram guidelines.

---
