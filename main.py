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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
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
    
    SEARCHING = [
        "Me search for you!",
        "Looking for music...",
        "What you want to hear?",
        "Me find good songs!"
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
    """Improved Deezer music downloader with album covers"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        self.arl_token = config.deezer_arl
    
    async def search_tracks(self, query: str, limit: int = 10) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Search for tracks on Deezer"""
        try:
            api_url = "https://api.deezer.com/search"
            params = {
                'q': query,
                'limit': limit,
                'index': 0
            }
            
            response = requests.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('data'):
                return None, "Me found nothing!"
            
            tracks = []
            for track in data['data']:
                tracks.append({
                    'id': track['id'],
                    'title': track['title'],
                    'artist': track['artist']['name'],
                    'album': track['album']['title'],
                    'duration': track['duration'],
                    'preview': track['preview'],
                    'cover_url': track['album']['cover_xl'] or track['album']['cover_big'] or track['album']['cover_medium'],
                    'display': f"{track['artist']['name']} - {track['title']} ({track['album']['title']})"
                })
            
            return tracks, None
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return None, f"Search failed: {str(e)}"
    
    async def download_track_by_id(self, track_id: str, track_info: Dict = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Download specific track by ID with album cover"""
        try:
            output_dir = self.temp_dir / 'deezer'
            output_dir.mkdir(exist_ok=True)
            
            # Get track info if not provided
            if not track_info:
                api_url = f"https://api.deezer.com/track/{track_id}"
                response = requests.get(api_url, timeout=30)
                response.raise_for_status()
                track_info = response.json()
            
            if 'error' in track_info:
                return None, None, "Track not found!"
            
            title = f"{track_info.get('artist', {}).get('name', 'Unknown')} - {track_info.get('title', 'Unknown')}"
            
            # Try full download first if ARL available
            if self.arl_token:
                try:
                    full_file = await self._try_full_download(track_id, track_info, output_dir)
                    if full_file:
                        return full_file, title, None
                except Exception as e:
                    logger.warning(f"Full download failed, trying preview: {e}")
            
            # Fallback to preview with album cover
            return await self._download_preview_with_cover(track_info, output_dir)
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None, None, f"Download failed: {str(e)}"
    
    async def _try_full_download(self, track_id: str, track_info: Dict, output_dir: Path) -> Optional[str]:
        """Try full download using deemix"""
        try:
            track_url = f"https://deezer.com/track/{track_id}"
            
            cmd = [
                'deemix',
                '--bitrate', 'FLAC',
                '--path', str(output_dir),
                '--arl', self.arl_token,
                '--embed-cover',  # Embed album cover
                track_url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            
            if result.returncode == 0:
                # Find downloaded file
                for file in output_dir.glob('**/*'):
                    if file.is_file() and file.suffix.lower() in ['.flac', '.mp3', '.m4a']:
                        return str(file)
            
            return None
            
        except FileNotFoundError:
            logger.info("deemix not installed, using preview")
            return None
        except Exception as e:
            logger.warning(f"Full download failed: {e}")
            return None
    
    async def _download_preview_with_cover(self, track_info: Dict, output_dir: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Download preview and add album cover using mutagen"""
        try:
            preview_url = track_info.get('preview')
            if not preview_url:
                return None, None, "No preview available!"
            
            title = f"{track_info.get('artist', {}).get('name', 'Unknown')} - {track_info.get('title', 'Unknown')}"
            filename = f"{title}.mp3"
            safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            filepath = output_dir / safe_filename
            
            # Download preview
            preview_response = requests.get(preview_url, timeout=30)
            preview_response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(preview_response.content)
            
            # Add album cover and metadata
            await self._add_album_cover_and_metadata(filepath, track_info)
            
            return str(filepath), title, None
            
        except Exception as e:
            logger.error(f"Preview download failed: {e}")
            return None, None, f"Preview download failed: {str(e)}"
    
    async def _add_album_cover_and_metadata(self, audio_path: Path, track_info: Dict):
        """Add album cover and metadata to audio file"""
        try:
            # Try to import mutagen for metadata
            try:
                from mutagen.mp3 import MP3
                from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TDRC
            except ImportError:
                logger.warning("mutagen not installed, skipping metadata")
                return
            
            # Download album cover
            cover_url = track_info.get('album', {}).get('cover_xl') or track_info.get('album', {}).get('cover_big')
            if not cover_url:
                return
            
            cover_response = requests.get(cover_url, timeout=30)
            cover_response.raise_for_status()
            cover_data = cover_response.content
            
            # Add metadata to MP3
            audio = MP3(audio_path, ID3=ID3)
            
            # Add or create ID3 tag
            try:
                audio.add_tags()
            except Exception:
                pass  # Tags might already exist
            
            # Set metadata
            audio.tags[TIT2] = TIT2(encoding=3, text=track_info.get('title', ''))
            audio.tags[TPE1] = TPE1(encoding=3, text=track_info.get('artist', {}).get('name', ''))
            audio.tags[TALB] = TALB(encoding=3, text=track_info.get('album', {}).get('title', ''))
            
            # Add release date if available
            if track_info.get('album', {}).get('release_date'):
                year = track_info['album']['release_date'][:4]
                audio.tags[TDRC] = TDRC(encoding=3, text=year)
            
            # Add album cover
            audio.tags[APIC] = APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,  # Cover (front)
                desc='Cover',
                data=cover_data
            )
            
            audio.save()
            logger.info(f"Added album cover and metadata to {audio_path}")
            
        except Exception as e:
            logger.warning(f"Failed to add album cover: {e}")

    async def download_from_url(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Download music from Deezer URL"""
        if not self.arl_token:
            return None, None, "Me need special key for Deezer work!"
        
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
            
            return await self.download_track_by_id(track_id)
                
        except Exception as e:
            logger.error(f"Deezer download error: {e}")
            return None, None, f"Something wrong with Deezer work! {str(e)}"

class RedditDownloader(BaseDownloader):
    """Enhanced Reddit downloader"""
    
    async def download_media(self, url: str) -> Tuple[Optional[List[str]], Optional[str], Optional[str]]:
        """Download media from Reddit with better error handling"""
        try:
            # Clean up URL and ensure it's in API format
            clean_url = self._clean_reddit_url(url)
            
            # Try multiple approaches for getting Reddit data
            post_data = None
            title = None
            
            # Method 1: Try JSON API
            try:
                api_url = clean_url + '.json'
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(api_url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0 and data[0].get('data', {}).get('children'):
                        post_data = data[0]['data']['children'][0]['data']
                        title = post_data.get('title', 'Reddit Post')
            except Exception as e:
                logger.warning(f"JSON API failed: {e}")
            
            # Method 2: Try using yt-dlp for Reddit (fallback)
            if not post_data:
                try:
                    return await self._download_with_ytdlp(clean_url, "Reddit Post")
                except Exception as e:
                    logger.warning(f"yt-dlp fallback failed: {e}")
            
            # Method 3: If we have post data, process it
            if post_data and title:
                files = []
                
                # Handle different Reddit media types
                if post_data.get('is_video') and post_data.get('secure_media'):
                    # Reddit video
                    reddit_video = post_data['secure_media'].get('reddit_video', {})
                    video_url = reddit_video.get('fallback_url') or reddit_video.get('hls_url')
                    if video_url:
                        file_path = await self._download_file(video_url, 'reddit_video.mp4')
                        if file_path:
                            files.append(file_path)
                
                elif post_data.get('url'):
                    media_url = post_data['url']
                    
                    if any(ext in media_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        # Direct image
                        ext = media_url.split('.')[-1].split('?')[0]
                        file_path = await self._download_file(media_url, f'reddit_image.{ext}')
                        if file_path:
                            files.append(file_path)
                    
                    elif 'v.redd.it' in media_url:
                        # Try to download v.redd.it
                        file_path = await self._download_file(media_url, 'vreddit.mp4')
                        if file_path:
                            files.append(file_path)
                    
                    elif any(domain in media_url for domain in ['imgur.com', 'gfycat.com', 'redgifs.com']):
                        # Use yt-dlp for external media
                        return await self._download_with_ytdlp(media_url, title)
                
                # Handle gallery posts
                if post_data.get('is_gallery') and post_data.get('media_metadata'):
                    gallery_data = post_data.get('gallery_data', {})
                    media_metadata = post_data.get('media_metadata', {})
                    
                    for item in gallery_data.get('items', []):
                        media_id = item.get('media_id')
                        if media_id in media_metadata:
                            media_info = media_metadata[media_id]
                            # Get highest quality image
                            if 's' in media_info:  # Image data
                                resolutions = media_info.get('p', [])
                                if resolutions:
                                    highest_res = max(resolutions, key=lambda x: x.get('x', 0) * x.get('y', 0))
                                    img_url = highest_res['u'].replace('&amp;', '&')
                                    ext = img_url.split('.')[-1].split('?')[0]
                                    file_path = await self._download_file(img_url, f'gallery_{media_id}.{ext}')
                                    if file_path:
                                        files.append(file_path)
                
                if files:
                    return files, title, None
                else:
                    return None, title, "No media found in this post!"
            
            # If all methods failed
            return None, None, "Could not access Reddit post. It might be private or deleted."
                
        except Exception as e:
            logger.error(f"Reddit download error: {e}")
            return None, None, f"Reddit work failed: {str(e)}"
    
    def _clean_reddit_url(self, url: str) -> str:
        """Clean and standardize Reddit URL with better share URL handling"""
        # Remove tracking parameters
        url = url.split('?')[0]
        
        # Handle Reddit share URLs by following redirects first
        if '/s/' in url or 'reddit.app.link' in url or 'redd.it' in url:
            try:
                # Follow redirect to get actual post URL
                response = requests.head(url, allow_redirects=True, timeout=10)
                if response.url and '/comments/' in response.url:
                    url = response.url
            except:
                pass
        
        # Convert various Reddit formats to standard format
        patterns = [
            (r'redd\.it/(\w+)', r'reddit.com/comments/\1'),
            (r'reddit\.app\.link/(\w+)', r'reddit.com/comments/\1'),
            (r'/r/(\w+)/s/(\w+)', r'/r/\1/comments/\2'),  # Share URL pattern
        ]
        
        for pattern, replacement in patterns:
            url = re.sub(pattern, replacement, url)
        
        # Ensure https and remove mobile prefix
        if not url.startswith('http'):
            url = 'https://' + url
        
        # Convert mobile URLs
        url = url.replace('m.reddit.com', 'www.reddit.com')
        url = url.replace('old.reddit.com', 'www.reddit.com')
        
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
🎵 Deezer music (links or search)
📱 Reddit posts 
📸 Instagram media
🎬 TikTok videos

*How to use me:*
• Send any supported link - me download automatically!
• Send music name (like "Metallica Enter Sandman") - me show you options to choose!

*No commands needed - me smart orc!*

*Zug zug!*
        """
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_url_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle any message containing URLs or music search queries"""
        if not update.message or not update.message.text:
            return
            
        message_text = update.message.text.strip()
        
        logger.info(f"Received message: {message_text}")
        
        # Extract URLs from message
        url_pattern = r'https?://[^\s<>"\{\}|\\^`\[\]]+'
        urls = re.findall(url_pattern, message_text)
        
        if urls:
            logger.info(f"Found URLs: {urls}")
            # Handle URLs
            for url in urls:
                platform = PlatformDetector.detect_platform(url)
                
                if not platform:
                    logger.info(f"Platform not detected for: {url}")
                    continue  # Skip unsupported URLs
                
                logger.info(f"Detected platform: {platform}")
                
                # Send working response
                working_response = OrcPeonResponses.get_random('working')
                await update.message.reply_text(f"{working_response} *{platform.title()}* work starting...")
                
                try:
                    if platform == 'deezer':
                        await self._handle_deezer(update, url)
                    else:
                        await self._handle_media(update, url, platform)
                except Exception as e:
                    logger.error(f"Error handling {platform}: {e}")
                    error_response = OrcPeonResponses.get_random('errors')
                    await update.message.reply_text(f"{error_response} {str(e)}")
        else:
            logger.info(f"No URLs found, checking if music search: {message_text}")
            # Check if it's a music search query (no URLs found)
            if len(message_text) > 2 and not message_text.startswith('/'):
                logger.info("Processing as music search")
                await self._handle_music_search(update, message_text)
    
    async def _handle_music_search(self, update: Update, query: str):
        """Handle music search queries"""
        try:
            logger.info(f"Music search for: {query}")
            search_response = OrcPeonResponses.get_random('searching')
            await update.message.reply_text(f"{search_response} Looking for: *{query}*", parse_mode=ParseMode.MARKDOWN)
            
            tracks, error = await self.deezer_downloader.search_tracks(query)
            
            if error:
                logger.error(f"Search error: {error}")
                error_response = OrcPeonResponses.get_random('errors')
                await update.message.reply_text(f"{error_response} {error}")
                return
            
            if not tracks:
                logger.info("No tracks found")
                no_media_response = OrcPeonResponses.get_random('no_media')
                await update.message.reply_text(f"{no_media_response} No music found!")
                return
            
            logger.info(f"Found {len(tracks)} tracks")
            
            # Create inline keyboard with search results
            keyboard = []
            for i, track in enumerate(tracks[:10]):  # Limit to 10 results
                duration_min = track['duration'] // 60
                duration_sec = track['duration'] % 60
                button_text = f"🎵 {track['display']} ({duration_min}:{duration_sec:02d})"
                
                # Truncate if too long
                if len(button_text) > 60:
                    button_text = button_text[:57] + "..."
                
                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f"download_{track['id']}"
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            choose_response = OrcPeonResponses.get_random('choose')
            
            await update.message.reply_text(
                f"{choose_response}\n\n🎵 *Search results for:* {query}",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Music search error: {e}")
            error_response = OrcPeonResponses.get_random('errors')
            await update.message.reply_text(f"{error_response} Search failed: {str(e)}")
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('download_'):
            track_id = query.data.replace('download_', '')
            
            working_response = OrcPeonResponses.get_random('working')
            await query.edit_message_text(f"{working_response} Downloading music...")
            
            try:
                filepath, title, error = await self.deezer_downloader.download_track_by_id(track_id)
                
                if error:
                    error_response = OrcPeonResponses.get_random('errors')
                    await query.edit_message_text(f"{error_response} {error}")
                    return
                
                # Send audio file
                with open(filepath, 'rb') as audio_file:
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=audio_file,
                        caption=f"🎵 *{title}*",
                        parse_mode=ParseMode.MARKDOWN
                    )
                
                success_response = OrcPeonResponses.get_random('success')
                await query.edit_message_text(success_response)
                
            except Exception as e:
                error_response = OrcPeonResponses.get_random('errors')
                await query.edit_message_text(f"{error_response} Failed to send audio!")
                logger.error(f"Error in callback: {e}")
            finally:
                if 'filepath' in locals():
                    await self.deezer_downloader.cleanup_file(filepath)
    
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
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
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
