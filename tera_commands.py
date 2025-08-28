from pyrogram import Client, filters
from pyrogram.types import Message
import requests
import os

# Get the download URL from the API
def get_download_url(api_url):
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        print("API response:", data)  # Debug print

        # Check if 'files' exists and contains at least one element
        if "files" in data and len(data["files"]) > 0:
            return data["files"][0].get("download_url")  # Get the download URL
        else:
            return None
    except Exception as e:
        print(f"Error fetching API response: {e}")
        return None

# Download the file using headers to avoid 403 error
def download_file(download_url, file_name):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        ),
        "Referer": "https://terabox-worker.robinkumarshakya103.workers.dev/",
    }
    with requests.get(download_url, headers=headers, stream=True) as r:
        r.raise_for_status()  # This will raise an error if the status code is not 200
        with open(file_name, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                if chunk:
                    f.write(chunk)
    return file_name

# Clean and shorten filename
def sanitize_file_name(file_name):
    file_name = file_name.split('?')[0]
    max_length = 255
    if len(file_name) > max_length:
        file_name = file_name[:max_length]
    file_name = ''.join(c for c in file_name if c.isalnum() or c in (' ', '_', '-', '.'))
    if not file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv')):
        file_name += '.mp4'
    return file_name

# Register the bot command
def register_tera_commands(app: Client):
    @app.on_message(filters.command(["tera", "ter"], prefixes=[".", "/"]))
    async def tera_handler(client: Client, message: Message):
        if len(message.command) < 2:
            await message.reply_text("❗ Please provide a link.\nUsage: `.tera <link>`")
            return

        url = message.command[1]
        await message.reply_text("🔄 Processing your request...")

        api_url = f"https://terabox-worker.robinkumarshakya103.workers.dev/api?url={url}"
        download_url = get_download_url(api_url)

        if not download_url:
            await message.reply_text("❌ Failed to retrieve download URL.")
            return

        # Debug print for download_url
        print(f"Download URL: {download_url}")

        file_name = sanitize_file_name(download_url.split("/")[-1])

        try:
            await message.reply_text("⬇️ Downloading file...")
            download_file(download_url, file_name)

            # Send file after downloading
            await message.reply_document(document=open(file_name, 'rb'))
            os.remove(file_name)
        except Exception as e:
            await message.reply_text(f"⚠️ Error: {str(e)}")
