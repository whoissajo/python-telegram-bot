import requests
from pyrogram import filters
from pyrogram.types import Message
from config import logger
import os

MULTIUP_API = "https://multiup.io/api"

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

def register_multiup_commands(app):
    """
    Register .upmul command for file uploads
    """
    @app.on_message(filters.regex(r'^[./]upmul') & filters.reply)
    async def upmul_command(client, message: Message):
        """
        Handle .upmul command to upload replied file to MultiUp
        """
        reply = message.reply_to_message
        if not reply or not (reply.document or reply.video):
            await message.reply("⚠️ Please reply to a file or video with `.upmul` to upload it to MultiUp.")
            return

        # Download the file
        status_msg = await message.reply("📥 Downloading file...")
        try:
            file_path = await client.download_media(
                message=reply,
file_name=f"temp_{reply.id}"
            )
            if not file_path:
                await status_msg.edit("❌ Failed to download file.")
                return

            # Get user credentials from config (not implemented in example)
            # For demonstration using placeholder values
            user_id = "demo_user"
            project_hash = "demo_project_hash"
            
            # Get hosts and fastest server
            try:
                hosts = get_hosts()
                server_url = get_fastest_server(os.path.getsize(file_path))
                
                # Upload file
                await status_msg.edit("⬆️ Uploading to MultiUp...")
                urls = upload_file(
                    server_url=server_url,
                    filepath=file_path,
                    user_id=user_id,
                    project_hash=project_hash,
                    description="Uploaded via Telegram bot",
                    hosts=hosts
                )
                
                # Send results
                if urls:
                    await status_msg.edit(
                        "✅ Upload successful! Share links:\n\n" + 
                        "\n".join(urls),
                        disable_web_page_preview=True
                    )
                else:
                    await status_msg.edit("❌ Upload completed but no URLs were returned.")
                    
            except Exception as e:
                await status_msg.edit(f"❌ Upload failed: {str(e)}")
                
        finally:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
    
    @app.on_message(filters.regex(r'^[./]upviki') & filters.reply)
    async def upviki_command(client, message: Message):
        """
        Handle .upviki command to upload replied file to Viki
        """
        reply = message.reply_to_message
        if not reply or not (reply.document or reply.video):
            await message.reply("⚠️ Please reply to a file or video with `.upviki` to upload it to Viki.")
            return

        status_msg = await message.reply("📥 Downloading file for Viki upload...")
        try:
            file_path = await client.download_media(
                message=reply,
                file_name=f"temp_viki_{reply.id}"
            )
            if not file_path:
                await status_msg.edit("❌ Failed to download file for Viki.")
                return

            # Placeholder values for user_hash, path, and path_public_share
            user_hash = "8muwyRuAZW"  # Replace with actual user hash if available
            path = ""                 # Replace with desired path if needed
            path_public_share = ""    # Replace with public share path if needed

            await status_msg.edit("⬆️ Uploading to Viki...")
            server_url = get_viki_server_url()
            upload_response = upload_to_viki(server_url, file_path, user_hash, path, path_public_share)

            if upload_response:
                # Assuming Viki returns a structure with a 'url' or similar key for the link
                # Adjust this part based on the actual response from Viki
                if 'url' in upload_response:
                    await status_msg.edit(f"✅ Upload successful to Viki!\nShare link: {upload_response['url']}")
                elif 'links' in upload_response and isinstance(upload_response['links'], dict) and 'url' in upload_response['links']:
                    await status_msg.edit(f"✅ Upload successful to Viki!\nShare link: {upload_response['links']['url']}")
                else:
                    await status_msg.edit("✅ Upload successful to Viki! Could not extract share link from response.")
            else:
                await status_msg.edit("❌ Upload to Viki completed but no URLs were returned.")

        except Exception as e:
            await status_msg.edit(f"❌ Upload to Viki failed: {str(e)}")
        finally:
            # Clean up the downloaded file
            if os.path.exists(file_path):
                os.remove(file_path)

    logger.info("Viki upload command registered successfully.")
    logger.info("MultiUp commands registered successfully.")

def upload_file(server_url, filepath, user_id, project_hash, description, hosts):
    with open(filepath, 'rb') as f:
        files = {'files[]': f}
        data = {'user': user_id, 'project-hash': project_hash, 'description': description}
        for h in hosts:
            data[h] = 'true'
        r = requests.post(server_url, data=data, files=files)

    # Log the response content and status code
    logger.info(f"Response from MultiUp API: {r.content}")
    logger.info(f"Response status code: {r.status_code}")

    # Parse JSON
    try:
        resp = r.json()
        logger.info(f"RAW UPLOAD RESPONSE: {resp}")

        urls = []
        # Handle MultiUp API response with 'files' key (list of dicts)
        if isinstance(resp, dict) and 'files' in resp and isinstance(resp['files'], list):
            for file_info in resp['files']:
                if 'url' in file_info:
                    urls.append(file_info['url'])
        else:
            # Fallback to previous logic for other response shapes
            items = resp if isinstance(resp, list) else [resp]
            for item in items:
                if 'url' in item:
                    urls.append(item['url'])
                elif 'link' in item:
                    urls.append(item['link'])
                elif 'links' in item and isinstance(item['links'], dict):
                    if 'url' in item['links']:
                        urls.append(item['links']['url'])
        return urls
    except ValueError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        return []

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
