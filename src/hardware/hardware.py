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

# Added imports
import tempfile
# import os # os is already imported at the top of the file

# Import for playing TTS feedback
try:
    from .audio_player import play_audio_file
except ImportError:
    # Fallback for direct execution if .audio_player is not found (e.g. running __main__)
    # This assumes audio_player.py is in the same directory for direct run.
    # For the main application (main.py), the relative import should work.
    try:
        from audio_player import play_audio_file
        logger.info("audio_player.py imported directly for HardwareManager feedback.")
    except ImportError:
        logger.error("HardwareManager: play_audio_file could not be imported for TTS feedback.")
        def play_audio_file(*args, **kwargs): # Placeholder if import fails
            logger.error("play_audio_file is not available, cannot play TTS feedback.")
            return False


from src.config import (
    BUTTON_STOP_ALARM_PIN
)

DEBOUNCE_TIME = 0.3

class HardwareManager:
    def __init__(self, alarm_manager, tts_speak_function): # Removed audio_play_function
        self.alarm_manager = alarm_manager
        self.tts_speak_function = tts_speak_function
        # self.audio_play_function = None # Removed
        self.system_enabled = True 
        self._stop_alarm_button = None
        logger.info("HardwareManager initialized for stop alarm button only.")

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
            self._speak_feedback("System disabled")
            return

        logger.info("ACTION: Requesting to stop sounding alarms.")
        if hasattr(self.alarm_manager, 'stop_active_alarms'):
            stopped_any = self.alarm_manager.stop_active_alarms()
            if stopped_any:
                self._speak_feedback("Alarm stopped.")
            # else: # Optionally, provide feedback if no alarm was actually sounding
                # self._speak_feedback("No active alarm to stop.")
        else:
            logger.warning("AlarmManager (AlarmScheduler) does not have 'stop_active_alarms' method.")
            self._speak_feedback("Could not stop alarm.")

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

if __name__ == '__main__':
    # Ensure basic logging is configured for direct script execution
    if not logging.getLogger().handlers or not any(isinstance(h, logging.StreamHandler) for h in logging.getLogger().handlers):
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[logging.StreamHandler()] # Explicitly add handler
        )
    # Re-fetch logger in case basicConfig was called by the import block or here
    logger = logging.getLogger(__name__)


    logger.info("--- Hardware Module Test for Raspberry Pi (Real Button) ---")

    if not GPIO_LIB_AVAILABLE:
        logger.critical("gpiozero is not available. Aborting hardware test.")
        # exit(1) # Don't exit if just importing, allow script to be imported elsewhere
        return  # Return if called as __main__ and gpiozero missing

    class MockAlarmManager:
        def stop_active_alarms(self):
            logger.info("MockAlarmManager: stop_active_alarms() called by button press.")
            return True

    # Mock tts_speak_function for testing HardwareManager
    # This mock needs to mimic the signature that _speak_feedback expects
    # from text_to_speech_openai: (text_input: str, output_filepath: str) -> bool
    def mock_tts_generator(text_input: str, output_filepath: str) -> bool:
        logger.info(f"MockTTSGenerator: Received text: '{text_input}', would write to: {output_filepath}")
        # Simulate successful TTS file creation
        try:
            with open(output_filepath, 'w') as f:
                f.write(f"This is a mock audio file for '{text_input}'.")
            logger.info(f"MockTTSGenerator: Successfully created mock file at {output_filepath}")
            return True
        except Exception as e:
            logger.error(f"MockTTSGenerator: Failed to create mock file: {e}")
            return False

    # Import config here, inside __main__, to ensure BUTTON_STOP_ALARM_PIN is fresh
    try:
        from src.config import BUTTON_STOP_ALARM_PIN as TEST_BUTTON_PIN
    except ImportError:
        logger.error("Could not import BUTTON_STOP_ALARM_PIN from src.config. Make sure src.config exists.")
        TEST_BUTTON_PIN = 0 # Default to 0 if import fails

    if TEST_BUTTON_PIN == 0:
        logger.error("BUTTON_STOP_ALARM_PIN is configured as 0 in src.config.py.")
        logger.error("Hardware test requires a valid GPIO pin number for the button.")
        logger.error("Please set BUTTON_STOP_ALARM_PIN to 17 (or your connected pin) in src/config.py.")
        exit(1)

    logger.info(f"Test will use GPIO pin {TEST_BUTTON_PIN} for the Stop Alarm button.")
    logger.info(f"Ensure a button is connected to GPIO {TEST_BUTTON_PIN} (with a pull-down resistor). Action is on press.")

    # Note: The original mock_tts just logged. The new mock_tts_generator simulates file creation
    # because _speak_feedback now expects the TTS function to create a file.
    # The play_audio_file mock above will handle the "playback" part for the test.

    hw_manager = HardwareManager(alarm_manager=MockAlarmManager(), tts_speak_function=mock_tts_generator)
    hw_manager.setup_gpio()

    if not hw_manager._stop_alarm_button:
        logger.error("Failed to set up the stop alarm button in HardwareManager. Exiting test.")
        # exit(1) # Don't exit if just importing
        return  # Return if called as __main__ and button setup failed


    logger.info("Hardware Stop Alarm button is set up.")
    logger.info("Press the button connected to GPIO {} to test. Press Ctrl+C to exit test." .format(TEST_BUTTON_PIN))

    try:
        # Keep the script running to detect button presses
        # gpiozero handles button events in a background thread, so the main thread just needs to stay alive.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt detected. Exiting test...")
    except Exception as e:
        logger.error(f"An error occurred during the test: {e}", exc_info=True)
    finally:
        logger.info("Cleaning up GPIO...")
        hw_manager.cleanup_gpio()
        logger.info("GPIO cleanup complete. Test finished.")
