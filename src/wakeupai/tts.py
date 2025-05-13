import os
import logging 
from openai import OpenAI # Ensure this library is added via Poetry
from ..config import OPENAI_API_KEY, TTS_VOICE_MODEL, TTS_MAX_DURATION_SECONDS # TTS_MAX_DURATION_SECONDS is for guidance

logger = logging.getLogger(__name__)

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

# Generate TTS
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

# =============================================================================================================================
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
        sample_text = "Good morning! Here are today's top news stories:\n\n**1. President Trump Begins Middle East Tour in Saudi Arabia**\n\nPresident Donald Trump has commenced a four-day visit to the Middle East, starting in Saudi Arabia. The agenda includes discussions on Iran's nuclear program, the Gaza conflict, and bolstering U.S.-Saudi business ties, with potential Saudi investments in the U.S. estimated at up to $600 billion. Trump's envoy, Steve Witkoff, is also engaging with families of hostages in Israel, following the recent release of American-Israeli hostage Edan Alexander. ([apnews.com](https://apnews.com/article/26f9104dd733e07136ff255c6917d66f?utm_source=openai))\n\n**2. EPA Announces Major Deregulation Efforts**\n\nThe Environmental Protection Agency has initiated the largest deregulation action in U.S. history, aiming to roll back numerous water and air quality regulations and defund billions allocated to green energy initiatives. This move includes reconsidering the \"endangerment finding,\" which classifies greenhouse gases as a public health threat. EPA Administrator Lee Zeldin stated, \"Today, the green new scam ends.\" ([democracynow.org](https://www.democracynow.org/2025/3/13/headlines?utm_source=openai))\n\n**3. Russia Reclaims Territory Amid Ceasefire Talks**\n\nRussian forces have recaptured nearly 90% of the territory in the Kursk region that was previously seized by Ukraine. This development comes as U.S. special envoy Steve Witkoff arrives in Moscow for ceasefire negotiations. Russia has presented demands including Ukraine's non-membership in NATO and international recognition of Crimea and other regions as Russian territory. ([democracynow.org](https://www.democracynow.org/2025/3/13/headlines?utm_source=openai))\n\n**4. Record-Breaking Tornado Outbreak in the U.S.**\n\nBetween March 13 and 16, the United States experienced a historic tornado outbreak, with 117 tornadoes reported across the Midwest and Eastern regions. This event is the largest on record for March, resulting in 43 fatalities and over 247 injuries. The outbreak caused significant damage and power outages affecting more than 670,000 residents. ([en.wikipedia.org](https://en.wikipedia.org/wiki/Tornado_outbreak_of_March_13%E2%80%9316%2C_2025?utm_source=openai))\n\n**5. Stock Market Update**\n\nAs of 1:31 PM UTC, the S&P 500 (SPY) is trading at $583.10, up 0.02% from the previous close. The Dow Jones Industrial Average (DIA) stands at $422.69, down 0.36%, while the Nasdaq-100 (QQQ) is at $508.84, up 0.20%. In the tech sector, Apple Inc. (AAPL) is trading at $211.18, up 0.19%, Microsoft Corp. (MSFT) at $446.30, down 0.66%, and Alphabet Inc. (GOOGL) at $158.13, down 0.21%.\n\nStay informed and have a great day!"
        
        test_output_dir = os.path.join("test_output/test_audio_output") # TEMP_AUDIO_DIR from alarm_handler might be better
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
