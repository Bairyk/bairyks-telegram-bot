#!/usr/bin/env python3
"""
Multi-Platform Media Downloader Telegram Bot
Supports: Deezer, Reddit, Instagram, TikTok
"""

import os
import sys
import asyncio
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import json
import re
from urllib.parse import urlparse

import telegram
from telegram import Update, InlineQueryResultAudio, InlineQueryResultVideo, InlineQueryResultPhoto
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    InlineQueryHandler,
    ContextTypes, 
    filters
)
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ErrorCodes:
    """Centralized error codes for the bot"""
    INVALID_URL = "E101"
    AUTHENTICATION_FAILED = "E102" 
    DOWNLOAD_FAILED = "E103"
    FILE_TOO_LARGE = "E104"
    UNSUPPORTED_PLATFORM = "E105"
    SEARCH_FAILED = "E201"
    NO_RESULTS_FOUND = "E202"
    RATE_LIMITED = "E301"
    INTERNAL_ERROR = "E500"

class Config:
    """Bot configuration"""
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.deezer_arl = os.getenv('DEEZER_ARL')
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.temp_dir = Path(tempfile.gettempdir()) / 'telegram_bot'
        self.temp_dir.mkdir(exist_ok=True)
        
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

class PlatformDetector:
    """Detects which platform a URL belongs to"""
    
    PATTERNS = {
        'deezer': [
            r'deezer\.com/track/(\d+)',
            r'deezer\.com/album/(\d+)',
            r'deezer\.com/playlist/(\d+)'
        ],
        'reddit': [
            r'reddit\.com/r/\w+/comments/\w+',
            r'redd\.it/\w+',
            r'old\.reddit\.com/r/\w+/comments/\w+'
            r'reddit\.com/r/\w+/s/\w+'  # Add this line for share URLs
        ],
        'instagram': [
            r'instagram\.com/p/[\w-]+',
            r'instagram\.com/reel/[\w-]+',
            r'instagr\.am/p/[\w-]+'
        ],
        'tiktok': [
            r'tiktok\.com/@[\w.-]+/video/\d+',
            r'vm\.tiktok\.com/[\w-]+',
            r'tiktok\.com/t/[\w-]+'
        ]
    }
    
    @classmethod
    def detect_platform(cls, url: str) -> Optional[str]:
        """Detect platform from URL"""
        for platform, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return platform
        return None

class BaseDownloader:
    """Base class for all downloaders"""
    
    def __init__(self, config: Config):
        self.config = config
        self.temp_dir = config.temp_dir
    
    async def cleanup_file(self, filepath: str):
        """Clean up temporary files"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.warning(f"Failed to cleanup file {filepath}: {e}")

class DeezerDownloader(BaseDownloader):
    """Deezer music downloader using deezloader-remix"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.arl_token = config.deezer_arl
    
    async def search_and_download(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Search and download music from Deezer"""
        if not self.arl_token:
            return None, f"{ErrorCodes.AUTHENTICATION_FAILED}: Deezer ARL token not configured"
        
        try:
            # Use deezloader-remix via subprocess
            output_dir = self.temp_dir / 'deezer'
            output_dir.mkdir(exist_ok=True)
            
            # Create a temporary config for deezloader
            config_data = {
                "userDefined": {
                    "downloadLocation": str(output_dir),
                    "tracknameTemplate": "%artist% - %title%",
                    "albumTracknameTemplate": "%artist% - %title%",
                    "playlistTracknameTemplate": "%artist% - %title%"
                },
                "spotify": {},
                "deezer": {"arl": self.arl_token}
            }
            
            config_file = output_dir / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
            
            # Search for the track using a simple approach
            # This is a simplified implementation - in production, you'd use proper API calls
            cmd = [
                sys.executable, '-c',
                f"""
import requests
import json

# Search Deezer public API
search_url = 'https://api.deezer.com/search'
params = {{'q': '{query}', 'limit': 1}}
response = requests.get(search_url, params=params)
data = response.json()

if data.get('data'):
    track = data['data'][0]
    print(json.dumps({{
        'id': track['id'],
        'title': track['title'],
        'artist': track['artist']['name'],
        'preview': track['preview']
    }}))
else:
    print('null')
"""
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0 or result.stdout.strip() == 'null':
                return None, f"{ErrorCodes.NO_RESULTS_FOUND}: No tracks found for '{query}'"
            
            track_info = json.loads(result.stdout.strip())
            
            # Download the preview (since full downloads require premium authentication)
            import requests
            preview_url = track_info['preview']
            if not preview_url:
                return None, f"{ErrorCodes.DOWNLOAD_FAILED}: No preview available"
            
            filename = f"{track_info['artist']} - {track_info['title']}.mp3"
            safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            filepath = output_dir / safe_filename
            
            response = requests.get(preview_url, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            if filepath.stat().st_size > self.config.max_file_size:
                await self.cleanup_file(str(filepath))
                return None, f"{ErrorCodes.FILE_TOO_LARGE}: File exceeds 50MB limit"
            
            return str(filepath), None
            
        except subprocess.TimeoutExpired:
            return None, f"{ErrorCodes.RATE_LIMITED}: Search timeout"
        except Exception as e:
            logger.error(f"Deezer download error: {e}")
            return None, f"{ErrorCodes.INTERNAL_ERROR}: {str(e)}"

class UniversalDownloader(BaseDownloader):
    """Universal downloader using yt-dlp and gallery-dl"""
    
    def __init__(self, config: Config):
        super().__init__(config)
    
    async def download_media(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download media from supported platforms"""
        platform = PlatformDetector.detect_platform(url)
        
        if not platform:
            return None, f"{ErrorCodes.UNSUPPORTED_PLATFORM}: URL not supported"
        
        try:
            if platform in ['reddit', 'tiktok']:
                return await self._download_with_ytdlp(url, platform)
            elif platform == 'instagram':
                return await self._download_with_gallery_dl(url)
            else:
                return None, f"{ErrorCodes.UNSUPPORTED_PLATFORM}: {platform} not supported for URL downloads"
        
        except Exception as e:
            logger.error(f"Download error for {url}: {e}")
            return None, f"{ErrorCodes.INTERNAL_ERROR}: {str(e)}"
    
    async def _download_with_ytdlp(self, url: str, platform: str) -> Tuple[Optional[str], Optional[str]]:
        """Download using yt-dlp"""
        output_dir = self.temp_dir / platform
        output_dir.mkdir(exist_ok=True)
        
        # Configure yt-dlp options
        cmd = [
            'yt-dlp',
            '--no-playlist',
            '--max-filesize', f'{self.config.max_file_size}',
            '-o', str(output_dir / '%(title)s.%(ext)s'),
            '--write-info-json',
            '--no-write-playlist-metafiles',
            url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                error_msg = result.stderr.lower()
                if 'file is larger than max-filesize' in error_msg:
                    return None, f"{ErrorCodes.FILE_TOO_LARGE}: File exceeds size limit"
                elif 'unable to download' in error_msg or 'not available' in error_msg:
                    return None, f"{ErrorCodes.DOWNLOAD_FAILED}: Content not available or private"
                else:
                    return None, f"{ErrorCodes.DOWNLOAD_FAILED}: {result.stderr[:100]}"
            
            # Find downloaded file
            for file in output_dir.glob('*'):
                if file.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.mp3', '.m4a', '.jpg', '.png', '.gif']:
                    return str(file), None
            
            return None, f"{ErrorCodes.DOWNLOAD_FAILED}: No media file found after download"
            
        except subprocess.TimeoutExpired:
            return None, f"{ErrorCodes.RATE_LIMITED}: Download timeout"
        except FileNotFoundError:
            return None, f"{ErrorCodes.INTERNAL_ERROR}: yt-dlp not installed"
    
    async def _download_with_gallery_dl(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Download using gallery-dl for Instagram"""
        output_dir = self.temp_dir / 'instagram'
        output_dir.mkdir(exist_ok=True)
        
        cmd = [
            'gallery-dl',
            '--dest', str(output_dir),
            '--filename', '{category}_{id}.{extension}',
            '--no-part',
            url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                if 'login required' in result.stderr.lower():
                    return None, f"{ErrorCodes.AUTHENTICATION_FAILED}: Instagram login required for this content"
                elif 'not found' in result.stderr.lower():
                    return None, f"{ErrorCodes.DOWNLOAD_FAILED}: Content not found or private"
                else:
                    return None, f"{ErrorCodes.DOWNLOAD_FAILED}: {result.stderr[:100]}"
            
            # Find downloaded file
            for file in output_dir.rglob('*'):
                if file.is_file() and file.suffix.lower() in ['.jpg', '.png', '.mp4', '.gif']:
                    if file.stat().st_size > self.config.max_file_size:
                        await self.cleanup_file(str(file))
                        return None, f"{ErrorCodes.FILE_TOO_LARGE}: File exceeds 50MB limit"
                    return str(file), None
            
            return None, f"{ErrorCodes.DOWNLOAD_FAILED}: No media file found"
            
        except subprocess.TimeoutExpired:
            return None, f"{ErrorCodes.RATE_LIMITED}: Download timeout"
        except FileNotFoundError:
            return None, f"{ErrorCodes.INTERNAL_ERROR}: gallery-dl not installed"

class MediaDownloaderBot:
    """Main bot class"""
    
    def __init__(self):
        self.config = Config()
        self.deezer_downloader = DeezerDownloader(self.config)
        self.universal_downloader = UniversalDownloader(self.config)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_text = """
🎵 *Multi-Platform Media Downloader Bot* 🎵

*Commands:*
• `/search <song name>` - Search and download music from Deezer
• `/download <url>` - Download media from Reddit, Instagram, TikTok

*Supported Platforms:*
🎵 Deezer (music search & preview download)
📱 Reddit (videos, images, gifs)  
📸 Instagram (posts, reels)
🎬 TikTok (videos)

*Note:* Some platforms may require the content to be public. File size limit: 50MB.

You can also use me in inline mode by typing `@YourBotName query`
        """
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        if not context.args:
            await update.message.reply_text(
                f"{ErrorCodes.INVALID_URL}: Please provide a search query.\n"
                "Usage: `/search song name - artist`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        query = ' '.join(context.args)
        await update.message.reply_text(f"🔍 Searching for: *{query}*...", parse_mode=ParseMode.MARKDOWN)
        
        filepath, error = await self.deezer_downloader.search_and_download(query)
        
        if error:
            await update.message.reply_text(f"❌ {error}")
            return
        
        try:
            with open(filepath, 'rb') as audio_file:
                filename = Path(filepath).name
                await update.message.reply_audio(
                    audio=audio_file,
                    filename=filename,
                    caption=f"🎵 Found: {filename}"
                )
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            await update.message.reply_text(f"❌ {ErrorCodes.INTERNAL_ERROR}: Failed to send audio file")
        finally:
            await self.deezer_downloader.cleanup_file(filepath)
    
    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /download command"""
        if not context.args:
            await update.message.reply_text(
                f"{ErrorCodes.INVALID_URL}: Please provide a URL.\n"
                "Usage: `/download <url>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        url = context.args[0]
        platform = PlatformDetector.detect_platform(url)
        
        if not platform:
            await update.message.reply_text(f"❌ {ErrorCodes.UNSUPPORTED_PLATFORM}: URL not supported")
            return
        
        await update.message.reply_text(f"📥 Downloading from *{platform.title()}*...", parse_mode=ParseMode.MARKDOWN)
        
        filepath, error = await self.universal_downloader.download_media(url)
        
        if error:
            await update.message.reply_text(f"❌ {error}")
            return
        
        try:
            file_ext = Path(filepath).suffix.lower()
            
            with open(filepath, 'rb') as media_file:
                filename = Path(filepath).name
                
                if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
                    await update.message.reply_photo(
                        photo=media_file,
                        caption=f"📸 Downloaded from {platform.title()}"
                    )
                elif file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                    await update.message.reply_video(
                        video=media_file,
                        caption=f"🎬 Downloaded from {platform.title()}"
                    )
                elif file_ext in ['.mp3', '.m4a', '.wav']:
                    await update.message.reply_audio(
                        audio=media_file,
                        caption=f"🎵 Downloaded from {platform.title()}"
                    )
                else:
                    await update.message.reply_document(
                        document=media_file,
                        filename=filename,
                        caption=f"📎 Downloaded from {platform.title()}"
                    )
                    
        except Exception as e:
            logger.error(f"Error sending media: {e}")
            await update.message.reply_text(f"❌ {ErrorCodes.INTERNAL_ERROR}: Failed to send media file")
        finally:
            await self.universal_downloader.cleanup_file(filepath)
    
    async def inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline queries"""
        query = update.inline_query.query.strip()
        
        if not query:
            return
        
        if query.startswith('http'):
            # URL download
            platform = PlatformDetector.detect_platform(query)
            if platform:
                results = [
                    telegram.InlineQueryResultArticle(
                        id='download_url',
                        title=f"Download from {platform.title()}",
                        description=f"Click to download media from {query}",
                        input_message_content=telegram.InputTextMessageContent(
                            message_text=f"/download {query}"
                        )
                    )
                ]
            else:
                results = [
                    telegram.InlineQueryResultArticle(
                        id='unsupported_url',
                        title="Unsupported URL",
                        description="This URL is not supported",
                        input_message_content=telegram.InputTextMessageContent(
                            message_text=f"❌ {ErrorCodes.UNSUPPORTED_PLATFORM}: URL not supported"
                        )
                    )
                ]
        else:
            # Music search
            results = [
                telegram.InlineQueryResultArticle(
                    id='search_music',
                    title=f"Search: {query}",
                    description="Search for music on Deezer",
                    input_message_content=telegram.InputTextMessageContent(
                        message_text=f"/search {query}"
                    )
                )
            ]
        
        await update.inline_query.answer(results, cache_time=0)
    
    async def handle_url_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle direct URL messages"""
        message_text = update.message.text
        
        # Extract URLs from message
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, message_text)
        
        if urls:
            url = urls[0]  # Process first URL
            platform = PlatformDetector.detect_platform(url)
            
            if platform:
                # Auto-download
                await update.message.reply_text(f"🔍 Detected {platform.title()} URL. Downloading...")
                
                filepath, error = await self.universal_downloader.download_media(url)
                
                if error:
                    await update.message.reply_text(f"❌ {error}")
                    return
                
                try:
                    file_ext = Path(filepath).suffix.lower()
                    
                    with open(filepath, 'rb') as media_file:
                        if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
                            await update.message.reply_photo(
                                photo=media_file,
                                caption=f"📸 Auto-downloaded from {platform.title()}"
                            )
                        elif file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                            await update.message.reply_video(
                                video=media_file,
                                caption=f"🎬 Auto-downloaded from {platform.title()}"
                            )
                        else:
                            await update.message.reply_document(
                                document=media_file,
                                caption=f"📎 Auto-downloaded from {platform.title()}"
                            )
                            
                except Exception as e:
                    logger.error(f"Error sending auto-downloaded media: {e}")
                    await update.message.reply_text(f"❌ {ErrorCodes.INTERNAL_ERROR}: Failed to send file")
                finally:
                    await self.universal_downloader.cleanup_file(filepath)
    
    def run(self):
        """Run the bot"""
        application = Application.builder().token(self.config.bot_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("search", self.search_command))
        application.add_handler(CommandHandler("download", self.download_command))
        application.add_handler(InlineQueryHandler(self.inline_query))
        application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'https?://'), self.handle_url_message))
        
        logger.info("Bot started successfully!")
        
        # Run the bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Main function"""
    try:
        bot = MediaDownloaderBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
