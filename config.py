"""
Configuration file for the Telegram bot.
Contains all API keys, URLs, and bot settings.
"""
import logging
import os
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()
# ========== BOT CONFIGURATION ==========
API_ID = int(os.getenv('API_ID') or 0) # Added default value for int conversion
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
# ========== A4F API CONFIGURATION ==========
CHAT_API_URL = os.getenv('CHAT_API_URL')
IMAGE_API_URL = os.getenv('IMAGE_API_URL')
API_KEY = os.getenv('API_KEY')
# ========== GOFILE API CONFIGURATION ==========
GOFILE_UPLOAD_URL = "https://store2.gofile.io/uploadFile"
# ========== MUX CONFIGURATION ==========
MUX_TOKEN_ID = os.getenv('MUX_TOKEN_ID')
MUX_TOKEN_SECRET = os.getenv('MUX_TOKEN_SECRET')
MUX_ASSETS_URL = os.getenv('MUX_ASSETS_URL')
MUX_UPLOADS_URL = os.getenv('MUX_UPLOADS_URL')
# ========== CLOUDINARY CONFIGURATION ==========
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')
CLOUDINARY_FOLDER = os.getenv('CLOUDINARY_FOLDER')
# ========== AI MODEL CONFIGURATIONS ==========
CHAT_MODELS = {
    "deep3": "provider-3/deepseek-v3",
    "gpt4": "provider-3/gpt-4",
    "grok4": "provider-3/grok-4-0709"
}
IMAGE_MODELS = {
    "image": "provider-6/sana-1.5",
    "image1": "provider-3/FLUX.1-schnell",
    "image2": "provider-1/FLUX.1-kontext-pro"
}
# ========== CHAT API SETTINGS ==========
CHAT_SYSTEM_MESSAGE = "You are a helpful assistant. also use some emojis to make responses more lively."
CHAT_TEMPERATURE = 0.7
CHAT_MAX_TOKENS = 150
# ========== IMAGE API SETTINGS ==========
IMAGE_SIZE = "1024x1024"
IMAGE_COUNT = 1
# ========== LOGGING CONFIGURATION ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
# ========== HELP TEXT ==========
HELP_TEXT = """
🤖 **All-in-One Bot Commands**
**Chat & Images:**
• `/deep3`, `/gpt4`, `/grok4` + message - Chat with AI
• `/image`, `/image1`, `/image2` + prompt - Generate images
• Reply `.bg` to image - Remove background
**File Management:**
• Reply `.up` - Upload to GoFile
• Reply `.upmix` - Upload video to MixDrop
• Reply `.imgup` - Upload image to Cloudinary
• `.link <url>` - Download from URL (max 1900MB)
• Reply `.compress` - Compress video while maintaining quality
**Media Libraries:**
• `.mux` - View/manage Mux videos
• `.imgs` - Browse Cloudinary images
• Reply `.muxup` - Upload to Mux
**Basic:**
• `/start` - Check bot status
• `/help` - Show this menu
💡 All commands work with either `.` or `/` prefix
"""
