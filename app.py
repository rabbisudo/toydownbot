from pyrogram import Client, filters
import httpx
import time

API_ID = 26257385
API_HASH = "bbd0c7447894542d6e6a5531af44d0b5"
BOT_TOKEN = "7961702167:AAHS7llSVZ8i4XH-_h9ULm3tFQS9MkHjU9I"
ADMIN_ID = 6355601354  # 🟡 Replace with your own Telegram user ID

app = Client("insta_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

API_ENDPOINT = "https://tele-social.vercel.app/down?url="
user_locks = {}

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
        "`/ig <Instagram URL>`\n\n"
        "I'll fetch and send you the video directly here!"
        , parse_mode="markdown"
    )

@app.on_message(filters.command("ig") & (filters.private | filters.group))
async def download_instagram_video(client, message):
    user_id = message.from_user.id
    video_url = None  # Pre-define to avoid UnboundLocalError later

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

if __name__ == "__main__":
    try:
        print("🤖 Bot is running...")
        app.run()
        app.send_message(ADMIN_ID, "✅ Bot started successfully and is now running.")
    except Exception as e:
        print(f"❌ Bot crashed: {e}\nRestarting...")
