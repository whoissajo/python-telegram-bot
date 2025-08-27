import os
import sys
import time
import tempfile
import logging
import asyncio
import datetime
import requests
import urllib.parse
import mimetypes # Added for VOE upload
from tqdm import tqdm
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from PIL import Image
# Try to import local config (user-provided). Fall back to environment variables.
try:
    import config as user_config
except Exception:
    user_config = None
# --- Config and logger setup ---
API_ID = getattr(user_config, 'API_ID', os.environ.get('API_ID'))
VOE_API_SERVER = getattr(user_config, 'VOE_API_SERVER', os.environ.get('VOE_API_SERVER'))
VOE_API_KEY = getattr(user_config, 'VOE_API_KEY', os.environ.get('VOE_API_KEY'))
async def upload_process(msg, filename, file_size_mb, tmp_path, user_id, hosts):
    try:
        # Format the results
        upload_details = []
        for idx, upload in enumerate(uploads, 1):
            details = [
                f"Mirror #{idx}:",
                f"Name: {upload['name']}",
                f"Size: {upload['size']}",
            ]
            if upload.get('type'):
                details.append(f"Type: {upload['type']}")
            details.append(f"Download: {upload['url']}")
            upload_details.append("\n".join(details))
        if not upload_details:
            raise Exception("Upload completed but failed to get valid URLs")
        result_text = (
            "Uploaded to MultiUp successfully!\n\n"
            f"Original file: {filename}\n"
            f"Size: {file_size_mb:.1f} MB\n\n"
            f"{'─' * 30}\n"
            f"{'\n\n'.join(upload_details)}"
        )
        await msg.edit_text(
            result_text,
            disable_web_page_preview=True
        )
        project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
        if not project_hash:
            raise Exception("Failed to create upload project")
        upload_url = server.rstrip('/') + "/upload/index.php"
        await msg.edit_text(
            f"Uploading to MultiUp servers...\n"
            f"📁 Filename: {filename}\n"
            f"📊 Size: {file_size_mb:.1f} MB\n"
            f"🔄 This may take a while...",
            disable_web_page_preview=True
        )
        uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
        if not uploads:
            raise Exception("Upload completed but no URLs returned")
        # Format upload results with better error handling
        upload_details = []
        for upload in uploads:
            if not upload.get('url'):
                continue
            detail = []
            if upload.get('name'):
                detail.append(f"📁 Name: {upload['name']}")
            if upload.get('size'):
                detail.append(f"📊 Size: {upload['size']}")
            detail.append(f"🔗 URL: {upload['url']}")
            upload_details.append("\n".join(detail))
        await msg.edit_text(
            "Upload completed successfully!\n\n"
            f"{'\n\n'.join(upload_details)}",
            disable_web_page_preview=True
        )
    except Exception as e:
        await msg.edit_text(f"An error occurred: {str(e)}")
API_HASH = getattr(user_config, 'API_HASH', os.environ.get('API_HASH'))
BOT_TOKEN = getattr(user_config, 'BOT_TOKEN', os.environ.get('BOT_TOKEN'))
GOFILE_UPLOAD_URL = getattr(user_config, 'GOFILE_UPLOAD_URL', os.environ.get('GOFILE_UPLOAD_URL', 'https://store2.gofile.io/uploadFile'))
HELP_TEXT = getattr(user_config, 'HELP_TEXT', "Use commands: .up (reply to media) , .bg (reply to image)")
# MixDrop credentials (from your snippet) - replace if needed
MIXDROP_EMAIL = getattr(user_config, 'MIXDROP_EMAIL', os.environ.get('MIXDROP_EMAIL', 'hariwoc436@elobits.com'))
MIXDROP_KEY = getattr(user_config, 'MIXDROP_KEY', os.environ.get('MIXDROP_KEY', 'xWPhNUDZKh6kl5Ax'))
MIXDROP_API_URL = getattr(user_config, 'MIXDROP_API_URL', os.environ.get('MIXDROP_API_URL', 'https://ul.mixdrop.ag/api'))
# Basic logger (user can supply logger in config.py)
logger = getattr(user_config, 'logger', None)
if logger is None:
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger('utility_bot')
# --- Optional rembg import for .bg command. If unavailable, we will gracefully disable the feature. ---
try:
    from rembg import remove
    REMBG_AVAILABLE = True
except Exception as e:
    REMBG_AVAILABLE = False
    logger.warning(f"rembg not available: {e} - .bg command will be disabled")
# ========== Utility helpers (URL validation, filename extraction) ==========
def is_valid_url(url: str) -> bool:
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False
def get_filename_from_url(url: str, response_headers: dict | None = None) -> str:
    if response_headers and 'content-disposition' in response_headers:
        content_disposition = response_headers['content-disposition']
        if 'filename=' in content_disposition:
            filename = content_disposition.split('filename=')[-1].strip('"')
            return filename
    parsed = urllib.parse.urlparse(url)
    name = os.path.basename(parsed.path)
    if not name or '.' not in name:
        return 'downloaded_file'
    return name
# ========== File type detection ==========
def get_file_type(filename: str) -> str:
    if not filename or '.' not in filename:
        return 'document'
    ext = filename.lower().rsplit('.', 1)[-1]
    video_extensions = {
        'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', 'm4v',
        '3gp', 'mpg', 'mpeg', 'ts', 'vob', 'ogv', 'rm', 'rmvb',
        'asf', 'divx', 'f4v', 'mts', 'm2ts', 'mxf', 'qt', 'xvid'
    }
    image_extensions = {
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'tif',
        'svg', 'ico', 'heic', 'heif'
    }
    audio_extensions = {
        'mp3', 'wav', 'flac', 'aac', 'ogg', 'wma', 'm4a', 'opus',
        'aiff'
    }
    if ext in video_extensions:
        return 'video'
    if ext in image_extensions:
        return 'photo'
    if ext in audio_extensions:
        return 'audio'
    return 'document'
# ========== Progress tracking ==========
class TelegramProgressTracker:
    """A non-blocking progress tracker for Pyrogram uploads/downloads.
    Provides a real-time progress bar in Telegram chat with speed and ETA information.
    """
    import time
    import datetime
    from pyrogram.errors import FloodWait, MessageNotModified
    def __init__(self, status_msg: Message, filename: str, size_mb: float, operation: str = "Uploading", user_msg: Message = None):
        self.status_msg = status_msg
        self.filename = filename
        self.size_mb = size_mb
        self.operation = operation
        self.user_msg = user_msg  # Original user message to reply to
        self.last_update_percent = -1
        self.last_update_time = time.time()
        self.start_time = time.time()
        self.progress_bar = None  # We'll focus on Telegram progress updates
    def __call__(self, current: int, total: int):
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, create a task
                loop.create_task(self._update(current, total))
            else:
                # If we're in a sync context, run until complete
                loop.run_until_complete(self._update(current, total))
        except Exception:
            # Handle case where event loop is not available
            pass
    def close(self):
        """Clean up resources"""
        if self.progress_bar:
            self.progress_bar.close()
    async def _update(self, current: int, total: int):
        try:
            if total <= 0:
                percent = 0.0
            else:
                percent = (current / total) * 100
            current_time = time.time()
            time_elapsed = current_time - self.start_time
            # Only update Telegram message if:
            # 1. 5% progress change OR
            # 2. At least 3 seconds passed since last update
            if (int(percent) >= self.last_update_percent + 5 or 
                current_time - self.last_update_time >= 3):
                self.last_update_percent = int(percent)
                self.last_update_time = current_time
                # Calculate speed and ETA
                if time_elapsed > 0:
                    speed = (current / 1_048_576) / time_elapsed  # MB/s
                    if speed > 0:
                        eta = (total - current) / (speed * 1_048_576)
                    else:
                        eta = 0
                else:
                    speed = 0
                    eta = 0
                # Create progress bar
                filled = int(percent // 5)
                progress_visual = "█" * filled + "░" * (20 - filled)
                # Format status message with mention
                mention = f"[{self.user_msg.from_user.first_name}](tg://user?id={self.user_msg.from_user.id})" if self.user_msg else ""
                status = (
                    f"{mention}\n\n" if mention else "" +
                    f"{'🔼' if self.operation.lower() == 'uploading' else '🔽'} "
                    f"**{self.operation}**: `{self.filename}`\n\n"
                    f"**Size**: {self.size_mb:.1f} MB\n"
                    f"**Progress**: {percent:.1f}%\n"
                    f"**Speed**: {speed:.1f} MB/s\n"
                    f"**ETA**: {datetime.timedelta(seconds=int(eta))}\n\n"
                    f"`{progress_visual}`"
                )
                try:
                    await self.status_msg.edit_text(
                        text=status,
                        parse_mode="markdown",
                        disable_web_page_preview=True
                    )
                except:
                    pass
        except:
            pass
    def close(self):
        return
class GoFileUploadProgress:
    def __init__(self, status_msg: Message, filename: str, size_mb: float):
        self.status_msg = status_msg
        self.filename = filename
        self.size_mb = size_mb
        self.progress_bar = None
        self.last = 0
    def update(self, current: int, total: int):
        # update tqdm console bar (optional) and edit message periodically
        try:
            if total <= 0:
                percent = 0.0
            else:
                percent = (current / total) * 100
            # Only edit every ~10%
            if int(percent) >= self.last + 10:
                self.last = int(percent)
                filled = int(percent // 5)
                progress_visual = "█" * filled + "░" * (20 - filled)
                try:
                    asyncio.create_task(self.status_msg.edit(
                        f"⏫ Uploading to GoFile: {self.filename}\n"
                        f"📊 {self.size_mb:.1f}MB | Progress: {percent:.1f}%\n"
                        f"[{progress_visual}]"
                    ))
                except Exception:
                    pass
        except Exception:
            pass
    def close(self):
        return
# ========== GoFile upload function (uses requests) ==========
def upload_to_gofile_api(file_path):
    url = "https://store2.gofile.io/uploadFile"
    with open(file_path, "rb") as f:
        files = {"file": f}
        r = requests.post(url, files=files)
        response_data = r.json() # Capture the JSON response

        if r.status_code == 200:
            print("Full response:") # Print full response
            print(response_data)

            if response_data.get('status') == 'ok': # Use .get for safety
                file_id = response_data['data']['id']
                file_name = response_data['data']['name']

                # Construct the download link in the desired format
                download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'
                print(f'File uploaded successfully! Public link: link ({download_link})') # Print the link
                # Return the full data for handle_upload_callback to use
                return response_data
            else: # Status not ok, but status code was 200
                raise Exception(f"GoFile upload status not ok: {response_data.get('error', 'Unknown error')}")
        else: # Status code not 200
            raise Exception(f"GoFile upload failed with status code {r.status_code}: {response_data.get('error', 'Unknown error')}")
# ========== VOE Upload Function ==========
async def upload_to_voe(client, message: Message):
    reply = message.reply_to_message
    if not (reply.video or reply.document):
        await message.reply("⚠️ Please reply to a video (mp4, mkv, avi, mov) with `.voe`.", quote=True)
        return
    media = reply.video or reply.document
    # Try to get filename and mime info
    file_name = getattr(media, "file_name", None) or getattr(media, "file_unique_id", "upload")
    media_mime = getattr(media, "mime_type", None)
    # Determine if it is likely a video
    is_video = False
    if media_mime and media_mime.startswith("video"):
        is_video = True
    else:
        guessed, _ = mimetypes.guess_type(file_name)
        if guessed and guessed.startswith("video"):
            is_video = True
    if not is_video:
        await message.reply("❌ VOE only accepts video files (mp4, mkv, avi, mov). Please reply with a supported video file.", quote=True)
        return
    temp = tempfile.NamedTemporaryFile(delete=False)
    temp_path = temp.name
    temp.close()
    status_msg = await message.reply("📥 Downloading file...", quote=True)
    try:
        await client.download_media(media, file_name=temp_path)
        # Step 1: Get upload server
        r = requests.get(VOE_API_SERVER, params={"key": VOE_API_KEY}, timeout=30)
        if r.status_code != 200:
            raise Exception(f"Failed to get server (HTTP {r.status_code}) - {r.text}")
        res = r.json()
        if not res.get("success"):
            raise Exception(f"Server error: {res.get('message', 'Unknown error')}")
        upload_url = res["result"]
        await status_msg.edit("⏫ Uploading to VOE...")
        # Step 2: Upload file (send filename and mime if available)
        mime_type_to_send = media_mime or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        with open(temp_path, "rb") as f:
            files = {"file": (file_name, f, mime_type_to_send)}
            upload_res = requests.post(upload_url, files=files, params={"key": VOE_API_KEY}, timeout=600)
        if upload_res.status_code != 200:
            raise Exception(f"Upload failed (HTTP {upload_res.status_code}): {upload_res.text}")
        data = upload_res.json()
        if not data.get("success"):
            raise Exception(f"Upload error: {data.get('message', 'Unknown error')}")
        file_code = data["file"]["file_code"]
        file_url = f"https://voe.sx/{file_code}"
        await status_msg.edit(f"✅ Uploaded to VOE!\n🔗 {file_url}", disable_web_page_preview=True)
    except Exception as e:
        logger.exception("VOE upload failed")
        await status_msg.edit(f"❌ VOE upload failed: {e}")
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass
# ========== MixDrop upload helper ==========
 # ========== MULTIUP FUNCTIONS ========== 
MULTIUP_API = "https://multiup.io/api"
MULTIUP_USERNAME = "timipi9811"
MULTIUP_PASSWORD = "Rajpoot@4080"
PROJECT_NAME = "Telegram Uploads"
PROJECT_PASS = ""
PROJECT_DESC = "Uploaded via bot"
FILE_DESC = "Uploaded from Telegram bot"
def login(username, password):
    r = requests.post(f"{MULTIUP_API}/login", data={'username': username, 'password': password})
    data = r.json()
    if data.get('error') and data['error'].lower() != 'success':
        return None
    return data
def get_fastest_server(size):
    r = requests.post(f"{MULTIUP_API}/get-fastest-server", data={'size': str(size)})
    data = r.json()
    if data.get('error') and data['error'].lower() != 'success':
        raise RuntimeError(data['error'])
    return data['server']
def get_hosts():
    r = requests.get(f"{MULTIUP_API}/get-list-hosts")
    data = r.json()
    raw = data.get('hosts', [])
    if isinstance(raw, dict):
        return list(raw.keys())
    if isinstance(raw, str):
        return [h.strip() for h in raw.split(',')]
    if isinstance(raw, list):
        if raw and isinstance(raw[0], dict) and 'host' in raw[0]:
            return [h['host'] for h in raw]
        return raw
    raise RuntimeError("Unrecognized hosts format")
def add_project(name, password, description, user_id):
    payload = {'name': name, 'password': password, 'description': description, 'user-id': user_id}
    r = requests.post(f"{MULTIUP_API}/add-project", data=payload)
    data = r.json()
    if data.get('error') and data['error'].lower() != 'success':
        raise RuntimeError(data['error'])
    return data['hash']
def upload_file(server_url, filepath, user_id, project_hash, description, hosts):
    with open(filepath, 'rb') as f:
        files = {'files[]': (os.path.basename(filepath), f)}  # Include filename in upload
        data = {'user': user_id, 'project-hash': project_hash, 'description': description}
        for h in hosts:
            data[h] = 'true'
        r = requests.post(server_url, data=data, files=files)
    response = r.json()
    if not response:
        raise Exception("Empty response from MultiUp")
    uploads = []
    # Handle the new response format with 'files' array
    if isinstance(response, dict) and 'files' in response:
        files = response['files']
        for file_info in files:
            size_mb = float(file_info.get('size', 0)) / (1024 * 1024)  # Convert to MB
            upload_info = {
                'name': file_info.get('name', os.path.basename(filepath)),
                'size': f"{size_mb:.2f} MB",
                'type': file_info.get('type', 'Unknown'),
                'url': file_info.get('url'),
                'hash': file_info.get('hash'),
                'project': file_info.get('project')
            }
            if upload_info['url']:  # Only add if URL is present
                uploads.append(upload_info)
    if not uploads:
        raise Exception("No valid upload URLs found in response")
    return uploads
 # ========== MultiUp upload helper ========== 
def upload_to_multiup(file_path: str, filename: str) -> str:
    """Upload file to MultiUp and return the download URL."""
    api_url = "https://multiup.org/api/upload"
    with open(file_path, "rb") as f:
        files = {"files[]": (filename, f)}
        response = requests.post(api_url, files=files)
    if response.status_code != 200:
        raise Exception(f"MultiUp HTTP error: {response.status_code} - {response.text}")
    try:
        data = response.json()
    except Exception:
        raise Exception(f"MultiUp returned non-json response: {response.text}")
    # MultiUp returns a list of uploads
    if isinstance(data, list) and len(data) > 0 and 'download_url' in data[0]:
        return data[0]['download_url']
    # Sometimes returns dict with 'files' key
    if isinstance(data, dict) and 'files' in data and len(data['files']) > 0 and 'download_url' in data['files'][0]:
        return data['files'][0]['download_url']
    raise Exception(f"MultiUp upload failed: {data}")
def is_mixdrop_supported(filename: str) -> bool:
    allowed_exts = {'mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'm4v'}
    if not filename or '.' not in filename:
        return False
    return filename.lower().rsplit('.', 1)[-1] in allowed_exts
def upload_to_mixdrop(file_path: str, filename: str, status_msg: Message, file_size_mb: float) -> str:
    """Upload file to MixDrop synchronously (requests). Returns download URL or raises Exception."""
    if not is_mixdrop_supported(filename):
        raise Exception("MixDrop does not support this file extension")
    with open(file_path, 'rb') as f:
        files = {"file": (filename, f)}
        data = {"email": MIXDROP_EMAIL, "key": MIXDROP_KEY}
        r = requests.post(MIXDROP_API_URL, data=data, files=files, timeout=180)
    if r.status_code != 200:
        raise Exception(f"MixDrop HTTP error: {r.status_code} - {r.text}")
    try:
        j = r.json()
    except Exception:
        raise Exception(f"MixDrop returned non-json response: {r.text}")
    if j.get('success') and j.get('result'):
        # result may contain different fields; try common keys
        return j['result'].get('url') or j['result'].get('file') or str(j['result'])
    else:
        raise Exception(f"MixDrop failed: {j}")
# Viki Upload Functionality
def get_viki_server_url():
    response = requests.get("https://vikingfile.com/api/get-server")
    if response.status_code == 200:
        server_data = response.json()
        return server_data["server"]
    else:
        raise Exception(f"Failed to get server URL. Status code: {response.status_code}")
def upload_to_viki(server_url, file_path, user_hash="", path="", path_public_share=""):
    with open(file_path, "rb") as file:
        files = {"file": file}
        data = {
            "user": user_hash,
            "path": path,
            "pathPublicShare": path_public_share,
        }
        response = requests.post(server_url, files=files, data=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to upload file. Status code: {response.status_code}")
# ========== Download from URL helper (for .link) ==========
def download_file_from_url(url: str, max_size_mb: int = 1900) -> tuple[str, str, float]:
    head = requests.head(url, timeout=10, allow_redirects=True)
    if head.status_code not in (200, 206):
        raise Exception(f"URL not accessible (Status {head.status_code})")
    cl = head.headers.get('content-length')
    if cl:
        size_mb = int(cl) / (1024 * 1024)
        if size_mb > max_size_mb:
            raise Exception(f"File too large ({size_mb:.1f}MB). Max allowed: {max_size_mb}MB")
    else:
        size_mb = 0.0
    filename = get_filename_from_url(url, head.headers)
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    temp = tempfile.NamedTemporaryFile(delete=False)
    temp_path = temp.name
    downloaded = 0
    max_bytes = max_size_mb * 1024 * 1024
    for chunk in r.iter_content(chunk_size=8192):
        if chunk:
            downloaded += len(chunk)
            if downloaded > max_bytes:
                temp.close()
                os.unlink(temp_path)
                raise Exception(f"File exceeds max size {max_size_mb}MB")
            temp.write(chunk)
    temp.close()
    final_mb = downloaded / (1024 * 1024)
    return temp_path, filename, final_mb
# ========== .bg command handler ==========
async def handle_bg_remove(client: Client, message: Message):
    if not REMBG_AVAILABLE:
        await message.reply("⚠️ Background removal feature is not available on the server (rembg not installed).", quote=True)
        return
    reply = message.reply_to_message
    if not reply or not reply.photo:
        await message.reply("⚠️ Please reply to an image with `.bg` or `/bg`.", quote=True)
        return
    temp_in = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    temp_in.close()
    status_msg = await message.reply_text("📥 Downloading image...", quote=True)
    try:
        await client.download_media(reply.photo, file_name=temp_in.name)
        await status_msg.edit_text("🖼️ Removing background...")
        with open(temp_in.name, 'rb') as f:
            input_image = f.read()
            output_image = remove(input_image)
        out_path = temp_in.name.replace('.png', '_nobg.png')
        with open(out_path, 'wb') as out:
            out.write(output_image)
        await status_msg.edit("✅ Background removed! Sending image...")
        await message.reply_document(document=out_path, caption="Here's your image with background removed", quote=True)
        await status_msg.delete()
    except Exception as e:
        logger.exception("Background removal failed")
        await status_msg.edit_text(f"❌ Background removal failed: {e}")
    finally:
        for p in (temp_in.name, locals().get('out_path', None)):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass
# ========== Core upload handlers and command registration ==========
async def handle_link_download(client: Client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        await message.reply_text("❌ Please provide a URL. Usage: .link <url>")
        return
    url = message.text.split(maxsplit=1)[1].strip()
    status_msg = await message.reply_text("⏬ Downloading... Please wait.")
    tmp_path = None
    try:
        tmp_path, filename, file_size_mb = download_file_from_url(url)
        await status_msg.edit_text(
            f"📥 Download complete. Uploading to Telegram...\n"
            f"📁 Filename: {filename}\n"
            f"📊 Size: {file_size_mb:.1f} MB"
        )
        file_type = get_file_type(filename)
        if file_type == 'video':
            await message.reply_video(
                video=tmp_path,
                caption=f"Downloaded from: {url}",
                supports_streaming=True
            )
        elif file_type == 'photo':
            await message.reply_photo(
                photo=tmp_path,
                caption=f"Downloaded from: {url}"
            )
        elif file_type == 'audio':
            await message.reply_audio(
                audio=tmp_path,
                caption=f"Downloaded from: {url}"
            )
        else: # document or unknown
            await message.reply_document(
                document=tmp_path,
                caption=f"Downloaded from: {url}"
            )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Link download error: {e}")
        await status_msg.edit_text(f"❌ Error: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
def register_utility_commands(app: Client):
    @app.on_message(filters.command("start"), group=1)
    async def start(client, message: Message):
        await message.reply("👋 Hello! I'm your assistant bot. Use /help to see all commands.", quote=True)
    @app.on_message(filters.command("help"), group=2)
    async def help_command(client, message: Message):
        await message.reply(HELP_TEXT, quote=True)
    if REMBG_AVAILABLE:
        @app.on_message(filters.regex(r'^[./]bg(\s|$)') & filters.reply, group=3)
        async def bg_remove_command(client, message: Message):
            await handle_bg_remove(client, message)
    @app.on_message(filters.regex(r'^[./]up(\s|$)') & filters.reply, group=4)
    async def unified_upload_command(client, message: Message):
        reply = message.reply_to_message
        if not reply or not (reply.video or reply.document or reply.photo or reply.audio):
            await message.reply("⚠️ Please reply to a video, document, photo, or audio file with `.up` or `/up`.", quote=True)
            return
        replied_msg_id = reply.id
        media_obj = (reply.document or reply.video or reply.photo or reply.audio)
        file_name = getattr(media_obj, 'file_name', 'media')
        keyboard = InlineKeyboardMarkup([
            [ 
                InlineKeyboardButton("MixDrop", callback_data=f"up:mixdrop:{replied_msg_id}"),
                InlineKeyboardButton("MultiUp", callback_data=f"up:multiup:{replied_msg_id}"),
                InlineKeyboardButton("GoFile", callback_data=f"up:gofile:{replied_msg_id}")
            ],
            [
                InlineKeyboardButton("VOE", callback_data=f"up:voe:{replied_msg_id}"),
                InlineKeyboardButton("Viki", callback_data=f"up:viki:{replied_msg_id}")
            ],
            [
                InlineKeyboardButton("ALL", callback_data=f"up:all:{replied_msg_id}")
            ]
        ])
        await message.reply(f"Select upload service for `{file_name}`:", reply_markup=keyboard, quote=True)
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile|voe|viki):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download : Link {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'voe': # Handle VOE upload
                # The provided `upload_to_voe` function already handles downloading and messaging
                # It expects `message` to be the original user message, not the status_msg.
                # So we will call it with `replied_msg` as the "message" argument.
                # However, the original `upload_to_voe` creates its own `status_msg`.
                # We need to adapt it to use the existing `status_msg` from the callback query.
                # Or, simplify: the user just wants the button added, and the VOE logic
                # is already defined to respond to `filters.regex(r'^\.voe') & filters.reply`.
                # If the user only wants the button for the existing command, I'll direct them
                # to use the command with reply, or make the button trigger the exact same
                # function that they gave.

                # Let's assume the provided `upload_to_voe` function is meant to be called directly.
                # It currently expects `message` to be the original message.
                # The callback handler only has `callback_query.message` (the message with buttons).
                # To re-use the `upload_to_voe` as is, it's better to pass the `replied_msg` to it.
                # But `upload_to_voe` also calls `message.reply`. We need it to *edit* `status_msg`.

                # New approach: Directly integrate the logic for VOE here, using `status_msg`.
                # This avoids re-downloading and re-messaging.
                if not (replied_msg.video or replied_msg.document):
                    await status_msg.edit("⚠️ VOE only accepts video or document files.")
                    return
                media_voe = replied_msg.video or replied_msg.document
                file_name_voe = getattr(media_voe, "file_name", None) or getattr(media_voe, "file_unique_id", "upload")
                media_mime_voe = getattr(media_voe, "mime_type", None)
                is_video_voe = False
                if media_mime_voe and media_mime_voe.startswith("video"):
                    is_video_voe = True
                else:
                    guessed_voe, _ = mimetypes.guess_type(file_name_voe)
                    if guessed_voe and guessed_voe.startswith("video"):
                        is_video_voe = True
                if not is_video_voe:
                    await status_msg.edit("❌ VOE only accepts video files (mp4, mkv, avi, mov). Please select a supported video file.")
                    return
                try:
                    await status_msg.edit("⏫ Uploading to VOE...")
                    # Step 1: Get upload server
                    r = requests.get(VOE_API_SERVER, params={"key": VOE_API_KEY}, timeout=30)
                    if r.status_code != 200:
                        raise Exception(f"Failed to get server (HTTP {r.status_code}) - {r.text}")
                    res = r.json()
                    if not res.get("success"):
                        raise Exception(f"Server error: {res.get('message', 'Unknown error')}")
                    upload_url = res["result"]
                    # Step 2: Upload file (send filename and mime if available)
                    mime_type_to_send = media_mime_voe or mimetypes.guess_type(file_name_voe)[0] or "application/octet-stream"
                    with open(tmp_path, "rb") as f: # Use already downloaded tmp_path
                        files = {"file": (file_name_voe, f, mime_type_to_send)}
                        upload_res = requests.post(upload_url, files=files, params={"key": VOE_API_KEY}, timeout=600)
                    if upload_res.status_code != 200:
                        raise Exception(f"Upload failed (HTTP {upload_res.status_code}): {upload_res.text}")
                    data = upload_res.json()
                    if not data.get("success"):
                        raise Exception(f"Upload error: {data.get('message', 'Unknown error')}")
                    file_code = data["file"]["file_code"]
                    file_url = f"https://voe.sx/{file_code}"
                    await status_msg.edit(f"✅ Uploaded to VOE!\n🔗 {file_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("VOE upload failed")
                    await status_msg.edit(f"❌ VOE upload failed: {e}")
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
        try:
            file_size_mb = getattr(media, 'file_size', 0) / (1024*1024)
            await status_msg.edit_text(f"📥 Downloading media...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
            download_tracker = TelegramProgressTracker(status_msg, filename, file_size_mb, "Downloading")
            await client.download_media(media, file_name=tmp_path, progress=download_tracker)
            file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            if service == 'gofile':
                await status_msg.edit_text(f" Uploading to GoFile...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Modified upload_to_gofile_api to return full response_data
                    response_data = upload_to_gofile_api(tmp_path)
                    # Extract necessary information from response_data
                    file_id = response_data['data']['id']
                    file_name = response_data['data']['name']
                    download_page_url = response_data['data']['downloadPage']
                    # Construct the custom download link as per user example
                    custom_download_link = f'https://store2.gofile.io/download/web/{file_id}/{file_name}'

                    logger.debug(f"GoFile upload URL (downloadPage): {download_page_url}")
                    logger.debug(f"GoFile custom download link: {custom_download_link}")

                    # Update the status message to include both links, prioritizing the custom one
                    await status_msg.edit_text(
                        f"✅ Uploaded successfully!\n"
                        f"📁 Filename: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"🔗 Download Link: {custom_download_link}\n" # User's custom link
                        f"ℹ️ GoFile Link: {download_page_url}", # The original link returned
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.exception("GoFile upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'mixdrop':
                await status_msg.edit_text(f" Uploading to MixDrop...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    download_url = upload_to_mixdrop(tmp_path, filename, status_msg, file_size_mb)
                    await status_msg.edit_text(f"✅ Uploaded to MixDrop successfully!\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MixDrop upload failed")
                    await status_msg.edit_text(f"❌ MixDrop upload failed: {e}", disable_web_page_preview=True)
            elif service == 'multiup':
                try:
                    msg = await status_msg.edit_text(
                        "Preparing MultiUp upload...\n"
                        f"File: {filename}\n"
                        f"Size: {file_size_mb:.1f} MB",
                        disable_web_page_preview=True
                    )
                    # Login to MultiUp
                    info = login(MULTIUP_USERNAME, MULTIUP_PASSWORD)
                    if not info or 'user' not in info:
                        raise Exception("MultiUp login failed. Please check credentials.")
                    user_id = str(info['user'])
                    size = os.path.getsize(tmp_path)
                    server = get_fastest_server(size)
                    all_hosts = get_hosts()
                    allowed = {'gofile.io', 'vikingfile.com', 'savefiles.com', 'streamtape.com'}
                    hosts = [h for h in all_hosts if h in allowed]
                    if not hosts:
                        raise Exception("No allowed hosts found.")
                    project_hash = add_project(PROJECT_NAME, PROJECT_PASS, PROJECT_DESC, user_id)
                    upload_url = server.rstrip('/') + "/upload/index.php"
                    await status_msg.edit_text(f" Uploading to MultiUp...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                    uploads = upload_file(upload_url, tmp_path, user_id, project_hash, FILE_DESC, hosts)
                    # Format upload results
                    upload_details = []
                    for upload in uploads:
                        upload_details.append(
                            f"📁 {upload['name']}\n"
                            f" Size: {upload['size']}\n"
                            f"📝 Type: {upload['type']}\n"
                            f"🔗 URL: {upload['url']}\n"
                        )
                    if not upload_details:
                        raise Exception("Upload completed but failed to get valid URLs")
                    result_text = (
                        f"✅ Uploaded to MultiUp successfully!\n\n"
                        f"📁 Original file: {filename}\n"
                        f"📊 Size: {file_size_mb:.1f} MB\n\n"
                        f"Upload Results:\n{'─' * 30}\n\n"
                        f"{'\n\n'.join(upload_details)}"
                    )
                    await msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("MultiUp upload failed")
                    await status_msg.edit_text(f"❌ Upload failed: {e}", disable_web_page_preview=True)
            elif service == 'viki':
                await status_msg.edit_text(f" Uploading to Viki...\n📁 Filename: {filename}\n📊 Size: {file_size_mb:.1f} MB", disable_web_page_preview=True)
                try:
                    # Get server URL and upload file
                    server_url = get_viki_server_url()
                    upload_response = upload_to_viki(server_url, tmp_path) # Using default empty values for user_hash, path, path_public_share
                    # Extract download URL from the response if available
                    download_url = upload_response.get('url') or upload_response.get('download') # Viki response might have different keys
                    if download_url:
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully!\n🔗 Download URL: {download_url}", disable_web_page_preview=True)
                    else:
                        # If no direct URL, return the whole response for inspection
                        await status_msg.edit_text(f"✅ Uploaded to Viki successfully! Response:\n```json\n{upload_response}\n```", disable_web_page_preview=True)
                except Exception as e:
                    logger.exception("Viki upload failed")
                    await status_msg.edit_text(f"❌ Viki upload failed: {e}", disable_web_page_preview=True)
            else:
                await status_msg.edit("❌ Unknown upload service selected.")
        except Exception as e:
            logger.exception("Error during upload handler")
            try:
                await status_msg.edit(f"❌ Error during upload process: {e}")
            except Exception:
                pass
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
    @app.on_message(filters.regex(r'^[./]link( |$)'), group=6) # Added .link command handler
    async def link_command(client, message: Message):
        await handle_link_download(client, message)
    # Optional: debug catch-all callback (uncomment to help debug callback delivery)
    # @app.on_callback_query()
    # async def debug_any_callback(client, cq: CallbackQuery):
    #     logger.info(f"ANY CALLBACK: {cq.data} from {cq.from_user.id}")
    #     try:
    #         await cq.answer()
    #     except Exception:
    #         pass
    # Robust callback handler
    @app.on_callback_query(filters.regex(r'^up:(mixdrop|multiup|gofile):'), group=5)
    async def handle_upload_callback(client, callback_query: CallbackQuery):
        # Acknowledge quickly so client stops showing spinner
        try:
            await callback_query.answer()
        except Exception:
            pass
        data = callback_query.data or ""
        logger.info(f"[UPLOAD_CALLBACK] {data} from {callback_query.from_user.id}")
        parts = data.split(':')
        if len(parts) != 3:
            await callback_query.message.edit("❌ Invalid callback data.")
            return
        _, service, replied_msg_id = parts
        chat_id = callback_query.message.chat.id
        status_msg = callback_query.message
        # Fetch the original message that contained the media
        try:
            replied_msg = await client.get_messages(chat_id, int(replied_msg_id))
        except Exception as e:
            logger.exception("Failed to fetch replied message")
            await status_msg.edit("❌ Could not fetch the original message.")
            return
        if not replied_msg or not (replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio):
            await callback_query.answer("Original file not found.", show_alert=True)
            await status_msg.edit("❌ Original file not found or it's not a media file.")
            return
        media = replied_msg.video or replied_msg.document or replied_msg.photo or replied_msg.audio
        filename = getattr(media, 'file_name', f'file_{getattr(media, "file_id", "unknown")}')
        # Create temp file preserving the original filename
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        # Ensure the temporary directory exists
        os.makedirs(tempfile.gettempdir(), exist_ok=True)
