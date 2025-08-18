# bairyks-telegram-bot
media downloader bot

# 🎵 Multi-Platform Media Downloader Telegram Bot

A powerful Telegram bot that can download content from multiple platforms including Deezer, Reddit, Instagram, and TikTok.

## 🚀 Features

- **Deezer Music Search**: Search and download music previews from Deezer
- **Universal Media Downloader**: Download videos, images, and audio from:
  - 📱 Reddit (videos, images, GIFs)
  - 📸 Instagram (posts, reels, stories)
  - 🎬 TikTok (videos)
- **Inline Mode Support**: Use the bot in any chat with `@YourBotName query`
- **Auto URL Detection**: Send a URL directly and the bot will auto-download
- **Error Handling**: Comprehensive error codes and user-friendly messages
- **File Size Limits**: Respects Telegram's 50MB file size limit

## 📋 Requirements

- Python 3.8+
- Telegram Bot Token
- Required external tools: `yt-dlp`, `gallery-dl`
- Optional: Deezer ARL token for music downloads

## 🔧 Installation

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd telegram-media-bot
pip install -r requirements.txt
```

### 2. Install External Dependencies

#### Install yt-dlp (for Reddit, TikTok)
```bash
pip install yt-dlp
# Or via system package manager
sudo apt install yt-dlp  # Ubuntu/Debian
brew install yt-dlp      # macOS
```

#### Install gallery-dl (for Instagram)
```bash
pip install gallery-dl
# Or via system package manager
sudo apt install gallery-dl  # Ubuntu/Debian
brew install gallery-dl      # macOS
```

### 3. Environment Configuration

Create a `.env` file in the project root:

```env
# Required: Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Optional: Deezer ARL token for full music downloads
# To get ARL: Login to Deezer in browser, check cookies for 'arl' value
DEEZER_ARL=your_deezer_arl_token_here

# Optional: Custom settings
MAX_FILE_SIZE=52428800  # 50MB in bytes
TEMP_DIR=/tmp/telegram_bot
```

### 4. Getting Required Tokens

#### Telegram Bot Token
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot`
3. Follow the prompts to create your bot
4. Copy the provided token

#### Deezer ARL Token (Optional but Recommended)
1. Login to [Deezer](https://deezer.com) in your browser
2. Open Developer Tools (F12)
3. Go to Application/Storage → Cookies → deezer.com
4. Find the `arl` cookie and copy its value
5. Add it to your `.env` file

**Note**: Without ARL token, only 30-second previews can be downloaded from Deezer.

## 🏃‍♂️ Running the Bot

### Local Development
```bash
python bot.py
```

### Production with systemd (Linux)
Create `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram Media Downloader Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/your/bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10
Environment=PATH=/usr/bin:/usr/local/bin
EnvironmentFile=/path/to/your/bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

## 🌐 Free Deployment Options

### 1. Railway.app (Recommended)

1. **Fork this repository** to your GitHub account

2. **Connect to Railway**:
   - Go to [Railway.app](https://railway.app)
   - Sign up with GitHub
   - Click "Deploy from GitHub repo"
   - Select your forked repository

3. **Set Environment Variables**:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   DEEZER_ARL=your_arl_token_here
   ```

4. **Deploy**: Railway will automatically build and deploy your bot

### 2. Render.com

1. **Create account** at [Render.com](https://render.com)

2. **Create new Web Service**:
   - Connect your GitHub repository
   - Build command: `pip install -r requirements.txt`
   - Start command: `python bot.py`

3. **Environment Variables**:
   - Add `TELEGRAM_BOT_TOKEN` and `DEEZER_ARL`

### 3. Heroku (Limited Free Tier)

1. **Install Heroku CLI** and login:
   ```bash
   heroku login
   ```

2. **Create Heroku app**:
   ```bash
   heroku create your-bot-name
   ```

3. **Add buildpacks**:
   ```bash
   heroku buildpacks:add heroku/python
   ```

4. **Set environment variables**:
   ```bash
   heroku config:set TELEGRAM_BOT_TOKEN=your_token
   heroku config:set DEEZER_ARL=your_arl_token
   ```

5. **Create Procfile**:
   ```
   worker: python bot.py
   ```

6. **Deploy**:
   ```bash
   git add .
   git commit -m "Deploy bot"
   git push heroku main
   heroku ps:scale worker=1
   ```

### 4. VPS Deployment (DigitalOcean, Linode, etc.)

```bash
# Install system dependencies
sudo apt update
sudo apt install python3 python3-pip yt-dlp gallery-dl

# Clone and setup
git clone <your-repo>
cd telegram-media-bot
pip3 install -r requirements.txt

# Create systemd service (see above)
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

## 📱 Bot Usage

### Commands

#### `/start`
Shows welcome message and available commands.

#### `/search <song name>`
Search and download music from Deezer.

**Examples:**
```
/search Bohemian Rhapsody Queen
/search Shape of You Ed Sheeran
/search Blinding Lights
```

#### `/download <url>`
Download media from supported platforms.

**Supported URLs:**
```
/download https://reddit.com/r/videos/comments/xyz/title/
/download https://instagram.com/p/ABC123/
/download https://tiktok.com/@user/video/123456789
/download https://vm.tiktok.com/ABC123/
```

### Inline Mode

You can use the bot in any chat by typing:
```
@YourBotName search query
@YourBotName https://instagram.com/p/ABC123/
```

### Auto URL Detection

Simply send a supported URL in any message and the bot will automatically detect and download the media.

## 🔧 Advanced Configuration

### Custom Settings

You can customize the bot behavior by modifying these environment variables:

```env
# File size limit (in bytes)
MAX_FILE_SIZE=52428800  # 50MB

# Custom temporary directory
TEMP_DIR=/tmp/telegram_bot

# Enable debug logging
LOG_LEVEL=DEBUG
```

### Platform-Specific Settings

#### Instagram
For private Instagram content, you may need to configure authentication:

Create `gallery-dl.conf`:
```json
{
    "extractor": {
        "instagram": {
            "username": "your_username",
            "password": "your_password"
        }
    }
}
```

#### Reddit
Reddit downloads work without authentication for public posts. For private subreddits, configure Reddit API credentials.

#### TikTok
TikTok downloads work for public videos. Some regional restrictions may apply.

## 🚨 Error Codes Reference

| Code | Description | Solution |
|------|-------------|----------|
| E101 | Invalid URL | Check URL format and try again |
| E102 | Authentication Failed | Check your ARL token or login credentials |
| E103 | Download Failed | Content may be private or deleted |
| E104 | File Too Large | File exceeds 50MB Telegram limit |
| E105 | Unsupported Platform | Platform not supported by bot |
| E201 | Search Failed | Try a different search query |
| E202 | No Results Found | No content found for your search |
| E301 | Rate Limited | Wait a few minutes and try again |
| E500 | Internal Error | Bot encountered an unexpected error |

## 🔒 Security & Privacy

### Data Handling
- **No Data Storage**: The bot doesn't store user data or downloaded files permanently
- **Temporary Files**: All downloads are temporary and deleted after sending
- **No Logging of URLs**: User URLs and search queries are not logged

### Recommended Security Practices

1. **Environment Variables**: Always use environment variables for tokens
2. **Token Rotation**: Regularly regenerate your bot token
3. **Access Control**: Consider implementing user whitelisting for private bots
4. **Rate Limiting**: The bot includes built-in rate limiting

### Privacy Considerations
- Only download content you have permission to download
- Respect platform terms of service
- Don't use the bot to download copyrighted material without permission

## 🛠️ Development & Customization

### Project Structure
```
telegram-media-bot/
├── bot.py                 # Main bot application
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables
├── README.md             # This file
├── config/
│   └── gallery-dl.conf   # gallery-dl configuration
└── logs/
    └── bot.log           # Application logs
```

### Adding New Platforms

To add support for a new platform:

1. **Add URL patterns** in `PlatformDetector.PATTERNS`
2. **Implement downloader method** in `UniversalDownloader`
3. **Add error handling** for platform-specific issues
4. **Update documentation**

Example:
```python
# In PlatformDetector.PATTERNS
'youtube': [
    r'youtube\.com/watch\?v=[\w-]+',
    r'youtu\.be/[\w-]+'
]

# In UniversalDownloader
async def _download_youtube(self, url: str):
    # Implementation here
    pass
```

### Custom Error Handling

Add custom error codes in the `ErrorCodes` class:
```python
class ErrorCodes:
    # ... existing codes ...
    CUSTOM_ERROR = "E600"
```

### Testing

Run tests locally:
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

## 📊 Monitoring & Logging

### Log Files
The bot logs important events to help with debugging:

```bash
# View logs
tail -f logs/bot.log

# Search for errors
grep "ERROR" logs/bot.log
```

### Health Monitoring

For production deployment, monitor these metrics:
- Bot response time
- Download success rate
- Error frequency
- Memory usage
- Disk space (for temporary files)

### Telegram Bot Health Check

Create a simple health check endpoint:
```python
async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Health check command for monitoring"""
    await update.message.reply_text("✅ Bot is healthy!")
```

## 🤝 Contributing

### Bug Reports
When reporting bugs, please include:
1. Error code (if any)
2. URL that caused the issue (if safe to share)
3. Platform (Reddit, Instagram, etc.)
4. Bot response/error message

### Feature Requests
Feature requests are welcome! Please check existing issues first.

### Pull Requests
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License. See LICENSE file for details.

## ⚠️ Disclaimer

This bot is for educational purposes. Users are responsible for:
- Complying with platform terms of service
- Respecting copyright laws
- Using downloaded content appropriately

The developers are not responsible for misuse of this software.

## 🆘 Troubleshooting

### Common Issues

#### Bot Not Responding
1. Check if the bot token is correct
2. Verify environment variables are set
3. Check internet connectivity
4. Review logs for errors

#### Downloads Failing
1. Verify `yt-dlp` and `gallery-dl` are installed
2. Check if the URL is accessible in browser
3. Try updating download tools: `pip install -U yt-dlp gallery-dl`
4. Check platform-specific restrictions

#### File Size Errors
1. Check if file exceeds 50MB limit
2. For large files, consider implementing file compression
3. Some platforms may have smaller limits

#### Memory Issues
1. Increase server memory allocation
2. Implement cleanup for temporary files
3. Add file size pre-checking

### Getting Help

1. **Check logs** first: `tail -f logs/bot.log`
2. **Search existing issues** in the repository
3. **Create new issue** with detailed information
4. **Join our community** (if applicable)

## 📚 Additional Resources

### Documentation Links
- [python-telegram-bot Documentation](https://python-telegram-bot.readthedocs.io/)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp#readme)
- [gallery-dl Documentation](https://gallery-dl.readthedocs.io/)
- [Telegram Bot API](https://core.telegram.org/bots/api)

### Useful Tools
- [BotFather](https://t.me/botfather) - Create and manage Telegram bots
- [Telegram Bot API Tester](https://core.telegram.org/bots/api)
- [yt-dlp Supported Sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

**Made with ❤️ for the open-source community**
