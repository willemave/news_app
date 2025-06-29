import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.services.openai_llm import OpenAITranscriptionService, MAX_FILE_SIZE_BYTES, CHUNK_DURATION_SECONDS


class TestOpenAITranscriptionService:
    """Test cases for OpenAITranscriptionService."""
    
    def test_init_no_api_key(self):
        """Test initialization without API key."""
        with patch("app.services.openai_llm.get_settings") as mock_get_settings:
            with patch("app.services.openai_llm.logger"):
                mock_settings = MagicMock(spec=["database_url"])  # No openai_api_key attribute
                mock_get_settings.return_value = mock_settings
                
                with pytest.raises(ValueError, match="OpenAI API key is required"):
                    OpenAITranscriptionService()
    
    @patch("app.services.openai_llm.OpenAI")
    @patch("app.services.openai_llm.get_settings")
    def test_get_audio_format(self, mock_get_settings, mock_openai):
        """Test audio format detection."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test-key"
        mock_get_settings.return_value = mock_settings
        
        service = OpenAITranscriptionService()
        
        assert service._get_audio_format(Path("test.mp3")) == "mp3"
        assert service._get_audio_format(Path("test.m4a")) == "mp4"
        assert service._get_audio_format(Path("test.wav")) == "wav"
        assert service._get_audio_format(Path("test.unknown")) == "mp3"  # default
    
    @patch("app.services.openai_llm.OpenAI")
    @patch("app.services.openai_llm.get_settings")
    def test_get_transcription_prompt(self, mock_get_settings, mock_openai):
        """Test prompt generation based on filename."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test-key"
        mock_get_settings.return_value = mock_settings
        
        service = OpenAITranscriptionService()
        
        # Test different filename patterns
        prompt = service._get_transcription_prompt(Path("interview-with-expert.mp3"))
        assert "interview" in prompt.lower()
        
        prompt = service._get_transcription_prompt(Path("tech-news-ai.mp3"))
        assert "technology" in prompt.lower()
        
        prompt = service._get_transcription_prompt(Path("bg2-episode-123.mp3"))
        assert "Bill Gurley" in prompt
        assert "Brad Gerstner" in prompt
        
        prompt = service._get_transcription_prompt(Path("random-podcast.mp3"))
        assert "podcast episode" in prompt
    
    @patch("app.services.openai_llm.os.path.getsize")
    @patch("app.services.openai_llm.OpenAI")
    @patch("app.services.openai_llm.get_settings")
    def test_check_file_size(self, mock_get_settings, mock_openai, mock_getsize):
        """Test file size checking."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test-key"
        mock_get_settings.return_value = mock_settings
        
        service = OpenAITranscriptionService()
        
        # Test file under limit
        mock_getsize.return_value = MAX_FILE_SIZE_BYTES - 1
        assert service._check_file_size(Path("test.mp3")) is True
        
        # Test file at limit
        mock_getsize.return_value = MAX_FILE_SIZE_BYTES
        assert service._check_file_size(Path("test.mp3")) is True
        
        # Test file over limit
        mock_getsize.return_value = MAX_FILE_SIZE_BYTES + 1
        assert service._check_file_size(Path("test.mp3")) is False
    
    @patch("app.services.openai_llm.subprocess.run")
    @patch("app.services.openai_llm.OpenAI")
    @patch("app.services.openai_llm.get_settings")
    def test_check_ffmpeg_available(self, mock_get_settings, mock_openai, mock_subprocess):
        """Test ffmpeg availability check."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test-key"
        mock_get_settings.return_value = mock_settings
        
        service = OpenAITranscriptionService()
        
        # Test when ffmpeg is available
        mock_subprocess.return_value = MagicMock(returncode=0)
        assert service._check_ffmpeg_available() is True
        
        # Test when ffmpeg is not available
        mock_subprocess.side_effect = FileNotFoundError()
        assert service._check_ffmpeg_available() is False
        
        # Test when ffmpeg returns error
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "ffmpeg")
        assert service._check_ffmpeg_available() is False
    
    @patch("app.services.openai_llm.subprocess.run")
    @patch("app.services.openai_llm.os.path.getsize")
    @patch("app.services.openai_llm.OpenAI")
    @patch("app.services.openai_llm.get_settings")
    def test_get_audio_duration(self, mock_get_settings, mock_openai, mock_getsize, mock_subprocess):
        """Test audio duration detection."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test-key"
        mock_get_settings.return_value = mock_settings
        
        service = OpenAITranscriptionService()
        
        # Test successful ffprobe
        mock_result = MagicMock()
        mock_result.stdout = "1800.5"
        mock_subprocess.return_value = mock_result
        
        duration = service._get_audio_duration(Path("test.mp3"))
        assert duration == 1800.5
        
        # Test ffprobe failure - fallback to estimation
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "ffprobe")
        mock_getsize.return_value = 30 * 1024 * 1024  # 30MB
        
        duration = service._get_audio_duration(Path("test.mp3"))
        assert duration == 30 * 60  # Estimated duration
    
    @patch("app.services.openai_llm.os.path.getsize")
    @patch("app.services.openai_llm.Path.exists")
    @patch("app.services.openai_llm.subprocess.run")
    @patch("app.services.openai_llm.tempfile.mkdtemp")
    @patch("app.services.openai_llm.OpenAI")
    @patch("app.services.openai_llm.get_settings")
    def test_split_audio_file_ffmpeg(self, mock_get_settings, mock_openai, mock_mkdtemp, 
                                     mock_subprocess, mock_exists, mock_getsize):
        """Test audio file splitting with ffmpeg."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test-key"
        mock_get_settings.return_value = mock_settings
        
        service = OpenAITranscriptionService()
        
        # Mock audio duration of 25 minutes
        duration_result = MagicMock()
        duration_result.stdout = "1500"  # 25 minutes
        
        # Mock successful ffmpeg split commands
        split_result = MagicMock()
        split_result.returncode = 0
        
        # Return different results for ffprobe and ffmpeg
        def subprocess_side_effect(*args, **kwargs):
            if "ffprobe" in args[0]:
                return duration_result
            else:
                return split_result
        
        mock_subprocess.side_effect = subprocess_side_effect
        mock_mkdtemp.return_value = "/tmp/audio_chunks_123"
        mock_exists.return_value = True
        mock_getsize.return_value = 10 * 1024 * 1024  # 10MB chunks
        
        # Execute
        chunks = service._split_audio_file_ffmpeg(Path("test.mp3"))
        
        # Should create 3 chunks (10 min, 10 min, 5 min)
        assert len(chunks) == 3
        assert all(str(chunk).startswith("/tmp/audio_chunks_123") for chunk in chunks)
        
        # Verify ffmpeg was called 3 times (after the initial ffprobe)
        assert mock_subprocess.call_count == 4  # 1 ffprobe + 3 ffmpeg
    
    @patch("app.services.openai_llm.os.path.getsize")
    @patch("app.services.openai_llm.OpenAI")
    @patch("app.services.openai_llm.get_settings")
    def test_transcribe_audio_small_file(self, mock_get_settings, mock_openai, mock_getsize):
        """Test transcription of small file (no splitting needed)."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test-key"
        mock_get_settings.return_value = mock_settings
        
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_transcription = MagicMock()
        mock_transcription.text = "This is the transcribed text"
        mock_transcription.language = "en"
        mock_client.audio.transcriptions.create.return_value = mock_transcription
        mock_openai.return_value = mock_client
        
        service = OpenAITranscriptionService()
        
        # Mock small file
        mock_getsize.return_value = 10 * 1024 * 1024  # 10MB
        
        # Execute
        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            transcript, language = service.transcribe_audio(Path("test.mp3"))
        
        # Assertions
        assert transcript == "This is the transcribed text"
        assert language == "en"
        mock_client.audio.transcriptions.create.assert_called_once()
    
    @patch("app.services.openai_llm.subprocess.run")
    @patch("app.services.openai_llm.os.path.getsize")
    @patch("app.services.openai_llm.OpenAI")
    @patch("app.services.openai_llm.get_settings")
    def test_transcribe_audio_large_file_no_ffmpeg(self, mock_get_settings, mock_openai, 
                                                   mock_getsize, mock_subprocess):
        """Test transcription of large file when ffmpeg is not available."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test-key"
        mock_get_settings.return_value = mock_settings
        
        service = OpenAITranscriptionService()
        
        # Mock large file
        mock_getsize.return_value = 30 * 1024 * 1024  # 30MB
        
        # Mock ffmpeg not available
        mock_subprocess.side_effect = FileNotFoundError()
        
        # Execute and expect error
        with pytest.raises(RuntimeError, match="ffmpeg is not available"):
            service.transcribe_audio(Path("test.mp3"))