import os
import tempfile
import time
import datetime
import logging

from .alarm import Alarm # For type hinting
from ..wakeupai.feeds import generate_feed_content
from ..wakeupai.tts import text_to_speech_openai
from ..hardware.audio_player import play_audio_file
from ..config import OPENAI_API_KEY, TTS_VOICE_MODEL # To check if core services are available

logger = logging.getLogger(__name__)

# This directory will store the temporary audio files for alarms.
# It should be writable by the application.
# Using a subdirectory within the project for simplicity, ensure it exists or is created.
TEMP_AUDIO_DIR = os.path.join("src/audio_files/temp_alarm_audio")
if not os.path.exists(TEMP_AUDIO_DIR):
    try:
        os.makedirs(TEMP_AUDIO_DIR)
        logger.info(f"Created temporary audio directory: {TEMP_AUDIO_DIR}")
    except Exception as e:
        logger.critical(f"Could not create temporary audio directory {TEMP_AUDIO_DIR}: {e}", exc_info=True)
        # Fallback to system temp if project-local fails, though this might have permission issues too
        TEMP_AUDIO_DIR = tempfile.gettempdir()
        logger.warning(f"Using system temp directory as fallback for temp audio: {TEMP_AUDIO_DIR}")

def process_single_triggered_alarm(alarm: Alarm, system_is_enabled: bool = True):
    """
    Processes a single alarm that has been identified as needing to trigger.
    This involves generating the feed, converting to speech, and playing it.

    Args:
        alarm (Alarm): The alarm object that has triggered.
        system_is_enabled (bool): If the overall system (e.g. hardware switch) is enabled.
                                  If False, the alarm sound might be suppressed.
    """
    logger.info(f"--- Processing Triggered Alarm --- ID: {alarm.alarm_id}, Label: '{alarm.label}' at {alarm.alarm_time.strftime('%H:%M')}")

    if not system_is_enabled:
        logger.info(f"Alarm '{alarm.label}' triggered, but system is currently disabled. Sound will not play.")
        # Even if system is disabled, the alarm object itself (e.g. one-time) might still be updated by AlarmManager
        return

    if not OPENAI_API_KEY:
        logger.error("OpenAI API key not configured. Cannot generate feed or speech for alarm '{alarm.label}'.")
        # Play a default sound here if desired
        play_audio_file("src/audio_files/default_alarm_sound.mp3") 
        return

    # 1. Generate Feed Content
    logger.info(f"Generating feed content for '{alarm.label}' (Type: {alarm.feed_type}, Options: {alarm.feed_options})")
    feed_text = generate_feed_content(feed_type=alarm.feed_type, options=alarm.feed_options)

    if not feed_text:
        logger.warning(f"Failed to generate feed content for '{alarm.label}'. Playing a generic sound or silence.")
        # Play a default sound here if desired
        play_audio_file("src/audio_files/default_alarm_sound.mp3") 
        return

    logger.debug(f"Feed content for '{alarm.label}' (first 80 chars): '{feed_text[:80]}...'")

    # 2. Generate Speech (TTS)
    # Create a unique filename for the temporary audio output
    # Using alarm_id and timestamp to ensure uniqueness and aid debugging
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize alarm.label for filename, or just use alarm_id for simplicity
    safe_label_part = "".join(c if c.isalnum() else '_' for c in alarm.label[:20])
    temp_audio_filename = f"alarm_{alarm.alarm_id}_{safe_label_part}_{timestamp_str}.mp3"
    temp_audio_filepath = os.path.join(TEMP_AUDIO_DIR, temp_audio_filename)

    logger.info(f"Generating speech for '{alarm.label}' to file: {temp_audio_filepath}")
    tts_success = text_to_speech_openai(text_input=feed_text, output_filepath=temp_audio_filepath)

    if not tts_success:
        logger.warning(f"Failed to generate speech for '{alarm.label}'. Playing a generic sound or silence.")
        # Play a default sound here if desired
        play_audio_file("src/audio_files/default_alarm_sound.mp3") 
        return

    # 3. Play Audio
    logger.info(f"Playing alarm audio for '{alarm.label}': {temp_audio_filepath}")
    # Playback should be blocking for a single alarm sound.
    # If multiple alarms trigger simultaneously, this sequential processing means they play one after another.
    playback_success = play_audio_file(temp_audio_filepath, wait_for_completion=True)

    if not playback_success:
        logger.warning(f"Failed to play audio for '{alarm.label}' (File: {temp_audio_filepath}). Player might have logged more details.")

    # 4. Cleanup Temporary Audio File
    # try:
    #     if os.path.exists(temp_audio_filepath):
    #         os.remove(temp_audio_filepath)
    #         logger.debug(f"Cleaned up temporary audio file: {temp_audio_filepath}")
    # except Exception as e:
    #     logger.error(f"Error cleaning up temporary audio file {temp_audio_filepath}: {e}", exc_info=True)
    
    # logger.info(f"--- Finished processing alarm: '{alarm.label}' ---")

# =============================================================================================================================
if __name__ == '__main__':
    print("--- Alarm Handler Test ---")

    # We need a mock Alarm object and a way to test this.
    # This requires OPENAI_API_KEY to be set in .env for full testing.

    class MockAlarm(Alarm):
        def __init__(self, alarm_id, label, feed_type="daily_news", feed_options=None, enabled=True):
            super().__init__(
                alarm_time=datetime.datetime.now().time(), 
                label=label, 
                alarm_id=alarm_id, 
                feed_type=feed_type, 
                feed_options=feed_options or {},
                enabled=enabled
            )
            # Ensure should_trigger and other necessary methods are available if called
            self.is_snoozing = False
            self.snooze_until_datetime = None
    
    # Setup basic logging for the __main__ test if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG, 
            format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger.info("Basic logging configured for alarm_handler.py direct test run.")

    logger.info("To run a full test of process_single_triggered_alarm, ensure:")
    logger.info("  1. OPENAI_API_KEY is set in your .env file.")
    logger.info("  2. Your internet connection is active.")
    logger.info("  3. (If on Pi) mpg123 is installed for audio playback.")
    
    if not OPENAI_API_KEY:
        logger.warning("\nOPENAI_API_KEY not found. Test will skip actual feed/TTS generation.")
    else:
        logger.info("\nOPENAI_API_KEY found. Proceeding with a test alarm processing.")
        
        logger.info("\n--- Test 1: Daily News Alarm ---")
        test_alarm_news = MockAlarm(alarm_id="test_news_001", label="Morning News Update")
        process_single_triggered_alarm(test_alarm_news)
        time.sleep(2) # Pause between tests

        logger.info("\n--- Test 2: Topic Facts Alarm ---")
        test_alarm_topic = MockAlarm(
            alarm_id="test_topic_002", 
            label="Fun Facts", 
            feed_type="topic_facts", 
            feed_options={"topic": "penguins"}
        )
        process_single_triggered_alarm(test_alarm_topic)
        time.sleep(2)

        logger.info("\n--- Test 3: Custom Prompt Alarm ---")
        test_alarm_custom = MockAlarm(
            alarm_id="test_custom_003", 
            label="My Custom Thought", 
            feed_type="custom_prompt", 
            feed_options={"prompt": "Give me a short, positive affirmation for the day."}
        )
        process_single_triggered_alarm(test_alarm_custom)
        time.sleep(2)

        logger.info("\n--- Test 4: System Disabled ---")
        test_alarm_system_off = MockAlarm(alarm_id="test_sys_off_004", label="System Off Test")
        process_single_triggered_alarm(test_alarm_system_off, system_is_enabled=False)

    logger.info("\n--- Alarm Handler Test Complete ---")
