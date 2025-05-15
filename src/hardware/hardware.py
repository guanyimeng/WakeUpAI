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


    logger.info("--- Hardware Module Test for Raspberry Pi (Real Button, No TTS Feedback) ---")

    if not GPIO_LIB_AVAILABLE:
        logger.critical("gpiozero is not available. Aborting hardware test.")
        return

    class MockAlarmManager:
        def stop_active_alarms(self):
            logger.info("MockAlarmManager: stop_active_alarms() called by button press.")
            return True # Simulate that an alarm was indeed stopped

    # mock_tts_generator is no longer needed as HardwareManager doesn't use TTS

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

    # HardwareManager is now instantiated without tts_speak_function
    hw_manager = HardwareManager(alarm_manager=MockAlarmManager())
    hw_manager.setup_gpio()

    if not hw_manager._stop_alarm_button:
        logger.error("Failed to set up the stop alarm button in HardwareManager. Exiting test.")
        return


    logger.info("Hardware Stop Alarm button is set up (no TTS feedback will occur).")
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
