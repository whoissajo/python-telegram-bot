# 🤖 Advanced Telegram Bot

A powerful Telegram bot with AI chat, image generation, file management, and media platform integrations.

## ✨ Features

- 🧠 Multiple AI chat models
- 🎨 Image generation & background removal
- 📤 Multi-platform file uploads
- 🎬 Video platform integration
- 🖼️ Image hosting and management

## 📁 Project Structure

```
├── main.py                  # Main bot runner
├── config.py               # Configuration and settings
├── ai_commands.py          # AI chat and image commands
├── utility_commands.py     # Basic and file commands
├── mux_commands.py         # Mux video integration
├── cloudinary_commands.py  # Image hosting
├── multiup_commands.py     # MultiUp integration
├── yt_commands.py         # YouTube integration
└── requirements.txt       # Dependencies
```

## 🚀 Getting Started

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the bot:
```bash
python main.py
```

## � Available Commands

### AI & Image Generation
- `/deep3`, `/gpt4`, `/grok4` + message - Chat with different AI models
- `/image`, `/image1`, `/image2` + prompt - Generate images with various models
- Reply `.bg` to image - Remove background

### File Management
- Reply `.up` - Upload to GoFile
- Reply `.upmix` - Upload video to MixDrop
- Reply `.imgup` - Upload image to Cloudinary
- `.link <url>` - Download from URL (max 1900MB)

### Media Platform Integration
- `.mux` - View/manage Mux videos
- `.imgs` - Browse Cloudinary images
- Reply `.muxup` - Upload to Mux

### Basic Commands
- `/start` - Check bot status
- `/help` - Show command menu

> 💡 All commands work with either `.` or `/` prefix

## 🔧 Module Details

### `config.py`
- API credentials and endpoints
- Model configurations
- Bot settings and defaults
- Help text and logging setup

### `ai_commands.py`
- AI chat integration (Deep3, GPT-4, Grok-4)
- Image generation (multiple models)
- API error handling

### `utility_commands.py`
- File upload functionality
- Background removal
- Basic command handlers
- URL download support

### `mux_commands.py`
- Video platform integration
- Asset management
- Interactive video controls

### `cloudinary_commands.py`
- Image hosting integration
- Image library management

### `multiup_commands.py`
- Multi-platform file uploads
- Upload status tracking

### `yt_commands.py`
- YouTube integration features

## 🛠️ Development

To add new features:

1. Choose appropriate module or create new one
2. Add command handlers
3. Update configuration if needed
4. Register commands in `main.py`
5. Update help text in `config.py`

## 🔒 Security

- API keys and tokens stored in config.py
- Rate limiting implemented for API calls
- Error handling for all operations

## ⚡ Performance

- Asynchronous command handling
- Efficient file transfer
- Progress tracking for uploads
- Modular architecture for scalability

---

📝 For detailed command usage examples and updates, use `/help` in the bot.

## 📝 Notes

- The bot session file (`a4f_bot.session`) remains the same
- All API keys and tokens are preserved in `config.py`
- Logging configuration is centralized in `config.py`
- Error handling is improved with better logging
