from pyrogram import Client, filters
import httpx
import time
import threading
from flask import Flask

API_ID = 26257385
API_HASH = "bbd0c7447894542d6e6a5531af44d0b5"
BOT_TOKEN = "7961702167:AAHS7llSVZ8i4XH-_h9ULm3tFQS9MkHjU9I"
ADMIN_ID = 6355601354

app = Client("insta_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
flask_app = Flask(__name__)

API_ENDPOINT = "https://tele-social.vercel.app/down?url="
user_locks = {}

# ==================== Flask API ====================
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

# ================ Pyrogram Bot Logic ================
def progress_bar(percent):
    done = int(percent / 5)
    return "▓" * done + "░" * (20 - done)

async def upload_progress(current, total, message, start_time):
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
        await message.edit(status)
    except:
        pass

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    await message.reply(
        "👋 Hi! I'm your Instagram Reel Downloader Bot.\n\n"
        "Send me an Instagram reel URL using the command:\n"
        "/ig <Instagram URL>\n\n"
        "I'll fetch and send you the video directly here!"
    )

@app.on_message(filters.command("ig") & (filters.private | filters.group))
async def download_instagram_video(client, message):
    user_id = message.from_user.id
    video_url = None

    if user_id in user_locks:
        await message.reply("⏳ Please wait until your current download is complete.")
        return

    if len(message.command) < 2:
        await message.reply("❗ Usage: /ig <Instagram URL>", reply_to_message_id=message.id)
        return

    url = message.command[1]
    status_msg = await message.reply("🔍 Searching the video...", reply_to_message_id=message.id)

    user_locks[user_id] = True

    try:
        async with httpx.AsyncClient(timeout=20) as client_http:
            resp = await client_http.get(API_ENDPOINT + url)
            try:
                data = resp.json()
            except Exception:
                await status_msg.edit("❌ API did not return valid JSON. Try again later.")
                return

        if not data.get("status"):
            await status_msg.edit("❌ Could not retrieve video.")
            return

        video_url = data["data"].get("direct_video", [None])[0]
        thumbnail_url = data["data"].get("thumbnail", [None])[0]

        if not video_url:
            await status_msg.edit("❌ No video found.")
            return

        await status_msg.edit("✅ Found! Downloading...")

        start_time = time.time()

        await client.send_video(
            chat_id=message.chat.id,
            video=video_url,
            caption="🎬 Here's your Instagram reel!",
            thumb=thumbnail_url,
            reply_to_message_id=message.id,
            progress=upload_progress,
            progress_args=(status_msg, start_time)
        )

        await status_msg.delete()

    except Exception as e:
        await status_msg.edit(
            f"⚠️ An error occurred while processing your request.\n"
            f"{'Here is the link:\n' + video_url if video_url else ''}\n\nError: `{e}`",
            parse_mode="markdown"
        )

    finally:
        user_locks.pop(user_id, None)

# =================== Main ===================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    print("🌐 Flask server started at http://localhost:8080")

    print("🤖 Bot is running...")
    try:
        app.run()
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
