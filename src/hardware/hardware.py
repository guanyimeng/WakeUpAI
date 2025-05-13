# e:\Dev\WakeUpAI\wakeupai\hardware.py
import time
import datetime
import os # Added for IS_RASPBERRY_PI check, though it was implicitly used
import logging

logger = logging.getLogger(__name__)

# --- Mock RPi.GPIO for development on non-Raspberry Pi systems ---
# Check if 'arm' is in platform, a more general check for Pi-like systems
# or if a specific environment variable is set to force using real GPIO
FORCE_REAL_GPIO = os.getenv("FORCE_REAL_GPIO", "false").lower() == "true"

IS_RASPBERRY_PI = FORCE_REAL_GPIO or (os.path.exists('/proc/cpuinfo') and ('Raspberry Pi' in open('/proc/cpuinfo').read()))

if IS_RASPBERRY_PI:
    try:
        import RPi.GPIO as GPIO
        logger.info("RPi.GPIO loaded successfully.")
    except ImportError as e:
        logger.error(f"RPi.GPIO library not found, but system appears to be a Raspberry Pi or FORCE_REAL_GPIO is true: {e}")
        GPIO = None # Explicitly set to None if import fails
    except RuntimeError as e: # Catches issues like "This module can only be run on a Raspberry Pi"
        logger.error(f"RuntimeError importing RPi.GPIO (may not be a Pi or permissions issue): {e}")
        GPIO = None
else:
    logger.info("Not a Raspberry Pi (or RPi.GPIO not available/forced off). Mocking GPIO library.")
    class MockGPIO:
        BCM = "BCM_MODE"
        IN = "INPUT_MODE"
        PUD_UP = "PULL_UP_RESISTOR"
        PUD_DOWN = "PULL_DOWN_RESISTOR"
        FALLING = "FALLING_EDGE_DETECT"
        RISING = "RISING_EDGE_DETECT"
        BOTH = "BOTH_EDGE_DETECT"
        LOW = 0
        HIGH = 1

        def __init__(self):
            self._pins_setup = {}
            self._callbacks = {}
            logger.debug("MockGPIO: Initialized.")

        def setmode(self, mode):
            logger.debug(f"MockGPIO: Set mode to {mode}")

        def setup(self, pin, direction, pull_up_down=None):
            self._pins_setup[pin] = {"direction": direction, "pull_up_down": pull_up_down}
            logger.debug(f"MockGPIO: Setup pin {pin} as {direction} with pull_up_down={pull_up_down}")

        def add_event_detect(self, pin, edge, callback=None, bouncetime=200):
            if pin not in self._pins_setup:
                logger.warning(f"MockGPIO: Pin {pin} not set up. Call setup() first.")
                return
            self._callbacks[pin] = callback
            logger.debug(f"MockGPIO: Added event detect on pin {pin} for {edge} edge. Callback: {callback.__name__ if callback else 'None'}. Bouncetime: {bouncetime}ms")

        def remove_event_detect(self, pin):
            if pin in self._callbacks:
                del self._callbacks[pin]
                logger.debug(f"MockGPIO: Removed event detect from pin {pin}")

        def input(self, pin):
            logger.debug(f"MockGPIO: Input read from pin {pin} (returning LOW/not pressed by default)")
            return self.LOW 

        def cleanup(self, pin=None):
            if pin:
                if pin in self._pins_setup: del self._pins_setup[pin]
                if pin in self._callbacks: del self._callbacks[pin]
                logger.debug(f"MockGPIO: Cleaned up pin {pin}")
            else:
                self._pins_setup.clear()
                self._callbacks.clear()
                logger.info("MockGPIO: Cleaned up all channels.")

        def trigger_event(self, pin):
            if pin in self._callbacks and self._callbacks[pin] is not None:
                logger.info(f"MockGPIO: Manually triggering event for pin {pin}")
                try:
                    self._callbacks[pin](pin) 
                except Exception as e_cb:
                    logger.error(f"MockGPIO: Error during triggered callback for pin {pin}: {e_cb}", exc_info=True)
            else:
                logger.warning(f"MockGPIO: No callback registered or callback is None for pin {pin}")

    GPIO = MockGPIO()

# Ensure GPIO is not None before use, even if IS_RASPBERRY_PI was true but import failed
if GPIO is None and IS_RASPBERRY_PI:
    logger.critical("GPIO library failed to load on a Raspberry Pi! Hardware buttons will not work.")
    # Optionally, could try to fall back to MockGPIO here if essential for app to run for other features
    # GPIO = MockGPIO() 
    # logger.warning("Falling back to MockGPIO on Raspberry Pi due to RPi.GPIO load failure.")

from wakeupai.config import (
    BUTTON_ENABLE_DISABLE_PIN,
    BUTTON_SNOOZE_PIN,
    BUTTON_SPEAK_TIME_PIN
)

# Debounce time for buttons in milliseconds
DEBOUNCE_TIME = 300

class HardwareManager:
    def __init__(self, alarm_manager, tts_speak_function):
        self.alarm_manager = alarm_manager
        self.tts_speak_function = tts_speak_function
        self.system_enabled = True # Overall system enabled state, can be toggled by button
        self._pins_to_check = []
        self.GPIO = GPIO # Store the active GPIO library (real or mock)
        logger.info("HardwareManager initialized.")

    def _get_pin_name(self, pin_number):
        if pin_number == BUTTON_ENABLE_DISABLE_PIN: return "Enable/Disable"
        if pin_number == BUTTON_SNOOZE_PIN: return "Snooze"
        if pin_number == BUTTON_SPEAK_TIME_PIN: return "Speak Time"
        return "Unknown Pin"

    def handle_enable_disable_button(self, channel):
        time.sleep(0.05) # Debounce / confirm press
        # if self.GPIO.input(channel) == self.GPIO.LOW: # Check for active low state
        logger.info(f"Button Pressed: Enable/Disable (Pin {channel}) detected.")
        self.system_enabled = not self.system_enabled
        status_message = "System Enabled" if self.system_enabled else "System Disabled"
        logger.info(f"ACTION: {status_message}")
        if self.tts_speak_function:
            self.tts_speak_function(status_message)
        # This could also globally enable/disable alarms in AlarmManager if desired.
        # For example:
        # for alarm_id in self.alarm_manager.alarms:
        #     if self.system_enabled:
        #         self.alarm_manager.enable_alarm(alarm_id)
        #     else:
        #         self.alarm_manager.disable_alarm(alarm_id)
        # print(f"All alarms set to {'enabled' if self.system_enabled else 'disabled'}")

    def handle_snooze_button(self, channel):
        time.sleep(0.05)
        # if self.GPIO.input(channel) == self.GPIO.LOW:
        logger.info(f"Button Pressed: Snooze (Pin {channel}) detected.")
        if not self.system_enabled:
            logger.info("System is disabled. Snooze button ignored.")
            if self.tts_speak_function: self.tts_speak_function("System disabled")
            return

        snoozed_labels = self.alarm_manager.request_snooze_for_active_alarms()

        if snoozed_labels:
            msg = f"Snooze activated for: {', '.join(snoozed_labels)}."
            logger.info(f"ACTION: {msg}")
            if self.tts_speak_function:
                if len(snoozed_labels) == 1:
                    self.tts_speak_function(f"Alarm {snoozed_labels[0]} snoozed.")
                elif len(snoozed_labels) > 1:
                    self.tts_speak_function(f"{len(snoozed_labels)} alarms snoozed.")
                # No generic "Alarm snoozed" as request_snooze_for_active_alarms handles the no-alarms-snoozed case message
        else:
            # alarm_manager.request_snooze_for_active_alarms logs details if nothing was snoozed.
            logger.info("No active alarms were ultimately snoozed by the button press.") 
            if self.tts_speak_function: self.tts_speak_function("No alarm to snooze now.")

    def handle_speak_time_button(self, channel):
        time.sleep(0.05)
        # if self.GPIO.input(channel) == self.GPIO.LOW:
        logger.info(f"Button Pressed: Speak Time (Pin {channel}) detected.")
        if not self.system_enabled:
            logger.info("System is disabled. Speak time button ignored.")
            if self.tts_speak_function: self.tts_speak_function("System disabled")
            return

        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p") 
        full_speech = f"The current time is {time_str}."
        logger.info(f"ACTION: Speaking time: {full_speech}")
        if self.tts_speak_function:
            self.tts_speak_function(full_speech)
        else:
            logger.warning("TTS function not available to speak time.")

    def setup_gpio(self):
        if not self.GPIO or not hasattr(self.GPIO, 'setmode'):
            logger.critical("HardwareManager: GPIO library (real or mock) not available or not initialized correctly. Cannot set up hardware buttons.")
            return
        
        try:
            self.GPIO.setmode(self.GPIO.BCM) 
            logger.info("HardwareManager: GPIO mode set to BCM.")

            button_pins_to_setup = [
                (BUTTON_ENABLE_DISABLE_PIN, "Enable/Disable", self.handle_enable_disable_button),
                (BUTTON_SNOOZE_PIN, "Snooze", self.handle_snooze_button),
                (BUTTON_SPEAK_TIME_PIN, "Speak Time", self.handle_speak_time_button)
            ]

            for pin, name, callback_func in button_pins_to_setup:
                if pin > 0:
                    self.GPIO.setup(pin, self.GPIO.IN, pull_up_down=self.GPIO.PUD_UP)
                    self.GPIO.add_event_detect(pin, self.GPIO.FALLING, callback=callback_func, bouncetime=DEBOUNCE_TIME)
                    self._pins_to_check.append(pin)
                    logger.info(f"HardwareManager: Setup {name} button on pin {pin}.")
                else:
                    logger.info(f"HardwareManager: {name} button pin not configured (is {pin}). Skipping setup.")
            
            logger.info("HardwareManager: GPIO setup for hardware buttons complete.")

        except Exception as e:
            logger.error(f"HardwareManager: Error setting up GPIO: {e}", exc_info=True)
            if hasattr(self.GPIO, 'cleanup'): 
                try: self.GPIO.cleanup()
                except Exception as e_clean: logger.error(f"HardwareManager: Error during GPIO cleanup after setup failure: {e_clean}", exc_info=True)

    def cleanup_gpio(self):
        logger.info("HardwareManager: Cleaning up GPIO...")
        if self.GPIO and hasattr(self.GPIO, 'cleanup'):
            try:
                self.GPIO.cleanup() 
                logger.info("HardwareManager: GPIO cleanup finished.")
            except Exception as e:
                logger.error(f"HardwareManager: Error during GPIO cleanup: {e}", exc_info=True)
        else:
            logger.info("HardwareManager: No GPIO library to cleanup or cleanup method not available.")

# --- Main execution for testing hardware module (with mocked GPIO) ---
if __name__ == '__main__':
    # Setup basic logging for the __main__ test if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG, 
            format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger.info("Basic logging configured for hardware.py direct test run.")

    logger.info("--- Hardware Module Test ---")
    
    # For testing, we need a mock alarm_manager and a mock tts_speak_function
    class MockAlarmManager:
        def __init__(self):
            self.alarms = {
                "test_alarm_1": type('Alarm', (object,), {
                    "label": "Test Alarm 1 for HW Test", 
                    "enabled": True, 
                    "is_snoozing": False, 
                    "snooze_until_datetime": None,
                    "alarm_id": "test_alarm_1_hw",
                    "should_trigger": lambda dt: True, 
                })
            }
            self.actively_sounding_alarm_ids = set() # Mock this attribute
            logger.debug("MockAlarmManager initialized for hardware test.")

        def get_alarm(self, alarm_id):
            return self.alarms.get(alarm_id)

        def snooze_alarm(self, alarm_id, minutes=9):
            alarm = self.get_alarm(alarm_id)
            if alarm:
                alarm.is_snoozing = True 
                logger.info(f"MockAlarmManager: Snoozed alarm '{alarm.label}' (ID: {alarm_id}) for {minutes} minutes.")
            else:
                logger.warning(f"MockAlarmManager: Alarm {alarm_id} not found for snooze.")
        
        def request_snooze_for_active_alarms(self, minutes=9) -> list[str]:
            logger.info(f"MockAlarmManager: request_snooze_for_active_alarms called. Active IDs: {self.actively_sounding_alarm_ids}")
            snoozed_labels = []
            # Simulate adding an alarm to active set for testing snooze path
            if not self.actively_sounding_alarm_ids and "test_alarm_1_hw" in self.alarms:
                self.actively_sounding_alarm_ids.add("test_alarm_1_hw")
                logger.debug("MockAlarmManager: Added test_alarm_1_hw to active set for snooze test.")
            
            for alarm_id in list(self.actively_sounding_alarm_ids):
                alarm = self.get_alarm(alarm_id)
                if alarm and alarm.enabled:
                    self.snooze_alarm(alarm_id, minutes)
                    snoozed_labels.append(alarm.label)
            return snoozed_labels
        
        def enable_alarm(self, alarm_id): logger.info(f"MockAlarmManager: Enabled {alarm_id}")
        def disable_alarm(self, alarm_id): logger.info(f"MockAlarmManager: Disabled {alarm_id}")

    mock_alarm_manager_instance = MockAlarmManager()

    def mock_tts_speak(text_to_speak):
        logger.info(f"MockTTS: Speaking -> '{text_to_speak}'")
        return True

    # Use local copies of pin numbers for testing override if not set in env
    # This ensures the test can run even if config hasn't loaded .env properly for direct script run
    test_enable_pin = BUTTON_ENABLE_DISABLE_PIN if BUTTON_ENABLE_DISABLE_PIN > 0 else 17
    test_snooze_pin = BUTTON_SNOOZE_PIN if BUTTON_SNOOZE_PIN > 0 else 27
    test_speak_time_pin = BUTTON_SPEAK_TIME_PIN if BUTTON_SPEAK_TIME_PIN > 0 else 22

    if BUTTON_ENABLE_DISABLE_PIN == 0: logger.info(f"Button Enable/Disable pin not in env, using mock {test_enable_pin} for hw test.")
    if BUTTON_SNOOZE_PIN == 0: logger.info(f"Button Snooze pin not in env, using mock {test_snooze_pin} for hw test.")
    if BUTTON_SPEAK_TIME_PIN == 0: logger.info(f"Button Speak Time pin not in env, using mock {test_speak_time_pin} for hw test.")

    # Override config pins for this test if they were 0, so MockGPIO can set them up
    # This is a bit of a hack for direct script testing; in app, config would be definitive.
    global_button_enable_pin_orig, global_button_snooze_pin_orig, global_button_speak_time_pin_orig = BUTTON_ENABLE_DISABLE_PIN, BUTTON_SNOOZE_PIN, BUTTON_SPEAK_TIME_PIN
    BUTTON_ENABLE_DISABLE_PIN_test_scope = test_enable_pin
    BUTTON_SNOOZE_PIN_test_scope = test_snooze_pin
    BUTTON_SPEAK_TIME_PIN_test_scope = test_speak_time_pin
    
    # Temporarily modify module level pin numbers if they were 0 for testing setup, ugly but for __main__ direct run
    # A better way would be to pass pin numbers to HardwareManager or have HardwareManager read them directly.
    # For now, this direct patch is for the if __name__ == '__main__' block only.
    # Monkey patching the global constants from config.py for the scope of this test
    import wakeupai.config as config_module
    original_pins = {
        'BUTTON_ENABLE_DISABLE_PIN': config_module.BUTTON_ENABLE_DISABLE_PIN,
        'BUTTON_SNOOZE_PIN': config_module.BUTTON_SNOOZE_PIN,
        'BUTTON_SPEAK_TIME_PIN': config_module.BUTTON_SPEAK_TIME_PIN
    }
    if config_module.BUTTON_ENABLE_DISABLE_PIN == 0: config_module.BUTTON_ENABLE_DISABLE_PIN = 17
    if config_module.BUTTON_SNOOZE_PIN == 0: config_module.BUTTON_SNOOZE_PIN = 27
    if config_module.BUTTON_SPEAK_TIME_PIN == 0: config_module.BUTTON_SPEAK_TIME_PIN = 22

    hw_manager = HardwareManager(alarm_manager=mock_alarm_manager_instance, tts_speak_function=mock_tts_speak)
    hw_manager.setup_gpio() # This uses the (potentially patched) global pin numbers from config

    logger.info("\nHardware buttons set up. Using MockGPIO, manually triggering events for testing...")

    try:
        if hw_manager.GPIO and hasattr(hw_manager.GPIO, 'trigger_event'):
            if config_module.BUTTON_ENABLE_DISABLE_PIN > 0:
                logger.info("\n--- Simulating Enable/Disable Button Press (1st time) ---")
                hw_manager.GPIO.trigger_event(config_module.BUTTON_ENABLE_DISABLE_PIN)
                time.sleep(0.1)
                logger.info(f"System enabled status: {hw_manager.system_enabled}")
                
                logger.info("\n--- Simulating Enable/Disable Button Press (2nd time) ---")
                hw_manager.GPIO.trigger_event(config_module.BUTTON_ENABLE_DISABLE_PIN)
                time.sleep(0.1)
                logger.info(f"System enabled status: {hw_manager.system_enabled}")

            if config_module.BUTTON_SNOOZE_PIN > 0:
                logger.info("\n--- Simulating Snooze Button Press ---")
                hw_manager.GPIO.trigger_event(config_module.BUTTON_SNOOZE_PIN)
                time.sleep(0.1)

            if config_module.BUTTON_SPEAK_TIME_PIN > 0:
                logger.info("\n--- Simulating Speak Time Button Press ---")
                hw_manager.GPIO.trigger_event(config_module.BUTTON_SPEAK_TIME_PIN)
                time.sleep(0.1)
        else:
            logger.warning("MockGPIO trigger_event not available, skipping button press simulations.")

        logger.info("\nTest complete. Press Ctrl+C to exit (cleanup will run).")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected during test.")
    finally:
        hw_manager.cleanup_gpio()
        # Restore original pin constants in config module
        config_module.BUTTON_ENABLE_DISABLE_PIN = original_pins['BUTTON_ENABLE_DISABLE_PIN']
        config_module.BUTTON_SNOOZE_PIN = original_pins['BUTTON_SNOOZE_PIN']
        config_module.BUTTON_SPEAK_TIME_PIN = original_pins['BUTTON_SPEAK_TIME_PIN']
        logger.debug("Restored original pin configurations in config module.")
    logger.info("--- Hardware Module Test Complete ---")
