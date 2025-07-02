import telebot
import httpx
import time
import threading
from flask import Flask, request

API_TOKEN = "7961702167:AAHS7llSVZ8i4XH-_h9ULm3tFQS9MkHjU9I"
ADMIN_ID = 6355601354

bot = telebot.TeleBot(API_TOKEN, parse_mode="Markdown")
flask_app = Flask(__name__)

API_ENDPOINT = "https://tele-social.vercel.app/down?url="
user_locks = {}

# =================== Flask ===================
@flask_app.route("/")
def home():
    return "✅ Instagram Reel Downloader Bot is running!"

@flask_app.route("/status")
def status():
    return "📡 Bot Status: Running"

@flask_app.route('/health', methods=['GET'])
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
        "👋 Hi! I'm your Instagram Reel Downloader Bot.\n\n"
        "Send me an Instagram reel URL using the command:\n"
        "`/ig <Instagram URL>`\n\n"
        "I'll fetch and send you the video directly here!"
    )

@bot.message_handler(commands=['ig'])
def download_instagram_video(message):
    user_id = message.from_user.id

    if user_id in user_locks:
        bot.reply_to(message, "⏳ Please wait until your current download is complete.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❗ Usage: /ig <Instagram URL>")
        return

    url = parts[1]
    status_msg = bot.reply_to(message, "🔍 Searching the video...")

    user_locks[user_id] = True
    video_url = None

    try:
        with httpx.Client(timeout=20) as client_http:
            resp = client_http.get(API_ENDPOINT + url)
            data = resp.json()

        if not data.get("status"):
            bot.edit_message_text("❌ Could not retrieve video.", message.chat.id, status_msg.message_id)
            return

        video_url = data["data"].get("direct_video", [None])[0]
        thumbnail_url = data["data"].get("thumbnail", [None])[0]

        if not video_url:
            bot.edit_message_text("❌ No video found.", message.chat.id, status_msg.message_id)
            return

        bot.edit_message_text("✅ Found! Downloading...", message.chat.id, status_msg.message_id)

        start_time = time.time()

        # Download to temp file first
        filename = f"video_{user_id}.mp4"
        with httpx.stream("GET", video_url, timeout=60) as r:
            with open(filename, "wb") as f:
                total = int(r.headers.get("content-length", 0))
                current = 0
                for chunk in r.iter_bytes():
                    f.write(chunk)
                    current += len(chunk)
                    if time.time() - start_time > 2:
                        upload_progress(current, total, status_msg, start_time)

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

# =================== Main ===================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    print("🌐 Flask server started at http://localhost:8080")
    print("🤖 Bot is running...")
    bot.infinity_polling()
