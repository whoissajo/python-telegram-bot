import yt_dlp
import tempfile
import os
from pyrogram import filters
from pyrogram.types import Message
from config import logger
import asyncio

async def handle_yt_download(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        await message.reply_text("❌ Please provide a YouTube URL. Usage: .yt <url>", quote=True)
        return
    url = message.text.split(maxsplit=1)[1].strip()
    status_msg = await message.reply_text("⏬ Downloading... Please wait.", quote=True)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            last_update_percent = 0
            last_edit_time = 0
            async def update_progress(percent, filename, speed=None, eta=None):
                filled = int(percent // 5)
                progress_visual = "█" * filled + "░" * (20 - filled)
                status = f"⏬ Downloading...\n{percent:.1f}% [{progress_visual}]"
                if filename:
                    status += f"\n{filename}"
                if speed:
                    status += f"\nSpeed: {speed/1024:.1f} KB/s"
                if eta:
                    status += f"\nETA: {eta}s"
                await status_msg.edit(status)
                await asyncio.sleep(3) # Add 3 seconds wait

            async def _send_upload_status():
                await status_msg.edit("📤 Uploading to Telegram...")
                await asyncio.sleep(3) # Add 3 seconds wait

            def progress_hook(d):
                nonlocal last_update_percent, last_edit_time
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes', 0)
                    percent = (downloaded / (total or 1)) * 100 if total else 0
                    import time
                    now = time.time()
                    # Only update if 10% more or 10 seconds passed
                    if percent - last_update_percent >= 10 or now - last_edit_time >= 10 or percent == 100:
                        last_update_percent = percent
                        last_edit_time = now
                        filename = d.get('filename', '')
                        speed = d.get('speed', None)
                        eta = d.get('eta', None)
                        asyncio.create_task(update_progress(percent, filename, speed, eta))
                elif d['status'] == 'finished':
                    asyncio.create_task(_send_upload_status())

            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'merge_output_format': 'mp4',
                'progress_hooks': [progress_hook],
                'filepath_cleanup_re': r'[\\/:*?"<>|\x00-\x1f\x7f\uff01-\uff3a\uff41-\uff5a\uff60-\uff9f]+',
                'max_filename_len': 100
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            files = os.listdir(tmpdir)
            if not files:
                await status_msg.edit("❌ Download failed. No file found.")
                return
            file_path = os.path.join(tmpdir, files[0])
            await status_msg.edit("📤 Uploading to Telegram...")
            await asyncio.sleep(3) # Add 3 seconds wait
            await message.reply_video(
                video=file_path,
                caption=f"Downloaded from: {url}",
                supports_streaming=True,
                quote=True
            )
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        await status_msg.edit(f"❌ Error: {e}")

def register_yt_commands(app):
    @app.on_message(filters.regex(r'^[./]yt( |$)'))
    async def yt_command(client, message: Message):
        await handle_yt_download(client, message)
