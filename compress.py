import os
import subprocess
import tempfile
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import asyncio

# Helper function to compress the video and return the process
def start_compress_video(input_video_path, output_video_path):
    # Command to compress the video with ffmpeg, keeping the original quality
    command = [
        "ffmpeg", 
        "-i", input_video_path, 
        "-vcodec", "libx264", 
        "-crf", "23",  # CRF 23 is a good balance, adjust as needed for quality/size tradeoff
        "-preset", "slow", 
        "-acodec", "aac", 
        "-b:a", "128k", 
        output_video_path
    ]
    
    # Run the ffmpeg process and return it
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Function to show the progress of compression
def get_progress_from_stderr(stderr_lines):
    for line in stderr_lines:
        line = line.decode('utf-8')
        if 'time=' in line:
            time_str = line.split('time=')[1].split(' ')[0]
            return time_str
    return None

# Function to handle the compress request
async def compress(client: Client, message: Message):
    print("Received a message to compress.")  # Log statement for debugging
    try:
        # Check if the message contains a video
        if message.video:
            print(f"Received .compress reply to video: {message.video.file_id}")  # Log video details

            # Get the video file from the message
            video_file_path = await message.download()

            # Create a temporary file for the compressed video
            output_video_path = tempfile.mktemp(suffix=".mp4")

            # Start the compression process
            process = start_compress_video(video_file_path, output_video_path)

            # Show progress and update the user
            progress_message = await message.reply("Compressing video... Please wait.")
            try:
                # Continuously read stderr for progress updates
                while process.poll() is None:  # While the process is still running
                    line = process.stderr.readline()
                    if line:
                        progress = get_progress_from_stderr([line])
                        if progress:
                            await progress_message.edit(f"Compressing video... {progress}")
                    await asyncio.sleep(1)  # Avoid busy-waiting

                # Get final output and errors after process completes
                out, err = process.communicate()
                if err:
                    print(f"Error during compression: {err.decode('utf-8')}")
                
                if process.returncode != 0:
                    await message.reply(f"Compression failed with error: {err.decode('utf-8')}")
                    return

            except FloodWait as e:
                await asyncio.sleep(e.x)
                # Re-try editing the message after flood wait
                while process.poll() is None:
                    line = process.stderr.readline()
                    if line:
                        progress = get_progress_from_stderr([line])
                        if progress:
                            await progress_message.edit(f"Compressing video... {progress}")
                    await asyncio.sleep(1)
                out, err = process.communicate() # Ensure to communicate again after flood wait if process was still running
            except Exception as e:
                print(f"Error during progress update or compression: {e}")
                await message.reply("An error occurred during video compression. Please try again.")
                # Ensure the process is terminated if an error occurs during monitoring
                if process.poll() is None:
                    process.terminate()
                return
            finally:
                # Send the compressed video back to the user
                if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 0:
                    await message.reply_video(output_video_path)
                else:
                    await message.reply("Compressed video file was not found or is empty.")
                
                await progress_message.delete()

            # Clean up the temp files
            if os.path.exists(video_file_path):
                os.remove(video_file_path)
            if os.path.exists(output_video_path):
                os.remove(output_video_path)
        else:
            await message.reply("Please reply to a video with `.compress` to compress it.")

    except Exception as e:
        print(f"Error occurred in main compress function: {e}")
        await message.reply("Something went wrong while compressing the video. Please try again.")

# Register the handler
def register_compress(app: Client):
    app.add_handler(filters.text & filters.regex(r"\.compress$"), compress)
