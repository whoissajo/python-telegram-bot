"""
AI Commands Module for Telegram Bot
Handles all AI-related functionality including chat and image generation.
"""

import requests
from pyrogram import filters
from pyrogram.types import Message
from requests.structures import CaseInsensitiveDict
from config import (
    CHAT_API_URL, IMAGE_API_URL, API_KEY, CHAT_MODELS, IMAGE_MODELS,
    CHAT_SYSTEM_MESSAGE, CHAT_TEMPERATURE, CHAT_MAX_TOKENS,
    IMAGE_SIZE, IMAGE_COUNT, logger
)


# ========== A4F Chat API ==========
async def call_chat_api(model, user_message):
    """
    Call the A4F Chat API with the specified model and user message.
    
    Args:
        model (str): The AI model to use
        user_message (str): The user's message
        
    Returns:
        str: The AI response or error message
    """
    headers = CaseInsensitiveDict({
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    })

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": CHAT_SYSTEM_MESSAGE},
            {"role": "user", "content": user_message}
        ],
        "temperature": CHAT_TEMPERATURE,
        "max_tokens": CHAT_MAX_TOKENS
    }

    try:
        r = requests.post(CHAT_API_URL, headers=headers, json=data)
        logger.info(f"Chat API status: {r.status_code}")
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        return f"❌ API error: {r.status_code}"
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return f"⚠️ Error: {e}"


# ========== A4F Image API ==========
async def call_image_api(model, prompt):
    """
    Call the A4F Image API with the specified model and prompt.
    
    Args:
        model (str): The image generation model to use
        prompt (str): The image generation prompt
        
    Returns:
        str: The image URL or error message
    """
    headers = CaseInsensitiveDict({
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    })

    data = {
        "model": model,
        "prompt": prompt,
        "n": IMAGE_COUNT,
        "size": IMAGE_SIZE
    }

    try:
        r = requests.post(IMAGE_API_URL, headers=headers, json=data)
        logger.info(f"Image API status: {r.status_code}")
        if r.status_code == 200:
            return r.json()["data"][0]["url"]
        return f"❌ API error: {r.status_code}"
    except Exception as e:
        logger.error(f"Image API error: {e}")
        return f"⚠️ Error: {e}"


# ========== Chat Command Handler ==========
async def handle_chat_command(message: Message, model: str):
    """
    Handle chat commands by extracting user input and calling the chat API.
    
    Args:
        message (Message): The Telegram message object
        model (str): The AI model to use
    """
    user_input = message.text.split(maxsplit=1)
    if len(user_input) < 2:
        await message.reply("⚠️ Please provide a message.")
        return
    
    query = user_input[1]
    status_msg = await message.reply("💬 Thinking...")
    response = await call_chat_api(model, query)
    await status_msg.edit(response)


# ========== Image Command Handler ==========
async def handle_image_command(message: Message, model: str):
    """
    Handle image generation commands by extracting prompt and calling the image API.
    
    Args:
        message (Message): The Telegram message object
        model (str): The image generation model to use
    """
    user_input = message.text.split(maxsplit=1)
    if len(user_input) < 2:
        await message.reply("⚠️ Please provide a prompt.")
        return
    
    prompt = user_input[1]
    status_msg = await message.reply("🖌 Generating image...")
    url = await call_image_api(model, prompt)
    
    if url.startswith("http"):
        await status_msg.delete()
        await message.reply_photo(url)
    else:
        await status_msg.edit(url)


# ========== Register AI Commands ==========
def register_ai_commands(app):
    """
    Register all AI-related commands with the bot.
    
    Args:
        app: The Pyrogram Client instance
    """
    
    # Chat Commands
    @app.on_message(filters.command("deep3"))
    async def deep3(client, message):
        await handle_chat_command(message, CHAT_MODELS["deep3"])

    @app.on_message(filters.command("gpt4"))
    async def gpt4(client, message):
        await handle_chat_command(message, CHAT_MODELS["gpt4"])

    @app.on_message(filters.command("grok4"))
    async def grok4(client, message):
        await handle_chat_command(message, CHAT_MODELS["grok4"])

    # Image Commands
    @app.on_message(filters.command("image"))
    async def image(client, message):
        await handle_image_command(message, IMAGE_MODELS["image"])

    @app.on_message(filters.command("image1"))
    async def image1(client, message):
        await handle_image_command(message, IMAGE_MODELS["image1"])

    @app.on_message(filters.command("image2"))
    async def image2(client, message):
        await handle_image_command(message, IMAGE_MODELS["image2"])
    
    logger.info("AI commands registered successfully")