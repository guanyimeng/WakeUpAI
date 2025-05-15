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
            model="gpt-4o-mini-tts",      # Standard quality, good for most cases. "tts-1-hd" for higher quality.
            voice=TTS_VOICE_MODEL, # From config.py, e.g., "alloy"
            input=text_input,
            instructions="Speak in the tone and style of Ron Burgundy from the movie Anchorman or an anchorman or newscaster from the 1980s, with a hint of energy and humor"
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
        sample_text = "Good morning, San Diego! I'm Ron Burgundy, and here's what's happening in our world today, May 14, 2025.\n\n**1. Markets on a Roller Coaster Ride**\n\nGlobal markets have been on a wild ride lately, but there's a glimmer of hope. After six weeks of tariff turmoil, U.S. stocks are back in the green for the year. Tech giants like Nvidia and AMD are leading the charge, thanks to massive AI deals in the Middle East. Nvidia's stock soared, pushing its valuation to a staggering $3 trillion. That's trillion with a 'T'! ([reuters.com](https://www.reuters.com/markets/europe/global-markets-view-europe-2025-05-14/?utm_source=openai))\n\n**2. Trade Talks Heating Up**\n\nPresident Trump is hinting at direct negotiations with China's President Xi Jinping to hammer out a trade deal. Meanwhile, potential agreements with India, Japan, and South Korea are still in the pipeline. It's like a high-stakes game of international poker, and everyone's waiting to see who blinks first. ([reuters.com](https://www.reuters.com/markets/europe/global-markets-view-europe-2025-05-14/?utm_source=openai))\n\n**3. Tech Stocks Take a Tumble**\n\nAfter riding high on the AI boom, tech stocks are facing a reality check. Market uncertainty and questions about the future of artificial intelligence have led to a significant drop in stock prices for major tech companies. It's a reminder that what goes up must come down—unless you're a helium balloon, of course. ([drydenwire.com](https://drydenwire.com/news/morning-headlines-friday-mar-14-2025/?utm_source=openai))\n\n**4. American Airlines Emergency Landing**\n\nAn American Airlines flight made an emergency landing at Denver International Airport after an engine issue caused a fire. Passengers had to evacuate using emergency slides, and 12 people were taken to the hospital with minor injuries. Talk about a flight to remember! ([drydenwire.com](https://drydenwire.com/news/morning-headlines-friday-mar-14-2025/?utm_source=openai))\n\n**5. Newsmax Settles Defamation Suit**\n\nNewsmax Media has paid $40 million to settle allegations that it defamed Smartmatic by reporting false claims about the 2020 U.S. election. It's a hefty price tag for spreading misinformation—perhaps a lesson in thinking before you speak. ([drydenwire.com](https://drydenwire.com/news/morning-headlines-friday-mar-14-2025/?utm_source=openai))\n\n**And now, a quick look at the weather:**\n\nIn sunny San Diego, it's currently 67°F (19°C) and, you guessed it, sunny. Today's high will be 69°F (21°C) with a low of 56°F (13°C). Perfect weather for a beach day or, if you're like me, a scotch on the rocks.\n\nStay classy, San Diego."

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
