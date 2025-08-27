# bot_notify.py

from pyrogram import Client
from pyrogram.errors import RPCError

# Replace this with your actual admin Telegram user ID
ADMIN_USER_ID = 5222080011


async def notify_admin_on_startup(app: Client):
    """
    Notify the admin that the bot has started.

    Args:
        app (Client): The Pyrogram Client instance
    """
    try:
        await app.send_message(
            chat_id=ADMIN_USER_ID,
            text="✅ Bot has been started successfully!"
        )
        print("📨 Admin notified about bot startup.")
    except RPCError as e:
        print(f"❌ Failed to send startup message to admin: {e}")