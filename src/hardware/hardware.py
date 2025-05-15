import time
import datetime
import os
import logging

# Attempt to import gpiozero directly. If this fails, the script won't run, 
# which is expected if mocking is removed and real hardware is assumed.
try:
    from gpiozero import Button as GPIOZeroButton
    GPIO_LIB_AVAILABLE = True
    GPIO_LIB = "gpiozero"
    logger = logging.getLogger(__name__)
    logger.info("gpiozero.Button loaded successfully.")
except ImportError as e:
    # Initialize logger here if not already, to report the critical error
    if 'logger' not in locals():
        logging.basicConfig(level=logging.INFO) # Basic config if logger wasn't set up
        logger = logging.getLogger(__name__)
    logger.critical(f"CRITICAL: gpiozero library not found. This script requires gpiozero to function. Error: {e}")
    logger.critical("Please ensure gpiozero is installed (e.g., 'sudo apt install python3-gpiozero')")
    GPIO_LIB_AVAILABLE = False
    GPIO_LIB = None
    # To prevent further errors if GPIOZeroButton is used, assign a placeholder 
    # This part of the script will likely not be fully functional without gpiozero
    class GPIOZeroButtonPlaceholder:
        def __init__(self, *args, **kwargs):
            logger.error("gpiozero not available, Button functionality will not work.")
        def __getattr__(self, name):
            # Allow calls but they do nothing
            def method(*args, **kwargs):
                logger.error(f"gpiozero not available, {name} called but will do nothing.")
            return method
    GPIOZeroButton = GPIOZeroButtonPlaceholder

# Removed tempfile and play_audio_file imports previously added for _speak_feedback

from src.config import (
    BUTTON_STOP_ALARM_PIN
)

DEBOUNCE_TIME = 0.3

class HardwareManager:
    def __init__(self, alarm_manager): # Removed tts_speak_function
        self.alarm_manager = alarm_manager
        # self.tts_speak_function = None # Removed
        self.system_enabled = True 
        self._stop_alarm_button = None
        logger.info("HardwareManager initialized for stop alarm button only (no TTS feedback).")

    # Removed _speak_feedback method entirely

    def _speak_feedback(self, text_to_say: str):
        if not self.tts_speak_function:
            logger.warning("HardwareManager: No TTS function provided, cannot speak feedback.")
            return

        temp_audio_file = None
        try:
            # Create a temporary file to store the TTS output
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmpfile:
                temp_audio_file = tmpfile.name
            
            # Generate speech to the temporary file
            # Assuming tts_speak_function is text_to_speech_openai which needs output_filepath
            tts_success = self.tts_speak_function(text_input=text_to_say, output_filepath=temp_audio_file)
            
            if tts_success:
                logger.info(f"HardwareManager: Playing TTS feedback: '{text_to_say}' from {temp_audio_file}")
                # Play the generated audio file.
                # Note: play_audio_file from audio_player can take stop_event,
                # but for short feedback, it might not be necessary.
                # If feedback sounds can be long, consider passing a stop_event here.
                play_audio_file(filepath=temp_audio_file, wait_for_completion=True)
            else:
                logger.warning(f"HardwareManager: TTS generation failed for: '{text_to_say}'")

        except Exception as e:
            logger.error(f"HardwareManager: Error in TTS feedback for '{text_to_say}': {e}", exc_info=True)
        finally:
            if temp_audio_file and os.path.exists(temp_audio_file):
                try:
                    os.remove(temp_audio_file)
                    logger.debug(f"HardwareManager: Cleaned up TTS temp file: {temp_audio_file}")
                except Exception as e_del:
                    logger.error(f"HardwareManager: Error deleting TTS temp file {temp_audio_file}: {e_del}")

    def handle_stop_alarm_button(self):
        time.sleep(0.05) 
        logger.info("Button Pressed: Stop Alarm detected.")
        if not self.system_enabled:
            logger.info("System is disabled. Stop alarm button ignored.")
            # No spoken feedback
            return

        logger.info("ACTION: Requesting to stop sounding alarms.")
        if hasattr(self.alarm_manager, 'stop_active_alarms'):
            stopped_any = self.alarm_manager.stop_active_alarms()
            if stopped_any:
                logger.info("Alarm stop request processed (alarm was active).") # Log instead of speak
            else:
                logger.info("Alarm stop request processed (no alarm was active).") # Log instead of speak
        else:
            logger.warning("AlarmManager (AlarmScheduler) does not have 'stop_active_alarms' method.")
            # No spoken feedback

    def setup_gpio(self):
        if not GPIO_LIB_AVAILABLE:
            logger.error("Cannot setup GPIO: gpiozero library is not available.")
            return
            
        self._stop_alarm_button = None 
        try:
            if BUTTON_STOP_ALARM_PIN > 0:
                self._stop_alarm_button = GPIOZeroButton(
                    BUTTON_STOP_ALARM_PIN,
                    pull_up=False, 
                    bounce_time=DEBOUNCE_TIME
                )
                self._stop_alarm_button.when_pressed = self.handle_stop_alarm_button
                logger.info(f"HardwareManager: Setup Stop Alarm button on pin {BUTTON_STOP_ALARM_PIN} using {GPIO_LIB}.")
            else:
                logger.info(f"HardwareManager: Stop Alarm button pin not configured (is {BUTTON_STOP_ALARM_PIN}). Skipping setup.")
        except Exception as e:
            logger.error(f"HardwareManager: Error setting up gpiozero buttons: {e}", exc_info=True)

    def cleanup_gpio(self):
        if not GPIO_LIB_AVAILABLE:
            # logger.info("Skipping GPIO cleanup: gpiozero library not available.") # Can be noisy
            return

        logger.info("HardwareManager: Cleaning up stop alarm button...")
        if self._stop_alarm_button:
            try:
                if hasattr(self._stop_alarm_button, "close"):
                    self._stop_alarm_button.close()
                    pin_number = getattr(self._stop_alarm_button.pin, 'number', BUTTON_STOP_ALARM_PIN)
                    logger.info(f"Closed button on pin {pin_number}")
            except Exception as e:
                logger.error(f"Error closing stop alarm button: {e}", exc_info=True)
            self._stop_alarm_button = None
        logger.info("HardwareManager: Button cleanup finished.")

