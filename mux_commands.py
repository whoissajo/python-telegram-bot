"""
Mux Commands Module for Telegram Bot
Handles all Mux video platform functionality including asset management, uploads, and thumbnails.
"""

import requests
import tempfile
import os
import asyncio
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import logger
from utility_commands import TelegramProgressTracker

# Import Mux configurations from config.py
from config import (
    MUX_TOKEN_ID, 
    MUX_TOKEN_SECRET,
    MUX_ASSETS_URL,
    MUX_UPLOADS_URL
)

# Authentication for Mux API
MUX_AUTH = (MUX_TOKEN_ID, MUX_TOKEN_SECRET)

# ========== MUX API FUNCTIONS ==========
def get_mux_assets():
    """
    Fetch all assets from Mux.
    
    Returns:
        list: List of asset dictionaries or empty list if failed
    """
    try:
        response = requests.get(MUX_ASSETS_URL, auth=MUX_AUTH)
        if response.status_code == 200:
            return response.json()["data"]
        else:
            logger.error(f"Failed to fetch Mux assets: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching Mux assets: {e}")
        return []


def delete_mux_asset(asset_id):
    """
    Delete a specific asset from Mux.
    
    Args:
        asset_id (str): The asset ID to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        delete_url = f"{MUX_ASSETS_URL}/{asset_id}"
        response = requests.delete(delete_url, auth=MUX_AUTH)
        return response.status_code == 204
    except Exception as e:
        logger.error(f"Error deleting Mux asset {asset_id}: {e}")
        return False


def get_asset_thumbnail(asset_id, time=1):
    """
    Get thumbnail URL for a specific asset.
    
    Args:
        asset_id (str): The asset ID
        time (int): Time in seconds for thumbnail
        
    Returns:
        str: Thumbnail URL or None if failed
    """
    try:
        # Get asset details first
        asset_url = f"{MUX_ASSETS_URL}/{asset_id}"
        response = requests.get(asset_url, auth=MUX_AUTH)
        
        if response.status_code == 200:
            asset_data = response.json()["data"]
            if asset_data.get("playback_ids"):
                playback_id = asset_data["playback_ids"][0]["id"]
                return f"https://image.mux.com/{playback_id}/thumbnail.jpg?time={time}"
        return None
    except Exception as e:
        logger.error(f"Error getting thumbnail for asset {asset_id}: {e}")
        return None


def create_mux_upload(filename=None):
    """
    Create a new upload URL for Mux with optimized settings.

    Args:
        filename (str): Original filename for format detection

    Returns:
        dict: Upload data with URL and ID, or None if failed
    """
    try:
        # Enhanced upload settings for better compatibility
        upload_data = {
            "new_asset_settings": {
                "playback_policy": ["public"],
                "encoding_tier": "baseline",
                "normalize_audio": True,  # Helps with audio compatibility
                "master_access": "temporary",  # Allow access to original file
                "mp4_support": "standard"  # Ensure MP4 compatibility
            },
            "cors_origin": "*",  # Allow CORS for web uploads
            "timeout": 3600  # 1 hour timeout for large files
        }

        # Add format-specific optimizations
        if filename:
            ext = filename.lower().split('.')[-1] if '.' in filename else ''

            # For problematic formats, use more aggressive normalization
            if ext in ['avi', 'wmv', 'flv', 'rm', 'rmvb', '3gp']:
                upload_data["new_asset_settings"]["normalize_audio"] = True
                upload_data["new_asset_settings"]["encoding_tier"] = "smart"  # Better encoding

        response = requests.post(MUX_UPLOADS_URL, json=upload_data, auth=MUX_AUTH)

        if response.status_code == 201:
            return response.json()["data"]
        else:
            logger.error(f"Failed to create Mux upload: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error creating Mux upload: {e}")
        return None


async def upload_file_to_mux(file_path, filename):
    """
    Upload a file to Mux using the upload URL.

    Args:
        file_path (str): Path to the file to upload
        filename (str): Original filename

    Returns:
        dict: Upload result with asset_id or error info
    """
    try:
        # Create upload URL with enhanced settings
        upload_data = create_mux_upload(filename)
        if not upload_data:
            return {"success": False, "error": "Failed to create upload URL"}

        upload_url = upload_data["url"]
        upload_id = upload_data["id"]

        # Get file size for Content-Length header
        file_size = os.path.getsize(file_path)

        # Determine content type based on file extension
        content_type = get_content_type(filename)

        # Log upload details
        logger.info(f"Uploading to Mux: {filename} ({file_size} bytes)")
        logger.info(f"Content-Type: {content_type}")
        logger.info(f"Upload URL: {upload_url}")

        # Upload file with proper headers
        headers = {
            'Content-Type': content_type,
            'Content-Length': str(file_size)
        }

        # Upload in chunks to handle large files better
        with open(file_path, 'rb') as f:
            response = requests.put(
                upload_url,
                data=f,
                headers=headers,
                timeout=300  # 5 minute timeout for large files
            )

        logger.info(f"Mux upload response: {response.status_code}")
        if response.text:
            logger.info(f"Response body: {response.text}")

        if response.status_code in [200, 201, 204]:
            return {
                "success": True,
                "upload_id": upload_id,
                "message": "Upload successful! Processing will begin shortly."
            }
        else:
            return {
                "success": False,
                "error": f"Upload failed: {response.status_code} - {response.text}"
            }

    except Exception as e:
        logger.error(f"Error uploading to Mux: {e}")
        return {"success": False, "error": str(e)}


def get_content_type(filename):
    """
    Get appropriate content type for file upload.

    Args:
        filename (str): The filename

    Returns:
        str: Content type
    """
    if not filename:
        return 'application/octet-stream'

    ext = filename.lower().split('.')[-1] if '.' in filename else ''

    content_types = {
        # Video formats
        'mp4': 'video/mp4',
        'avi': 'video/x-msvideo',
        'mkv': 'video/x-matroska',
        'mov': 'video/quicktime',
        'wmv': 'video/x-ms-wmv',
        'flv': 'video/x-flv',
        'webm': 'video/webm',
        'm4v': 'video/x-m4v',
        '3gp': 'video/3gpp',
        'mpg': 'video/mpeg',
        'mpeg': 'video/mpeg',

        # Audio formats
        'mp3': 'audio/mpeg',
        'wav': 'audio/wav',
        'flac': 'audio/flac',
        'aac': 'audio/aac',
        'ogg': 'audio/ogg',
        'wma': 'audio/x-ms-wma',
        'm4a': 'audio/mp4',
        'opus': 'audio/opus',
    }

    return content_types.get(ext, 'application/octet-stream')


def verify_file_integrity(file_path, filename):
    """
    Verify that the downloaded file is valid and check for common video issues.

    Args:
        file_path (str): Path to the file
        filename (str): Original filename

    Returns:
        dict: Verification result with recommendations
    """
    try:
        file_size = os.path.getsize(file_path)

        if file_size == 0:
            return {"valid": False, "error": "File is empty"}

        if file_size < 100:  # Very small files are likely corrupted
            return {"valid": False, "error": "File too small, likely corrupted"}

        # Check if file has proper extension
        if not filename or '.' not in filename:
            return {"valid": False, "error": "No file extension found"}

        # Try to read first few bytes to ensure file is readable
        with open(file_path, 'rb') as f:
            header = f.read(32)  # Read more bytes for better analysis
            if len(header) == 0:
                return {"valid": False, "error": "Cannot read file header"}

        # Check for common video file signatures
        video_signatures = {
            b'\x00\x00\x00\x18ftypmp4': 'MP4',
            b'\x00\x00\x00\x20ftypmp4': 'MP4',
            b'RIFF': 'AVI',
            b'\x1a\x45\xdf\xa3': 'MKV/WebM',
            b'ftyp': 'MP4/MOV (partial)',
            b'ID3': 'MP3',
            b'RIFF': 'WAV/AVI'
        }

        detected_format = None
        for signature, format_name in video_signatures.items():
            if header.startswith(signature) or signature in header[:16]:
                detected_format = format_name
                break

        # Get file extension
        ext = filename.lower().split('.')[-1] if '.' in filename else ''

        # Check for potential compatibility issues
        warnings = []

        # Check for problematic formats that often cause Mux issues
        problematic_formats = ['avi', 'wmv', 'flv', 'rm', 'rmvb', '3gp']
        if ext in problematic_formats:
            warnings.append(f"{ext.upper()} format may have compatibility issues with Mux")

        # Very large files might have issues
        if file_size > 5 * 1024 * 1024 * 1024:  # 5GB
            warnings.append("Very large file - may cause upload timeout")

        return {
            "valid": True,
            "size": file_size,
            "size_mb": file_size / (1024 * 1024),
            "detected_format": detected_format,
            "warnings": warnings,
            "extension": ext
        }

    except Exception as e:
        return {"valid": False, "error": f"File verification failed: {e}"}


async def create_mux_asset_from_url(input_url):
    """
    Alternative method: Create Mux asset directly from URL (like your working code).

    Args:
        input_url (str): URL to the video file

    Returns:
        dict: Asset creation result
    """
    try:
        asset_data = {
            "input": input_url,
            "playback_policy": ["public"],
            "encoding_tier": "baseline"
        }

        response = requests.post(MUX_ASSETS_URL, json=asset_data, auth=MUX_AUTH)

        if response.status_code == 201:
            asset = response.json()["data"]
            return {
                "success": True,
                "asset_id": asset["id"],
                "status": asset["status"]
            }
        else:
            logger.error(f"Failed to create Mux asset: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": f"Asset creation failed: {response.status_code}"
            }

    except Exception as e:
        logger.error(f"Error creating Mux asset: {e}")
        return {"success": False, "error": str(e)}


# ========== TELEGRAM UI FUNCTIONS ==========
def create_assets_keyboard(assets, page=0, per_page=5):
    """
    Create inline keyboard for assets list.
    
    Args:
        assets (list): List of assets
        page (int): Current page number
        per_page (int): Assets per page
        
    Returns:
        InlineKeyboardMarkup: Keyboard with asset buttons
    """
    keyboard = []
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_assets = assets[start_idx:end_idx]
    
    for asset in page_assets:
        # Create button text with asset info
        status_emoji = "✅" if asset["status"] == "ready" else "⏳"
        duration = asset.get("duration", 0)
        duration_str = f"{int(duration//60)}:{int(duration%60):02d}" if duration else "N/A"
        
        button_text = f"{status_emoji} {asset['id'][:8]}... ({duration_str})"
        keyboard.append([InlineKeyboardButton(
            button_text, 
            callback_data=f"mux_asset_{asset['id']}"
        )])
    
    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"mux_page_{page-1}"))
    if end_idx < len(assets):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"mux_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Refresh button
    keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="mux_refresh")])
    
    return InlineKeyboardMarkup(keyboard)


def create_asset_detail_keyboard(asset_id):
    """
    Create keyboard for individual asset details.
    
    Args:
        asset_id (str): The asset ID
        
    Returns:
        InlineKeyboardMarkup: Keyboard with asset actions
    """
    keyboard = [
        [
            InlineKeyboardButton("🗑️ Delete", callback_data=f"mux_delete_{asset_id}"),
            InlineKeyboardButton("🎬 Playback URL", callback_data=f"mux_playback_{asset_id}")
        ],
        [InlineKeyboardButton("⬅️ Back to List", callback_data="mux_back")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


# ========== COMMAND HANDLERS ==========
async def handle_mux_assets(client, message: Message):
    """
    Handle .mux command to show all assets.
    
    Args:
        client: Pyrogram client
        message (Message): The message object
    """
    status_msg = await message.reply("🔍 Fetching Mux assets...")
    
    assets = get_mux_assets()
    
    if not assets:
        await status_msg.edit("❌ No assets found or failed to fetch assets from Mux.")
        return
    
    # Create assets list message
    total_assets = len(assets)
    ready_assets = len([a for a in assets if a["status"] == "ready"])
    
    text = f"📹 **Mux Assets** ({total_assets} total, {ready_assets} ready)\n\n"
    text += "Select an asset to view details:"
    
    keyboard = create_assets_keyboard(assets)
    
    await status_msg.edit(text, reply_markup=keyboard)


def is_valid_mux_file(filename):
    """
    Check if file is valid for Mux upload.

    Args:
        filename (str): The filename to check

    Returns:
        bool: True if valid for Mux, False otherwise
    """
    if not filename:
        return False

    ext = filename.lower().split('.')[-1] if '.' in filename else ''

    # Mux supported formats
    mux_supported = {
        # Video formats
        'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', 'm4v',
        '3gp', 'mpg', 'mpeg', 'ts', 'mts', 'm2ts', 'vob', 'asf',
        'divx', 'f4v', 'mxf', 'qt', 'xvid',

        # Audio formats
        'mp3', 'wav', 'flac', 'aac', 'ogg', 'wma', 'm4a', 'opus',
        'aiff', 'au', 'amr', 'ac3', 'ape', 'dts'
    }

    return ext in mux_supported


async def handle_mux_upload(client, message: Message):
    """
    Handle .muxup command to upload media to Mux.

    Args:
        client: Pyrogram client
        message (Message): The message object
    """
    reply = message.reply_to_message

    # Check if replying to media
    if not reply or not (reply.video or reply.document or reply.audio):
        await message.reply("⚠️ Please reply to a video, document, or audio file with `.muxup` or `/muxup`.")
        return
    
    media = reply.video or reply.document or reply.audio

    # Get original filename and create temp file with proper extension
    original_filename = getattr(media, 'file_name', None)

    # Determine file extension
    if original_filename and '.' in original_filename:
        file_extension = '.' + original_filename.split('.')[-1]
    elif reply.video:
        file_extension = '.mp4'  # Default for videos
    elif reply.audio:
        file_extension = '.mp3'  # Default for audio
    else:
        file_extension = '.mp4'  # Default fallback

    # Create temporary file with proper extension
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
    temp.close()

    try:
        # Download media with progress
        status_msg = await message.reply("📥 Downloading media for Mux upload...")

        # Get proper filename
        filename = original_filename or f'video_{media.file_id[:8]}{file_extension}'

        # Create download progress tracker
        download_tracker = TelegramProgressTracker(
            status_msg,
            filename,
            getattr(media, 'file_size', 0) / (1024*1024),
            "Downloading"
        )

        await client.download_media(
            media,
            file_name=temp.name,
            progress=download_tracker
        )
        download_tracker.close()

        # Get file info
        file_size_mb = os.path.getsize(temp.name) / (1024 * 1024)

        # Log file details for debugging
        logger.info(f"Downloaded file: {filename}, size: {file_size_mb:.1f}MB, temp path: {temp.name}")

        # Verify file integrity and check for compatibility issues
        verification = verify_file_integrity(temp.name, filename)
        if not verification["valid"]:
            await status_msg.edit(
                f"❌ **File verification failed**\n"
                f"📁 File: {filename}\n"
                f"⚠️ Error: {verification['error']}\n"
                f"🔄 Try uploading the file again."
            )
            return

        # Show warnings if any compatibility issues detected
        if verification.get("warnings"):
            warning_text = "\n".join([f"⚠️ {w}" for w in verification["warnings"]])
            await status_msg.edit(
                f"⚠️ **Compatibility Warning**\n"
                f"📁 File: {filename}\n"
                f"🔍 Detected: {verification.get('detected_format', 'Unknown')}\n"
                f"{warning_text}\n"
                f"🔄 Proceeding with enhanced compatibility settings..."
            )
            await asyncio.sleep(2)  # Show warning for 2 seconds

        # Validate file type for Mux
        if not is_valid_mux_file(filename):
            await status_msg.edit(
                f"❌ **Unsupported file format for Mux**\n"
                f"📁 File: {filename}\n"
                f"⚠️ Mux only supports video and audio files.\n"
                f"✅ Supported: MP4, AVI, MKV, MOV, MP3, WAV, etc."
            )
            return

        # Upload to Mux
        await status_msg.edit(
            f"⬆️ **Uploading to Mux**\n"
            f"📁 File: {filename}\n"
            f"📊 Size: {file_size_mb:.1f}MB\n"
            f"🔄 Creating upload URL..."
        )

        result = await upload_file_to_mux(temp.name, filename)

        if result["success"]:
            await status_msg.edit(
                f"✅ **Upload Successful!**\n"
                f"📁 File: {filename}\n"
                f"📊 Size: {file_size_mb:.1f}MB\n"
                f"🔍 Format: {verification.get('detected_format', 'Auto-detected')}\n"
                f"🆔 Upload ID: `{result['upload_id']}`\n"
                f"⏳ Processing will begin shortly...\n"
                f"📺 Check your Mux dashboard for processing status.\n"
                f"💡 If processing fails, the file format may need conversion."
            )
        else:
            # Check if it's a format-related error
            error_msg = result.get('error', '').lower()
            if 'non_standard_input' in error_msg or 'invalid_input' in error_msg:
                await status_msg.edit(
                    f"❌ **Format Compatibility Issue**\n"
                    f"📁 File: {filename}\n"
                    f"📊 Size: {file_size_mb:.1f}MB\n"
                    f"🔍 Format: {verification.get('detected_format', 'Unknown')}\n"
                    f"⚠️ Mux detected non-standard video encoding\n"
                    f"💡 **Solutions:**\n"
                    f"• Convert to standard MP4 (H.264 + AAC)\n"
                    f"• Use video editing software to re-encode\n"
                    f"• Try uploading a different video file\n"
                    f"🔧 Recommended: Use FFmpeg or similar tool"
                )
            else:
                await status_msg.edit(
                    f"❌ **Upload Failed**\n"
                    f"📁 File: {filename}\n"
                    f"📊 Size: {file_size_mb:.1f}MB\n"
                    f"🔍 Format: {verification.get('detected_format', 'Unknown')}\n"
                    f"⚠️ Error: {result['error']}\n"
                    f"🔄 Please try again or check file format."
                )
            
    except Exception as e:
        logger.error(f"Mux upload process failed: {e}")
        await status_msg.edit(f"❌ Upload failed: {e}")
    
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(temp.name):
                os.unlink(temp.name)
        except Exception as e:
            logger.warning(f"Failed to delete temp file: {e}")


# ========== REGISTER MUX COMMANDS ==========
def register_mux_commands(app):
    """
    Register all Mux-related commands with the bot.
    
    Args:
        app: The Pyrogram Client instance
    """
    
    @app.on_message(filters.regex(r'^[./]mux$'))
    async def mux_assets(client, message):
        """Handle .mux or /mux command"""
        await handle_mux_assets(client, message)

    @app.on_message(filters.regex(r'^[./]muxup') & filters.reply)
    async def mux_upload(client, message):
        """Handle .muxup or /muxup command"""
        await handle_mux_upload(client, message)
    
    # ========== CALLBACK HANDLERS ==========
    @app.on_callback_query(filters.regex(r'^mux_'))
    async def handle_mux_callbacks(client, callback_query: CallbackQuery):
        """Handle all Mux-related callback queries"""
        data = callback_query.data

        try:
            if data.startswith("mux_asset_"):
                # Show individual asset details
                asset_id = data.replace("mux_asset_", "")
                await show_asset_details(client, callback_query, asset_id)

            elif data.startswith("mux_delete_"):
                # Delete asset
                asset_id = data.replace("mux_delete_", "")
                await delete_asset_callback(client, callback_query, asset_id)

            elif data.startswith("mux_playback_"):
                # Show playback URL
                asset_id = data.replace("mux_playback_", "")
                await show_playback_url(client, callback_query, asset_id)

            elif data.startswith("mux_page_"):
                # Navigate pages
                page = int(data.replace("mux_page_", ""))
                await navigate_assets_page(client, callback_query, page)

            elif data == "mux_refresh":
                # Refresh assets list
                await refresh_assets_list(client, callback_query)

            elif data == "mux_back":
                # Go back to assets list
                await go_back_to_assets(client, callback_query)

        except Exception as e:
            logger.error(f"Error handling Mux callback {data}: {e}")
            await callback_query.answer("❌ An error occurred", show_alert=True)

    logger.info("Mux commands registered successfully")


# ========== CALLBACK FUNCTIONS ==========
async def show_asset_details(client, callback_query: CallbackQuery, asset_id: str):
    """Show details for a specific asset."""
    try:
        # Get asset details
        asset_url = f"{MUX_ASSETS_URL}/{asset_id}"
        response = requests.get(asset_url, auth=MUX_AUTH)

        if response.status_code != 200:
            await callback_query.answer("❌ Failed to fetch asset details", show_alert=True)
            return

        asset = response.json()["data"]

        # Format asset information
        status_emoji = "✅" if asset["status"] == "ready" else "⏳"
        duration = asset.get("duration", 0)
        duration_str = f"{int(duration//60)}:{int(duration%60):02d}" if duration else "N/A"

        text = f"📹 **Asset Details**\n\n"
        text += f"🆔 **ID:** `{asset['id']}`\n"
        text += f"{status_emoji} **Status:** {asset['status'].title()}\n"
        text += f"⏱️ **Duration:** {duration_str}\n"
        text += f"📅 **Created:** {asset['created_at'][:10]}\n"

        if asset.get("playback_ids"):
            playback_id = asset["playback_ids"][0]["id"]
            text += f"🎬 **Playback ID:** `{playback_id}`\n"

        # Get and send thumbnail
        thumbnail_url = get_asset_thumbnail(asset_id)
        keyboard = create_asset_detail_keyboard(asset_id)

        if thumbnail_url:
            try:
                await callback_query.message.delete()
                await client.send_photo(
                    chat_id=callback_query.message.chat.id,
                    photo=thumbnail_url,
                    caption=text,
                    reply_markup=keyboard
                )
                await callback_query.answer()
                return
            except Exception:
                # Fallback to text if thumbnail fails
                pass

        # Fallback to text message
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()

    except Exception as e:
        logger.error(f"Error showing asset details: {e}")
        await callback_query.answer("❌ Error loading asset details", show_alert=True)


async def delete_asset_callback(client, callback_query: CallbackQuery, asset_id: str):
    """Handle asset deletion."""
    try:
        # Confirm deletion
        success = delete_mux_asset(asset_id)

        if success:
            await callback_query.answer("✅ Asset deleted successfully!", show_alert=True)
            # Go back to assets list
            await go_back_to_assets(client, callback_query)
        else:
            await callback_query.answer("❌ Failed to delete asset", show_alert=True)

    except Exception as e:
        logger.error(f"Error deleting asset: {e}")
        await callback_query.answer("❌ Error deleting asset", show_alert=True)


async def show_playback_url(client, callback_query: CallbackQuery, asset_id: str):
    """Show playback URL for an asset."""
    try:
        # Get asset details
        asset_url = f"{MUX_ASSETS_URL}/{asset_id}"
        response = requests.get(asset_url, auth=MUX_AUTH)

        if response.status_code == 200:
            asset = response.json()["data"]
            if asset.get("playback_ids"):
                playback_id = asset["playback_ids"][0]["id"]
                playback_url = f"https://stream.mux.com/{playback_id}.m3u8"

                await callback_query.answer()
                await client.send_message(
                    chat_id=callback_query.message.chat.id,
                    text=f"🎬 **Playback URL for Asset**\n\n"
                         f"🆔 Asset ID: `{asset_id}`\n"
                         f"🔗 Playback URL: `{playback_url}`\n"
                         f"📱 Stream URL: `https://stream.mux.com/{playback_id}`",
                    disable_web_page_preview=True
                )
            else:
                await callback_query.answer("❌ No playback ID available", show_alert=True)
        else:
            await callback_query.answer("❌ Failed to fetch playback URL", show_alert=True)

    except Exception as e:
        logger.error(f"Error getting playback URL: {e}")
        await callback_query.answer("❌ Error getting playback URL", show_alert=True)


async def navigate_assets_page(client, callback_query: CallbackQuery, page: int):
    """Navigate to a different page of assets."""
    try:
        assets = get_mux_assets()

        if not assets:
            await callback_query.answer("❌ No assets found", show_alert=True)
            return

        total_assets = len(assets)
        ready_assets = len([a for a in assets if a["status"] == "ready"])

        text = f"📹 **Mux Assets** ({total_assets} total, {ready_assets} ready)\n\n"
        text += "Select an asset to view details:"

        keyboard = create_assets_keyboard(assets, page)

        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()

    except Exception as e:
        logger.error(f"Error navigating to page {page}: {e}")
        await callback_query.answer("❌ Error loading page", show_alert=True)


async def refresh_assets_list(client, callback_query: CallbackQuery):
    """Refresh the assets list."""
    try:
        assets = get_mux_assets()

        if not assets:
            await callback_query.answer("❌ No assets found", show_alert=True)
            return

        total_assets = len(assets)
        ready_assets = len([a for a in assets if a["status"] == "ready"])

        text = f"📹 **Mux Assets** ({total_assets} total, {ready_assets} ready)\n\n"
        text += "Select an asset to view details:"

        keyboard = create_assets_keyboard(assets)

        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer("🔄 Assets refreshed!")

    except Exception as e:
        logger.error(f"Error refreshing assets: {e}")
        await callback_query.answer("❌ Error refreshing assets", show_alert=True)


async def go_back_to_assets(client, callback_query: CallbackQuery):
    """Go back to the main assets list."""
    try:
        assets = get_mux_assets()

        if not assets:
            await callback_query.message.edit_text("❌ No assets found or failed to fetch assets from Mux.")
            await callback_query.answer()
            return

        total_assets = len(assets)
        ready_assets = len([a for a in assets if a["status"] == "ready"])

        text = f"📹 **Mux Assets** ({total_assets} total, {ready_assets} ready)\n\n"
        text += "Select an asset to view details:"

        keyboard = create_assets_keyboard(assets)

        # Delete current message and send new one (to handle photo -> text transition)
        try:
            await callback_query.message.delete()
            await client.send_message(
                chat_id=callback_query.message.chat.id,
                text=text,
                reply_markup=keyboard
            )
        except:
            # Fallback to edit if delete fails
            await callback_query.message.edit_text(text, reply_markup=keyboard)

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Error going back to assets: {e}")
        await callback_query.answer("❌ Error loading assets", show_alert=True)