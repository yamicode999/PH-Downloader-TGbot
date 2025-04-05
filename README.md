
# 🔞 Adult Video Downloader Telegram Bot

This is a Telegram bot built using Python and `pyTelegramBotAPI` (Telebot) that allows **18+ users** to download videos from **Pornhub**. It includes **age verification**, **channel subscription checks**, and allows users to set **gender** and **sexual orientation preferences**. 

> ⚠️ **This bot is for educational purposes only.** Ensure you comply with all applicable laws and Telegram's terms of service before deploying such a bot publicly.

> ⭐ **If you find this project useful, please consider giving it a star to support the development!** ⭐

---

## 🚀 Features

- 🔞 Age verification system
- 📺 Download videos from Pornhub in various resolutions
- ⚖️ **File size limit of 2GB** (Telegram does not allow videos larger than 2GB)
- 🎯 **Personalized video recommendations** based on gender & sexual orientation
- ✅ User data stored in SQLite (status, gender, orientation)
- 📢 Channel membership enforcement
- 🌈 Collects gender and sexual orientation for future personalized recommendations
- 🧠 Uses `yt-dlp` to fetch video info and handle downloads
- 🗑️ Deletes video after 30 seconds to save storage and ensure privacy

> 🔍 **Video recommendations are powered by [`pornhub-api`](https://github.com/Derfirm/pornhub-api).** Special thanks to [Derfirm](https://github.com/Derfirm) for this awesome library! If you find it useful, consider giving it a star. ⭐

---

### 🔔 Admin Tools

Admins (defined in the `ADMINS` list like below) have access to special commands:

```python
ADMINS = [123456789, 987654321]
```

#### `/ad` – Broadcast Message  
This command allows admins to send an **advertisement or announcement** to **all verified users**.  
It's useful for updates, promotions, or important news related to the bot.

> ⚠️ Make sure to keep broadcasts respectful and avoid spamming users.

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
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB limit
```

> 🔧 Make sure the `FFMPEG_PATH` points to the actual path of the FFmpeg binary. On most systems, it's simply `"ffmpeg"` if added to your system's PATH.

### 4. Run the Bot

```bash
python __main__.py
```

---

## 🛠 Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and verify age |
| `/age` | Reconfirm age if needed |
| `/user` | Update gender or orientation |
| `/ad` | **(Admin only)** Broadcast message to all verified users |

---

## 💬 Buttons

After successful verification, the bot provides the following options:

- `🔍 Find Video` – Get **personalized** Pornhub video recommendations based on your gender and orientation
- `💾 Download Video` – Input a Pornhub URL and download in preferred resolution

---

## 🔐 Data Privacy

- User information is stored in a local `SQLite` database (`users.db`)
- Downloaded videos are removed 30 seconds after sending
- No data is shared or sent to third parties

---

## 📜 License  

This project is licensed under the **GPL-3.0** license. You are free to use, modify, and distribute it under the same license terms.  

For more details, please read the [`LICENSE`](LICENSE) file.  

---

## ❗ Disclaimer

This bot is designed for **educational and personal use only**. Distribution or use of adult content may be restricted in some countries. Please use responsibly and ensure compliance with local laws and Telegram guidelines.

> ⭐ **If you appreciate this project, please consider giving it a star to support future improvements!** ⭐

