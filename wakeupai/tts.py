# e:\Dev\WakeUpAI\wakeupai\tts.py
import os
import logging # Added
from openai import OpenAI # Ensure this library is added via Poetry
from wakeupai.config import OPENAI_API_KEY, TTS_VOICE_MODEL, TTS_MAX_DURATION_SECONDS # TTS_MAX_DURATION_SECONDS is for guidance

logger = logging.getLogger(__name__) # Added

# Initialize the OpenAI client globally or within functions as preferred.
if not OPENAI_API_KEY:
    logger.critical("OPENAI_API_KEY not configured for TTS. TTS functionality will not work.")
    client = None 
else:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.debug("OpenAI client initialized successfully for TTS module.")
    except Exception as e:
        logger.critical(f"Failed to initialize OpenAI client for TTS: {e}", exc_info=True)
        client = None

def text_to_speech_openai(text_input: str, output_filepath: str) -> bool:
    """
    Generates speech from the given text using OpenAI's TTS API and saves it to a file.

    Args:
        text_input (str): The text to convert to speech.
        output_filepath (str): The path (including filename, e.g., speech.mp3) to save the audio file.

    Returns:
        bool: True if speech generation was successful and file saved, False otherwise.
    """
    if not client:
        logger.error("OpenAI client is not initialized for TTS. Cannot generate speech.")
        return False

    if not text_input:
        logger.error("No text provided for speech generation.")
        return False

    if not output_filepath:
        logger.error("No output file path provided for saving speech.")
        return False

    try:
        # Ensure the directory for the output file exists
        output_dir = os.path.dirname(output_filepath)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                logger.info(f"Created directory for TTS output: {output_dir}")
            except Exception as e_mkdir:
                logger.error(f"Failed to create directory {output_dir} for TTS output: {e_mkdir}", exc_info=True)
                return False # Cannot save file if dir creation fails

        logger.info(f"Generating speech for text (first 50 chars): '{text_input[:50]}...' to {output_filepath}")
        
        # OpenAI TTS API call
        # Refer to OpenAI documentation for the latest parameters and models.
        # model="tts-1" or "tts-1-hd"
        # voice can be one of "alloy", "echo", "fable", "onyx", "nova", "shimmer"
        response = client.audio.speech.create(
            model="tts-1",      # Standard quality, good for most cases. "tts-1-hd" for higher quality.
            voice=TTS_VOICE_MODEL, # From config.py, e.g., "alloy"
            input=text_input,
        # response_format="mp3" is default, others include opus, aac, flac
        )

        # Stream the audio to the file
        response.stream_to_file(output_filepath)
        logger.info(f"Speech successfully generated and saved to {output_filepath}")
        return True

    except Exception as e:
        logger.error(f"Error during OpenAI TTS generation or saving to {output_filepath}: {e}", exc_info=True)
        # Clean up partially created file if an error occurs
        if os.path.exists(output_filepath):
            try:
                os.remove(output_filepath)
                logger.debug(f"Removed partially created TTS file: {output_filepath}")
            except Exception as remove_e:
                logger.error(f"Could not remove partially created TTS file {output_filepath}: {remove_e}", exc_info=True)
        return False

if __name__ == '__main__':
    # Setup basic logging for the __main__ test if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG, 
            format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger.info("Basic logging configured for tts.py direct test run.")

    logger.info("--- TTS Module Test ---")
    if not OPENAI_API_KEY or not client:
        logger.warning("OpenAI API key not configured or client not initialized. Cannot run TTS test.")
    else:
        logger.info(f"Using TTS Voice Model: {TTS_VOICE_MODEL}")
        sample_text = "Hello, this is a test of the WakeUpAI text-to-speech system using OpenAI."
        
        test_output_dir = os.path.join(os.path.dirname(__file__), "..", "test_audio_output") # TEMP_AUDIO_DIR from alarm_handler might be better
        if not os.path.exists(test_output_dir):
            try:
                os.makedirs(test_output_dir)
                logger.info(f"Created directory for TTS test output: {test_output_dir}")
            except Exception as e_mkdir_test:
                logger.error(f"Could not create test output directory {test_output_dir}: {e_mkdir_test}", exc_info=True)
                test_output_dir = "." 
        
        test_filename = "tts_direct_test_output.mp3"
        full_output_path = os.path.join(test_output_dir, test_filename)
        
        logger.info(f"Attempting to save speech to: {full_output_path}")
        
        success = text_to_speech_openai(sample_text, full_output_path)
        
        if success:
            logger.info(f"TTS test successful. Audio saved to {full_output_path}")
        else:
            logger.error("TTS test failed.")
    logger.info("--- TTS Module Test Complete ---")
