#!/usr/bin/env python3
"""
Test suite for Telegram Media Downloader Bot
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Import bot modules
from bot import (
    Config, 
    PlatformDetector, 
    DeezerDownloader,
    UniversalDownloader,
    MediaDownloaderBot,
    ErrorCodes
)

@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    config = Config()
    config.bot_token = "test_token"
    config.deezer_arl = "test_arl"
    config.max_file_size = 1024 * 1024  # 1MB for testing
    config.temp_dir = Path(tempfile.gettempdir()) / 'test_bot'
    config.temp_dir.mkdir(exist_ok=True)
    return config

class TestPlatformDetector:
    """Test platform detection functionality"""
    
    def test_detect_deezer_urls(self):
        """Test Deezer URL detection"""
        test_urls = [
            ("https://deezer.com/track/123456", "deezer"),
            ("https://www.deezer.com/album/789", "deezer"),
            ("https://deezer.com/playlist/456", "deezer"),
            ("https://example.com/music", None),
        ]
        
        for url, expected in test_urls:
            result = PlatformDetector.detect_platform(url)
            assert result == expected, f"Failed for URL: {url}"
    
    def test_detect_reddit_urls(self):
        """Test Reddit URL detection"""
        test_urls = [
            ("https://reddit.com/r/videos/comments/abc123/title/", "reddit"),
            ("https://old.reddit.com/r/funny/comments/xyz/", "reddit"),
            ("https://redd.it/abc123", "reddit"),
            ("https://example.com/reddit", None),
        ]
        
        for url, expected in test_urls:
            result = PlatformDetector.detect_platform(url)
            assert result == expected, f"Failed for URL: {url}"
    
    def test_detect_instagram_urls(self):
        """Test Instagram URL detection"""
        test_urls = [
            ("https://instagram.com/p/ABC123/", "instagram"),
            ("https://www.instagram.com/reel/XYZ789/", "instagram"),
            ("https://instagr.am/p/DEF456/", "instagram"),
            ("https://example.com/insta", None),
        ]
        
        for url, expected in test_urls:
            result = PlatformDetector.detect_platform(url)
            assert result == expected, f"Failed for URL: {url}"
    
    def test_detect_tiktok_urls(self):
        """Test TikTok URL detection"""
        test_urls = [
            ("https://tiktok.com/@user/video/123456789", "tiktok"),
            ("https://vm.tiktok.com/ABC123/", "tiktok"),
            ("https://tiktok.com/t/XYZ789/", "tiktok"),
            ("https://example.com/tiktok", None),
        ]
        
        for url, expected in test_urls:
            result = PlatformDetector.detect_platform(url)
            assert result == expected, f"Failed for URL: {url}"

class TestDeezerDownloader:
    """Test Deezer downloader functionality"""
    
    @pytest.mark.asyncio
    async def test_search_without_arl(self, mock_config):
        """Test search fails without ARL token"""
        mock_config.deezer_arl = None
        downloader = DeezerDownloader(mock_config)
        
        filepath, error = await downloader.search_and_download("test song")
        
        assert filepath is None
        assert ErrorCodes.AUTHENTICATION_FAILED in error
    
    @pytest.mark.asyncio
    async def test_cleanup_file(self, mock_config):
        """Test file cleanup functionality"""
        downloader = DeezerDownloader(mock_config)
        
        # Create a temporary file
        test_file = mock_config.temp_dir / "test_file.mp3"
        test_file.write_text("test content")
        
        assert test_file.exists()
        await downloader.cleanup_file(str(test_file))
        assert not test_file.exists()

class TestUniversalDownloader:
    """Test universal downloader functionality"""
    
    @pytest.mark.asyncio
    async def test_unsupported_url(self, mock_config):
        """Test handling of unsupported URLs"""
        downloader = UniversalDownloader(mock_config)
        
        filepath, error = await downloader.download_media("https://example.com/unsupported")
        
        assert filepath is None
        assert ErrorCodes.UNSUPPORTED_PLATFORM in error
    
    @pytest.mark.asyncio
    @patch('subprocess.run')
    async def test_ytdlp_download_success(self, mock_subprocess, mock_config):
        """Test successful yt-dlp download"""
        downloader = UniversalDownloader(mock_config)
        
        # Mock successful subprocess call
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stderr = ""
        
        # Create a fake downloaded file
        output_dir = mock_config.temp_dir / 'reddit'
        output_dir.mkdir(exist_ok=True)
        fake_file = output_dir / 'test_video.mp4'
        fake_file.write_text("fake video content")
        
        filepath, error = await downloader._download_with_ytdlp(
            "https://reddit.com/r/videos/comments/test/", "reddit"
        )
        
        assert error is None
        assert filepath is not None
        assert Path(filepath).exists()
        
        # Cleanup
        await downloader.cleanup_file(filepath)
    
    @pytest.mark.asyncio
    @patch('subprocess.run')
    async def test_ytdlp_download_failure(self, mock_subprocess, mock_config):
        """Test yt-dlp download failure"""
        downloader = UniversalDownloader(mock_config)
        
        # Mock failed subprocess call
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Download failed: Video not available"
        
        filepath, error = await downloader._download_with_ytdlp(
            "https://reddit.com/r/videos/comments/test/", "reddit"
        )
        
        assert filepath is None
        assert ErrorCodes.DOWNLOAD_FAILED in error

class TestMediaDownloaderBot:
    """Test main bot functionality"""
    
    @pytest.fixture
    def mock_bot(self, mock_config):
        """Create a mock bot instance"""
        with patch.object(Config, '__init__', return_value=None):
            bot = MediaDownloaderBot()
            bot.config = mock_config
            bot.deezer_downloader = Mock()
            bot.universal_downloader = Mock()
            return bot
    
    @pytest.mark.asyncio
    async def test_start_command(self, mock_bot):
        """Test /start command"""
        # Mock update and context
        update = Mock()
        update.message.reply_text = AsyncMock()
        context = Mock()
        
        await mock_bot.start_command(update, context)
        
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "Multi-Platform Media Downloader Bot" in call_args
    
    @pytest.mark.asyncio
    async def test_search_command_no_args(self, mock_bot):
        """Test /search command without arguments"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        context = Mock()
        context.args = []
        
        await mock_bot.search_command(update, context)
        
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert ErrorCodes.INVALID_URL in call_args
    
    @pytest.mark.asyncio
    async def test_download_command_no_args(self, mock_bot):
        """Test /download command without arguments"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        context = Mock()
        context.args = []
        
        await mock_bot.download_command(update, context)
        
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert ErrorCodes.INVALID_URL in call_args
    
    @pytest.mark.asyncio
    async def test_download_command_unsupported_url(self, mock_bot):
        """Test /download command with unsupported URL"""
        update = Mock()
        update.message.reply_text = AsyncMock()
        context = Mock()
        context.args = ["https://example.com/unsupported"]
        
        await mock_bot.download_command(update, context)
        
        # Should be called twice: once for unsupported platform
        assert update.message.reply_text.call_count == 1
        call_args = update.message.reply_text.call_args[0][0]
        assert ErrorCodes.UNSUPPORTED_PLATFORM in call_args

class TestErrorHandling:
    """Test error handling functionality"""
    
    def test_error_codes_exist(self):
        """Test that all error codes are defined"""
        required_codes = [
            'INVALID_URL', 'AUTHENTICATION_FAILED', 'DOWNLOAD_FAILED',
            'FILE_TOO_LARGE', 'UNSUPPORTED_PLATFORM', 'SEARCH_FAILED',
            'NO_RESULTS_FOUND', 'RATE_LIMITED', 'INTERNAL_ERROR'
        ]
        
        for code in required_codes:
            assert hasattr(ErrorCodes, code), f"Missing error code: {code}"
            assert getattr(ErrorCodes, code).startswith('E'), f"Invalid error code format: {code}"

@pytest.mark.integration
class TestIntegration:
    """Integration tests (require external dependencies)"""
    
    @pytest.mark.asyncio
    async def test_full_workflow_reddit(self, mock_config):
        """Test full workflow for Reddit URL (requires yt-dlp)"""
        downloader = UniversalDownloader(mock_config)
        
        # This test requires yt-dlp to be installed
        try:
            import subprocess
            result = subprocess.run(['yt-dlp', '--version'], capture_output=True)
            if result.returncode != 0:
                pytest.skip("yt-dlp not available")
        except FileNotFoundError:
            pytest.skip("yt-dlp not installed")
        
        # Test with a known working Reddit URL (you may need to update this)
        test_url = "https://www.reddit.com/r/PublicFreakout/comments/example/"
        
        filepath, error = await downloader.download_media(test_url)
        
        # This might fail due to the URL being fake, but it tests the integration
        if filepath:
            assert Path(filepath).exists()
            await downloader.cleanup_file(filepath)

def test_environment_variables():
    """Test environment variable handling"""
    # Test with missing bot token
    original_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if 'TELEGRAM_BOT_TOKEN' in os.environ:
        del os.environ['TELEGRAM_BOT_TOKEN']
    
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Config()
    
    # Restore original token if it existed
    if original_token:
        os.environ['TELEGRAM_BOT_TOKEN'] = original_token

if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
