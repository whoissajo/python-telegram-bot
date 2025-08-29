import time
from tqdm import tqdm
from pyrogram import Client, filters
from pyrogram.types import Message

def show_progress(client, message: Message):
    # Wait for 3 seconds before starting the progress update
    time.sleep(3)

    total_steps = 100  # Total steps for the progress bar
    bar_length = 20  # Length of the progress bar (in terms of blocks)

    # Using tqdm to create the progress bar
    for step in tqdm(range(total_steps), desc="Processing...", ncols=100, ascii=True):
        # Calculate how many filled blocks there should be
        filled_blocks = "█" * (step * bar_length // total_steps)
        empty_blocks = "░" * (bar_length - len(filled_blocks))

        # Construct the progress bar string
        progress_bar = f"[{filled_blocks}{empty_blocks}] {step}%"
        
        # Update the Telegram message with the current progress
        message.edit(f"Progress.... {progress_bar}")
        
        # Simulate some work being done (this will make the bar take ~5 seconds)
        time.sleep(0.05)

    # Once the progress is complete, finalize the message
    message.edit("Progress completed..!")

def register_progress(app: Client):
    @app.on_message(filters.command("pr"))
    def progress_handler(client, message):
        # Send a new message indicating that the process has started
        msg = message.reply("Starting progress... Please wait.")
        show_progress(client, msg)
