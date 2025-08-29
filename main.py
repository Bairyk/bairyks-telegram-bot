#!/usr/bin/env python3
"""
Multi-Platform Media Downloader Telegram Bot with Orc Peon Personality
Supports: Deezer, Reddit, Instagram, TikTok
"""

import os
import sys
import asyncio
import logging
import tempfile
import subprocess
import random
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import json
import re
from urllib.parse import urlparse, unquote
import requests
from datetime import datetime

import telegram
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
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

class OrcPeonResponses:
    """Orc Peon personality responses"""
    
    READY = [
        "Ready to work.",
        "Work, work.",
        "Something need doing?",
        "What you want?"
    ]
    
    WORKING = [
        "I can do that.",
        "Be happy to.",
        "Work, work.",
        "Okie dokie.",
        "Me busy, leave me alone!",
        "Dabu! (Yes!)"
    ]
    
    SUCCESS = [
        "Job's done!",
        "Work complete!",
        "Task finished!",
        "Me finished!",
        "Something else need doing?"
    ]
    
    ERRORS = [
        "Whaaat?",
        "Me busy. Leave me alone!!",
        "No time for play.",
        "Me not that kind of orc!",
        "Something wrong!",
        "Me can't do that!",
        "Zug zug... problem!",
        "Work not complete!"
    ]
    
    NO_MEDIA = [
        "No work here!",
        "Nothing to do!",
        "Me see no task!",
        "What you want me do with this?"
    ]
    
    @classmethod
    def get_random(cls, response_type: str) -> str:
        responses = getattr(cls, response_type.upper(), cls.READY)
        return random.choice(responses)

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
            r'deezer\.com/(?:\w+/)?track/(\d+)',
            r'deezer\.com/(?:\w+/)?album/(\d+)',
            r'deezer\.com/(?:\w+/)?playlist/(\d+)',
            r'deezer\.page\.link/[\w-]+',
            r'deezer\.app\.goo\.gl/[\w-]+'
        ],
        'reddit': [
            # Standard Reddit post URLs
            r'(?:https?://)?(?:www\.)?reddit\.com/r/[\w\d_]+/comments/[\w\d]+(?:/[^?\s]*)?(?:\?[^\s]*)?',
            r'(?:https?://)?old\.reddit\.com/r/[\w\d_]+/comments/[\w\d]+(?:/[^?\s]*)?(?:\?[^\s]*)?',
            r'(?:https?://)?new\.reddit\.com/r/[\w\d_]+/comments/[\w\d]+(?:/[^?\s]*)?(?:\?[^\s]*)?',
            r'(?:https?://)?(?:m\.)?reddit\.com/r/[\w\d_]+/comments/[\w\d]+(?:/[^?\s]*)?(?:\?[^\s]*)?',
            
            # Short URLs
            r'(?:https?://)?redd\.it/[\w\d]+',
            r'(?:https?://)?reddit\.app\.link/[\w\d]+',
            
            # Share URLs
            r'(?:https?://)?(?:www\.)?reddit\.com/r/[\w\d_]+/s/[\w\d]+',
            
            # Gallery URLs
            r'(?:https?://)?(?:www\.)?reddit\.com/gallery/[\w\d]+',
            
            # Video URLs
            r'(?:https?://)?v\.redd\.it/[\w\d]+',
            r'(?:https?://)?(?:www\.)?reddit\.com/r/[\w\d_]+/comments/[\w\d]+/.*\.(?:mp4|gif|gifv)',
            
            # Media URLs
            r'(?:https?://)?i\.redd\.it/[\w\d]+\.(?:jpg|jpeg|png|gif|webp)',
            r'(?:https?://)?preview\.redd\.it/[\w\d]+\.(?:jpg|jpeg|png|gif|webp)',
            
            # Mobile URLs
            r'(?:https?://)?(?:www\.)?reddit\.com/r/[\w\d_]+/comments/[\w\d]+\.json',
        ],
        'instagram': [
            r'instagram\.com/p/[\w-]+',
            r'instagram\.com/reel/[\w-]+',
            r'instagram\.com/tv/[\w-]+',
            r'instagr\.am/p/[\w-]+',
            r'instagram\.com/stories/[\w.-]+/\d+',
            r'ig\.me/[\w-]+'
        ],
        'tiktok': [
            r'tiktok\.com/@[\w.-]+/video/\d+',
            r'vm\.tiktok\.com/[\w-]+',
            r'tiktok\.com/t/[\w-]+',
            r'm\.tiktok\.com/v/\d+\.html',
            r'tiktok\.com/.*\?.*v=\d+',
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
    """Improved Deezer music downloader"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.arl_token = config.deezer_arl
    
    async def download_from_url(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Download music from Deezer URL"""
        if not self.arl_token:
            return None, None, f"Me need special key for Deezer work!"
        
        try:
            # Extract track ID from URL
            track_id = None
            patterns = [
                r'deezer\.com/(?:\w+/)?track/(\d+)',
                r'deezer\.com/(?:\w+/)?album/(\d+)',
                r'deezer\.com/(?:\w+/)?playlist/(\d+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    track_id = match.group(1)
                    break
            
            if not track_id:
                return None, None, "Me can't find track in URL!"
            
            # Try to download using deemix or similar tool
            output_dir = self.temp_dir / 'deezer'
            output_dir.mkdir(exist_ok=True)
            
            # Use deemix if available, otherwise fallback to API + preview
            cmd = [
                'deemix',
                '--bitrate', 'FLAC',  # Try for highest quality
                '--path', str(output_dir),
                '--arl', self.arl_token,
                url
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    # Find downloaded file
                    for file in output_dir.glob('**/*'):
                        if file.is_file() and file.suffix.lower() in ['.flac', '.mp3', '.m4a']:
                            title = file.stem
                            return str(file), title, None
                else:
                    # Fallback to preview download
                    return await self._download_preview(track_id, output_dir)
                    
            except FileNotFoundError:
                # deemix not installed, use preview
                return await self._download_preview(track_id, output_dir)
                
        except Exception as e:
            logger.error(f"Deezer download error: {e}")
            return None, None, f"Something wrong with Deezer work! {str(e)}"
    
    async def _download_preview(self, track_id: str, output_dir: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Download preview version"""
        try:
            # Get track info from Deezer API
            api_url = f"https://api.deezer.com/track/{track_id}"
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            track_data = response.json()
            
            if 'error' in track_data:
                return None, None, "Track not found on Deezer!"
            
            preview_url = track_data.get('preview')
            if not preview_url:
                return None, None, "No preview available!"
            
            title = f"{track_data.get('artist', {}).get('name', 'Unknown')} - {track_data.get('title', 'Unknown')}"
            filename = f"{title}.mp3"
            safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            filepath = output_dir / safe_filename
            
            # Download preview
            preview_response = requests.get(preview_url, timeout=30)
            preview_response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(preview_response.content)
            
            return str(filepath), title, None
            
        except Exception as e:
            return None, None, f"Preview download failed: {str(e)}"

class RedditDownloader(BaseDownloader):
    """Enhanced Reddit downloader"""
    
    async def download_media(self, url: str) -> Tuple[Optional[List[str]], Optional[str], Optional[str]]:
        """Download media from Reddit with better handling"""
        try:
            # Clean up URL and ensure it's in API format
            clean_url = self._clean_reddit_url(url)
            api_url = clean_url.replace('reddit.com', 'reddit.com') + '.json'
            
            # Get post data
            headers = {
                'User-Agent': 'MediaDownloaderBot/1.0'
            }
            
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                post_data = data[0]['data']['children'][0]['data']
            else:
                return None, None, "Can't find post data!"
            
            title = post_data.get('title', 'Reddit Post')
            files = []
            
            # Handle different Reddit media types
            if post_data.get('is_video'):
                # Reddit video
                video_url = post_data.get('secure_media', {}).get('reddit_video', {}).get('fallback_url')
                if video_url:
                    file_path = await self._download_file(video_url, 'reddit_video.mp4')
                    if file_path:
                        files.append(file_path)
            
            elif post_data.get('url'):
                url = post_data['url']
                
                if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    # Direct image
                    ext = url.split('.')[-1].split('?')[0]
                    file_path = await self._download_file(url, f'reddit_image.{ext}')
                    if file_path:
                        files.append(file_path)
                
                elif 'v.redd.it' in url:
                    # v.redd.it video
                    return await self._download_vreddit(url)
                
                elif 'imgur' in url:
                    # Imgur content
                    return await self._handle_imgur(url)
                
                elif 'gfycat' in url or 'redgifs' in url:
                    # Use yt-dlp for these
                    return await self._download_with_ytdlp(url, title)
            
            # Handle gallery posts
            if post_data.get('is_gallery'):
                gallery_data = post_data.get('gallery_data', {})
                media_metadata = post_data.get('media_metadata', {})
                
                for item in gallery_data.get('items', []):
                    media_id = item['media_id']
                    if media_id in media_metadata:
                        # Get highest quality image
                        resolutions = media_metadata[media_id].get('p', [])
                        if resolutions:
                            highest_res = max(resolutions, key=lambda x: x.get('x', 0) * x.get('y', 0))
                            img_url = highest_res['u'].replace('&amp;', '&')
                            ext = img_url.split('.')[-1].split('?')[0]
                            file_path = await self._download_file(img_url, f'reddit_gallery_{media_id}.{ext}')
                            if file_path:
                                files.append(file_path)
            
            if files:
                return files, title, None
            else:
                return None, title, "No media found in this post!"
                
        except Exception as e:
            logger.error(f"Reddit download error: {e}")
            return None, None, f"Reddit work failed: {str(e)}"
    
    def _clean_reddit_url(self, url: str) -> str:
        """Clean and standardize Reddit URL"""
        # Remove tracking parameters
        url = url.split('?')[0]
        
        # Convert various Reddit formats to standard format
        patterns = [
            (r'redd\.it/(\w+)', r'reddit.com/comments/\1'),
            (r'reddit\.app\.link/(\w+)', r'reddit.com/comments/\1'),
            (r'/s/(\w+)', r'/comments/\1'),
        ]
        
        for pattern, replacement in patterns:
            url = re.sub(pattern, replacement, url)
        
        # Ensure https
        if not url.startswith('http'):
            url = 'https://' + url
        
        return url
    
    async def _download_file(self, url: str, filename: str) -> Optional[str]:
        """Download a single file"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            filepath = self.temp_dir / 'reddit' / filename
            filepath.parent.mkdir(exist_ok=True)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            if filepath.stat().st_size > self.config.max_file_size:
                await self.cleanup_file(str(filepath))
                return None
            
            return str(filepath)
            
        except Exception as e:
            logger.error(f"File download failed: {e}")
            return None
    
    async def _download_with_ytdlp(self, url: str, title: str) -> Tuple[Optional[List[str]], Optional[str], Optional[str]]:
        """Use yt-dlp for complex Reddit media"""
        output_dir = self.temp_dir / 'reddit'
        output_dir.mkdir(exist_ok=True)
        
        cmd = [
            'yt-dlp',
            '--no-playlist',
            '--max-filesize', f'{self.config.max_file_size}',
            '-o', str(output_dir / '%(title)s.%(ext)s'),
            '--merge-output-format', 'mp4',
            url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                files = []
                for file in output_dir.glob('*'):
                    if file.is_file() and file.suffix.lower() in ['.mp4', '.webm', '.mkv', '.jpg', '.png', '.gif']:
                        files.append(str(file))
                
                if files:
                    return files, title, None
            
            return None, title, "yt-dlp download failed"
            
        except Exception as e:
            return None, title, f"yt-dlp error: {str(e)}"

class UniversalDownloader(BaseDownloader):
    """Universal downloader with better Reddit support"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.reddit_downloader = RedditDownloader(config)
    
    async def download_media(self, url: str) -> Tuple[Optional[List[str]], Optional[str], Optional[str]]:
        """Download media from supported platforms"""
        platform = PlatformDetector.detect_platform(url)
        
        if not platform:
            return None, None, "Me don't know this place!"
        
        try:
            if platform == 'reddit':
                return await self.reddit_downloader.download_media(url)
            elif platform in ['tiktok', 'instagram']:
                return await self._download_with_ytdlp(url, platform)
            else:
                return None, None, f"Me can't work with {platform}!"
        
        except Exception as e:
            logger.error(f"Download error for {url}: {e}")
            return None, None, f"Work failed: {str(e)}"
    
    async def _download_with_ytdlp(self, url: str, platform: str) -> Tuple[Optional[List[str]], Optional[str], Optional[str]]:
        """Download using yt-dlp with better format selection"""
        output_dir = self.temp_dir / platform
        output_dir.mkdir(exist_ok=True)
        
        cmd = [
            'yt-dlp',
            '--no-playlist',
            '--max-filesize', f'{self.config.max_file_size}',
            '-o', str(output_dir / '%(title)s.%(ext)s'),
            '--write-info-json',
            '--format', 'best[ext=mp4]/best',  # Prefer mp4
            '--merge-output-format', 'mp4',
            url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                files = []
                title = None
                
                # Find downloaded files and extract title
                for file in output_dir.glob('*'):
                    if file.suffix == '.json':
                        try:
                            with open(file, 'r') as f:
                                info = json.load(f)
                                title = info.get('title', file.stem)
                        except:
                            pass
                    elif file.suffix.lower() in ['.mp4', '.webm', '.mkv', '.jpg', '.png', '.gif']:
                        files.append(str(file))
                
                if files:
                    return files, title or "Downloaded Media", None
                else:
                    return None, None, "No media files found"
            else:
                error_msg = result.stderr.lower()
                if 'private' in error_msg or 'not available' in error_msg:
                    return None, None, "Content is private or not available!"
                else:
                    return None, None, f"Download failed: {result.stderr[:100]}"
                    
        except subprocess.TimeoutExpired:
            return None, None, "Download took too long!"
        except FileNotFoundError:
            return None, None, "yt-dlp not installed!"

class MediaDownloaderBot:
    """Main bot class with Orc Peon personality"""
    
    def __init__(self):
        self.config = Config()
        self.deezer_downloader = DeezerDownloader(self.config)
        self.universal_downloader = UniversalDownloader(self.config)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        response = OrcPeonResponses.get_random('ready')
        welcome_text = f"""
{response}

*Me can work with:*
🎵 Deezer music
📱 Reddit posts 
📸 Instagram media
🎬 TikTok videos

*Just send me link and me do work!*
No need for commands - me smart orc!

*Zug zug!*
        """
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_url_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle any message containing URLs - auto-detect and download"""
        message_text = update.message.text
        
        # Extract URLs from message
        url_pattern = r'https?://[^\s<>"\{\}|\\^`\[\]]+'
        urls = re.findall(url_pattern, message_text)
        
        if not urls:
            # Check if it's a search query (if no URLs found)
            return
        
        for url in urls:
            platform = PlatformDetector.detect_platform(url)
            
            if not platform:
                continue  # Skip unsupported URLs
            
            # Send working response
            working_response = OrcPeonResponses.get_random('working')
            await update.message.reply_text(f"{working_response} *{platform.title()}* work starting...")
            
            try:
                if platform == 'deezer':
                    await self._handle_deezer(update, url)
                else:
                    await self._handle_media(update, url, platform)
            except Exception as e:
                error_response = OrcPeonResponses.get_random('errors')
                await update.message.reply_text(f"{error_response} {str(e)}")
    
    async def _handle_deezer(self, update: Update, url: str):
        """Handle Deezer downloads"""
        filepath, title, error = await self.deezer_downloader.download_from_url(url)
        
        if error:
            error_response = OrcPeonResponses.get_random('errors')
            await update.message.reply_text(f"{error_response} {error}")
            return
        
        try:
            with open(filepath, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    caption=f"🎵 *{title}*\n{url}",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            success_response = OrcPeonResponses.get_random('success')
            await update.message.reply_text(success_response)
            
        except Exception as e:
            error_response = OrcPeonResponses.get_random('errors')
            await update.message.reply_text(f"{error_response} Failed to send audio!")
        finally:
            await self.deezer_downloader.cleanup_file(filepath)
    
    async def _handle_media(self, update: Update, url: str, platform: str):
        """Handle other media downloads"""
        filepaths, title, error = await self.universal_downloader.download_media(url)
        
        if error:
            if "No media found" in error or "No work here" in error:
                no_media_response = OrcPeonResponses.get_random('no_media')
                await update.message.reply_text(f"{no_media_response} {error}")
            else:
                error_response = OrcPeonResponses.get_random('errors')
                await update.message.reply_text(f"{error_response} {error}")
            return
        
        if not filepaths:
            no_media_response = OrcPeonResponses.get_random('no_media')
            await update.message.reply_text(no_media_response)
            return
        
        try:
            # Send media files
            for filepath in filepaths:
                file_ext = Path(filepath).suffix.lower()
                
                with open(filepath, 'rb') as media_file:
                    if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        await update.message.reply_photo(
                            photo=media_file,
                            caption=f"📸 *{title}*\n{url}" if len(filepaths) == 1 else None,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    elif file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                        await update.message.reply_video(
                            video=media_file,
                            caption=f"🎬 *{title}*\n{url}" if len(filepaths) == 1 else None,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    elif file_ext in ['.mp3', '.m4a', '.wav']:
                        await update.message.reply_audio(
                            audio=media_file,
                            caption=f"🎵 *{title}*\n{url}" if len(filepaths) == 1 else None,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    else:
                        filename = Path(filepath).name
                        await update.message.reply_document(
                            document=media_file,
                            filename=filename,
                            caption=f"📎 *{title}*\n{url}" if len(filepaths) == 1 else None,
                            parse_mode=ParseMode.MARKDOWN
                        )
            
            # Send title and link in separate message if multiple files
            if len(filepaths) > 1:
                await update.message.reply_text(
                    f"📎 *{title}*\n{url}",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            success_response = OrcPeonResponses.get_random('success')
            await update.message.reply_text(success_response)
            
        except Exception as e:
            logger.error(f"Error sending media: {e}")
            error_response = OrcPeonResponses.get_random('errors')
            await update.message.reply_text(f"{error_response} Failed to send files!")
        finally:
            # Cleanup all files
            for filepath in filepaths:
                await self.universal_downloader.cleanup_file(filepath)
    
    def run(self):
        """Run the bot"""
        application = Application.builder().token(self.config.bot_token).build()
        
        # Add handlers - only start command and URL detection
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r'https?://'), 
            self.handle_url_message
        ))
        
        logger.info("Peon bot ready for work! Zug zug!")
        
        # Run the bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Main function"""
    try:
        bot = MediaDownloaderBot()
        bot.run()
    except Exception as e:
        logger.error(f"Peon can't start work: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
