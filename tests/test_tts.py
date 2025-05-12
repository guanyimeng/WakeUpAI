# e:\Dev\WakeUpAI\tests\test_tts.py
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import logging
import shutil # For cleaning up test directories

from wakeupai.tts import text_to_speech_openai, client as tts_openai_client # Import the client directly for patching
from wakeupai import tts # To modify tts.client for testing initialization failure
from wakeupai.config import TTS_VOICE_MODEL

TEST_TTS_OUTPUT_DIR = "test_tts_temp_output"

class TestTTSModule(unittest.TestCase):
    """Tests for the tts.py module."""

    def setUp(self):
        # Create a temporary directory for TTS output files during tests
        if not os.path.exists(TEST_TTS_OUTPUT_DIR):
            os.makedirs(TEST_TTS_OUTPUT_DIR)
        # Suppress most logging unless specifically testing for it
        logging.disable(logging.DEBUG) 
        self.original_tts_client = tts.client # Store original client from tts module

    def tearDown(self):
        # Remove the temporary directory and its contents after tests
        if os.path.exists(TEST_TTS_OUTPUT_DIR):
            shutil.rmtree(TEST_TTS_OUTPUT_DIR)
        logging.disable(logging.NOTSET) # Re-enable logging
        tts.client = self.original_tts_client # Restore original client

    def test_tts_client_not_initialized(self):
        """Test text_to_speech_openai returns False if client is None."""
        original_client = tts.client
        tts.client = None # Force client to be None
        
        output_file = os.path.join(TEST_TTS_OUTPUT_DIR, "no_client_test.mp3")
        result = text_to_speech_openai("Hello", output_file)
        self.assertFalse(result)
        self.assertFalse(os.path.exists(output_file))
        
        tts.client = original_client # Restore

    def test_tts_no_text_input(self):
        """Test with no text input."""
        output_file = os.path.join(TEST_TTS_OUTPUT_DIR, "no_text.mp3")
        result = text_to_speech_openai("", output_file)
        self.assertFalse(result)
        self.assertFalse(os.path.exists(output_file))

    def test_tts_no_output_filepath(self):
        """Test with no output filepath."""
        result = text_to_speech_openai("Some text", "")
        self.assertFalse(result)

    @patch('wakeupai.tts.client.audio.speech.create')
    def test_tts_successful_generation(self, mock_speech_create):
        """Test successful speech generation and file saving."""
        # Ensure the client is mocked if it was None initially due to no API key
        if tts.client is None: 
            tts.client = MagicMock()
            # If client was None, mock_speech_create would not be on tts.client.audio.speech
            # so we re-patch it directly on the mocked client if needed for this test path.
            # This is a bit complex due to global client init. A better way is to inject client.
            tts.client.audio.speech.create = mock_speech_create 

        mock_response = MagicMock()
        # stream_to_file is a method on the response object returned by speech.create()
        mock_response.stream_to_file = MagicMock()
        mock_speech_create.return_value = mock_response

        text_input = "Hello, world! This is a test."
        output_file = os.path.join(TEST_TTS_OUTPUT_DIR, "success.mp3")

        with patch('os.path.exists') as mock_path_exists, \
             patch('os.makedirs') as mock_makedirs: 
            mock_path_exists.side_effect = lambda path: False # Simulate dir doesn't exist initially
            
            result = text_to_speech_openai(text_input, output_file)

            self.assertTrue(result)
            mock_speech_create.assert_called_once_with(
                model="tts-1", 
                voice=TTS_VOICE_MODEL,
                input=text_input
            )
            mock_response.stream_to_file.assert_called_once_with(output_file)
            mock_makedirs.assert_called_once_with(TEST_TTS_OUTPUT_DIR) # Check if dir creation was attempted

    @patch('wakeupai.tts.client.audio.speech.create')
    def test_tts_api_error(self, mock_speech_create):
        """Test handling of OpenAI API error during speech generation."""
        if tts.client is None: tts.client = MagicMock(); tts.client.audio.speech.create = mock_speech_create

        mock_speech_create.side_effect = Exception("OpenAI API Error")
        
        text_input = "This will fail."
        output_file = os.path.join(TEST_TTS_OUTPUT_DIR, "api_error.mp3")
        
        # Ensure the file doesn't exist before the call
        if os.path.exists(output_file): os.remove(output_file)

        result = text_to_speech_openai(text_input, output_file)

        self.assertFalse(result)
        # Test that a partially created file would be removed (if stream_to_file was mocked to create one first)
        # For this test, as stream_to_file is not called on error, we just check it doesn't exist.
        self.assertFalse(os.path.exists(output_file), "Output file should not exist after API error if not created, or be removed if partially created.")

    @patch('wakeupai.tts.client.audio.speech.create')
    @patch('os.remove') # Mock os.remove to check its called
    def test_tts_cleanup_on_streaming_error(self, mock_os_remove, mock_speech_create):
        """Test that a partially created file is removed if stream_to_file fails."""
        if tts.client is None: tts.client = MagicMock(); tts.client.audio.speech.create = mock_speech_create
        
        mock_response = MagicMock()
        mock_response.stream_to_file.side_effect = Exception("Streaming Error")
        mock_speech_create.return_value = mock_response
        
        text_input = "Streaming failure test."
        output_file = os.path.join(TEST_TTS_OUTPUT_DIR, "streaming_error.mp3")

        # Simulate the file exists (as if stream_to_file created it before failing)
        with patch('os.path.exists', return_value=True):
            result = text_to_speech_openai(text_input, output_file)
        
        self.assertFalse(result)
        mock_os_remove.assert_called_once_with(output_file)

    @patch('wakeupai.tts.client.audio.speech.create')
    def test_tts_directory_creation_failure(self, mock_speech_create):
        """Test TTS failure if output directory cannot be created."""
        if tts.client is None: tts.client = MagicMock(); tts.client.audio.speech.create = mock_speech_create
        
        text_input = "Dir creation fail test."
        # Path to a non-existent directory that we will mock as uncreatable
        uncreatable_dir = os.path.join(TEST_TTS_OUTPUT_DIR, "uncreatable_subdir")
        output_file = os.path.join(uncreatable_dir, "test.mp3")

        with patch('os.path.exists', return_value=False) as mock_path_exists, \
             patch('os.makedirs', side_effect=OSError("Permission denied")) as mock_makedirs:
            
            result = text_to_speech_openai(text_input, output_file)
            
            self.assertFalse(result)
            mock_path_exists.assert_called_with(uncreatable_dir) # Check that existence of dir was checked
            mock_makedirs.assert_called_once_with(uncreatable_dir) # Check that dir creation was attempted
            mock_speech_create.assert_not_called() # API call should not happen if dir fails

if __name__ == '__main__':
    unittest.main()
