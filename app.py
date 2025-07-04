import telebot
import httpx
import time
import threading
import os
from flask import Flask
from yt_dlp import YoutubeDL


API_TOKEN = "7961702167:AAHS7llSVZ8i4XH-_h9ULm3tFQS9MkHjU9I"
ADMIN_ID = 6355601354

bot = telebot.TeleBot(API_TOKEN, parse_mode="Markdown")
flask_app = Flask(__name__)

API_ENDPOINT = "https://tele-social.vercel.app/down?url="
user_locks = {}

# =================== Flask ===================
@flask_app.route("/")
def home():
    return "✅ Instagram & YouTube Downloader Bot is running!"

@flask_app.route("/status")
def status():
    return "📡 Bot Status: Running"

@flask_app.route("/health", methods=['GET'])
def health_check():
    return "OK", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

# =================== Progress ===================
def progress_bar(percent):
    done = int(percent / 5)
    return "▓" * done + "░" * (20 - done)

def upload_progress(current, total, message, start_time):
    percent = current * 100 / total
    bar = progress_bar(percent)
    speed = current / (1024 * 1024 * (time.time() - start_time) + 1e-6)

    status = f"""
📥 Upload Progress 📥

{bar}

🚧 PC: {percent:.2f}%
⚡️ Speed: {speed:.2f} MB/s
📶 Status: {current / (1024 * 1024):.1f} MB of {total / (1024 * 1024):.1f} MB
"""
    try:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=status
        )
    except:
        pass

# =================== Handlers ===================
@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.send_message(
        message.chat.id,
        "👋 Hi! I'm your Instagram & YouTube Downloader Bot.\n\n"
        "Send me a video link using:\n"
        "📸 `/ig <Instagram URL>`\n"
        "▶️ `/yt <YouTube Shorts/Video URL>`\n\n"
        "I'll fetch and send you the video directly here!"
    )

@bot.message_handler(commands=['ig'])
def download_instagram_video(message):
    user_id = message.from_user.id

    if user_id in user_locks:
        bot.reply_to(message, "⏳ Please wait until your current download is complete.")
        return

    parts = message.text.split()
    url = None

    # Case 1: URL in command (/ig <url>)
    if len(parts) >= 2:
        url = parts[1]

    # Case 2: Replied message contains URL
    elif message.reply_to_message and message.reply_to_message.text:
        url = message.reply_to_message.text.strip()

    if not url or "http" not in url:
        bot.reply_to(message, "❗ Usage: /ig <Instagram URL>")
        return

    status_msg = bot.reply_to(message, "🔍 Searching the video...")

    user_locks[user_id] = True
    video_url = None
    filename = f"ig_video_{user_id}.mp4"

    try:
        with httpx.Client(timeout=20) as client_http:
            resp = client_http.get(API_ENDPOINT + url)
            data = resp.json()

        if not data.get("status") or not data["data"].get("direct_video"):
            bot.edit_message_text("❌ Could not retrieve Instagram video.", message.chat.id, status_msg.message_id)
            return

        video_url = data["data"]["direct_video"][0]
        bot.edit_message_text("✅ Found! Downloading...", message.chat.id, status_msg.message_id)

        start_time = time.time()
        last_update = time.time()

        with httpx.stream("GET", video_url, timeout=60) as r:
            with open(filename, "wb") as f:
                total = int(r.headers.get("content-length", 0))
                current = 0
                for chunk in r.iter_bytes():
                    f.write(chunk)
                    current += len(chunk)
                    now = time.time()
                    if now - last_update > 2:
                        upload_progress(current, total, status_msg, start_time)
                        last_update = now

        bot.send_video(
            chat_id=message.chat.id,
            video=open(filename, "rb"),
            caption="🎬 Here's your Instagram reel!",
            reply_to_message_id=message.id
        )

        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(
            f"⚠️ An error occurred.\n{'Here is the link:\n' + video_url if video_url else ''}\n\nError: `{e}`",
            message.chat.id,
            status_msg.message_id
        )

    finally:
        user_locks.pop(user_id, None)
        if os.path.exists(filename):
            os.remove(filename)

@bot.message_handler(commands=['yt'])
def download_youtube_video(message):
    user_id = message.from_user.id

    if user_id in user_locks:
        bot.reply_to(message, "⏳ Please wait until your current download is complete.")
        return

    parts = message.text.split()
    url = None

    # Case 1: URL in command (/yt <url>)
    if len(parts) >= 2:
        url = parts[1]

    # Case 2: Replied message contains URL
    elif message.reply_to_message and message.reply_to_message.text:
        url = message.reply_to_message.text.strip()

    if not url or "http" not in url:
        bot.reply_to(message, "❗ Usage: /yt <YouTube URL>")
        return

    status_msg = bot.reply_to(message, "🔍 Processing the YouTube video...")

    user_locks[user_id] = True
    filename = f"yt_video_{user_id}.mp4"

    download_info = {"status_msg": status_msg, "start_time": time.time(), "filename": filename}

    def yt_progress_hook(d):
        if d['status'] == 'downloading':
            downloaded_bytes = d.get('downloaded_bytes', 0)
            total_bytes = d.get('total_bytes', d.get('total_bytes_estimate', 0))
            if total_bytes > 0:
                upload_progress(downloaded_bytes, total_bytes, download_info["status_msg"], download_info["start_time"])

    try:
        ydl_opts = {
            'outtmpl': filename,
            'format': 'mp4',
            'merge_output_format': 'mp4',
            'quiet': True,
            'progress_hooks': [yt_progress_hook],
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "🎬 Here's your video!")

        bot.send_video(
            chat_id=message.chat.id,
            video=open(filename, "rb"),
            caption=title,
            reply_to_message_id=message.id
        )

        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(
            f"⚠️ An error occurred while downloading.\n\nError: `{str(e)}`",
            message.chat.id,
            status_msg.message_id,
            parse_mode="Markdown"
        )

    finally:
        user_locks.pop(user_id, None)
        if os.path.exists(filename):
            os.remove(filename)

# =================== Main ===================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    print("🌐 Flask server started at http://localhost:8080")
    print("🤖 Bot is running...")
    bot.infinity_polling()
