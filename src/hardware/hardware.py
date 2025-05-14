# e:\Dev\WakeUpAI\wakeupai\hardware.py
import time
import datetime
import os
import logging

logger = logging.getLogger(__name__)

# --- GPIOZero setup ---
# Use GPIOZero on Raspberry Pi 5 and above, fallback to mock on non-RPi.
FORCE_REAL_GPIO = os.getenv("FORCE_REAL_GPIO", "false").lower() == "true"

try:
    # Try to import gpiozero only if on a pi or force flag
    IS_RASPBERRY_PI = FORCE_REAL_GPIO or (
        os.path.exists('/proc/cpuinfo') and any(
            proc_line in open('/proc/cpuinfo').read()
            for proc_line in ['Raspberry Pi', 'BCM2835', 'BCM2708', 'BCM2709', 'BCM2710', 'BCM2711']
        )
    )
except Exception:
    IS_RASPBERRY_PI = False

if IS_RASPBERRY_PI:
    try:
        from gpiozero import Button as GPIOZeroButton
        logger.info("gpiozero.Button loaded successfully.")
        GPIO_LIB = "gpiozero"
    except ImportError as e:
        logger.error(f"gpiozero library not found, though system appears to be Raspberry Pi or FORCE_REAL_GPIO is true: {e}")
        GPIOZeroButton = None
        GPIO_LIB = None
else:
    GPIOZeroButton = None
    GPIO_LIB = None

if not IS_RASPBERRY_PI or not GPIOZeroButton:
    logger.info("Not a Raspberry Pi (or gpiozero not available/forced off). Mocking GPIO library.")

    class MockButton:
        def __init__(self, pin, pull_up=True, bounce_time=None):
            self.pin = pin
            self.pull_up = pull_up
            self.bounce_time = bounce_time
            self.when_pressed = None
            logger.debug(f"MockButton: Initialized for pin {pin}, pull_up={pull_up}, bounce_time={bounce_time}")

        def simulate_press(self):
            logger.info(f"MockButton: Simulating press on pin {self.pin}")
            if self.when_pressed:
                try:
                    self.when_pressed()
                except Exception as e:
                    logger.error(f"MockButton: Error during when_pressed callback for pin {self.pin}: {e}", exc_info=True)

    GPIOZeroButton = MockButton
    GPIO_LIB = "mock"

from ..config import (
    BUTTON_STOP_ALARM_PIN,
    BUTTON_SNOOZE_PIN,
    BUTTON_SPEAK_TIME_PIN
)

# Debounce time for buttons in seconds (gpiozero expects float), default 0.3s
DEBOUNCE_TIME = 0.3

class HardwareManager:
    def __init__(self, alarm_manager, tts_speak_function):
        self.alarm_manager = alarm_manager
        self.tts_speak_function = tts_speak_function
        self.system_enabled = True # Overall system enabled state, can be toggled by button
        self._buttons = []
        logger.info("HardwareManager initialized.")

    def _get_pin_name(self, pin_number):
        if pin_number == BUTTON_STOP_ALARM_PIN: return "Stop Alarm"
        if pin_number == BUTTON_SNOOZE_PIN: return "Snooze"
        if pin_number == BUTTON_SPEAK_TIME_PIN: return "Speak Time"
        return "Unknown Pin"

    def handle_stop_alarm_button(self):
        time.sleep(0.05)
        logger.info(f"Button Pressed: Stop Alarm detected.")
        if not self.system_enabled:
            logger.info("System is disabled. Stop alarm button ignored.")
            if self.tts_speak_function: self.tts_speak_function("System disabled")
            return

        logger.info("ACTION: Requesting to stop sounding alarms.")
        if hasattr(self.alarm_manager, 'stop_sounding_alarms'):
            self.alarm_manager.stop_sounding_alarms()
            if self.tts_speak_function:
                 self.tts_speak_function("Alarm stopped.")
        else:
            logger.warning("AlarmManager does not have 'stop_sounding_alarms' method.")
            if self.tts_speak_function:
                self.tts_speak_function("Could not stop alarm.")

    def handle_snooze_button(self):
        time.sleep(0.05)
        logger.info(f"Button Pressed: Snooze detected.")
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
        else:
            logger.info("No active alarms were ultimately snoozed by the button press.") 
            if self.tts_speak_function: self.tts_speak_function("No alarm to snooze now.")

    def handle_speak_time_button(self):
        time.sleep(0.05)
        logger.info(f"Button Pressed: Speak Time detected.")
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
        # Create buttons for stop alarm, snooze, speak time if pins are set
        self._buttons.clear()
        try:
            pin_button_map = [
                (BUTTON_STOP_ALARM_PIN, "Stop Alarm", self.handle_stop_alarm_button),
                (BUTTON_SNOOZE_PIN, "Snooze", self.handle_snooze_button),
                (BUTTON_SPEAK_TIME_PIN, "Speak Time", self.handle_speak_time_button),
            ]
            for pin, name, callback_func in pin_button_map:
                if pin > 0:
                    btn = GPIOZeroButton(
                        pin,
                        pull_up=True,
                        bounce_time=DEBOUNCE_TIME
                    )
                    btn.when_pressed = callback_func
                    self._buttons.append(btn)
                    logger.info(f"HardwareManager: Setup {name} button on pin {pin} using {GPIO_LIB}.")
                else:
                    logger.info(f"HardwareManager: {name} button pin not configured (is {pin}). Skipping setup.")

            logger.info("HardwareManager: Button setup for hardware buttons complete.")

        except Exception as e:
            logger.error(f"HardwareManager: Error setting up gpiozero buttons: {e}", exc_info=True)

    def cleanup_gpio(self):
        logger.info("HardwareManager: Cleaning up buttons...")
        for btn in getattr(self, "_buttons", []):
            try:
                # gpiozero Button will auto cleanup on program exit, but we try to close if supported
                if hasattr(btn, "close"):
                    btn.close()
                    logger.info(f"Closed button on pin {getattr(btn, 'pin', None)}")
            except Exception as e:
                logger.error(f"Error closing button: {e}", exc_info=True)
        self._buttons.clear()
        logger.info("HardwareManager: Button cleanup finished.")

# =============================================================================================================================
# --- Main execution for testing hardware module (with mocked GPIO) ---
if __name__ == '__main__':
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
            self.actively_sounding_alarm_ids = set()
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
            if not self.actively_sounding_alarm_ids and "test_alarm_1_hw" in self.alarms:
                self.actively_sounding_alarm_ids.add("test_alarm_1_hw")
                logger.debug("MockAlarmManager: Added test_alarm_1_hw to active set for snooze test.")

            for alarm_id in list(self.actively_sounding_alarm_ids):
                alarm = self.get_alarm(alarm_id)
                if alarm and alarm.enabled:
                    self.snooze_alarm(alarm_id, minutes)
                    snoozed_labels.append(alarm.label)
            return snoozed_labels

        def stop_sounding_alarms(self):
            logger.info("MockAlarmManager: stop_sounding_alarms called.")
            if self.actively_sounding_alarm_ids:
                stopped_ids = list(self.actively_sounding_alarm_ids)
                self.actively_sounding_alarm_ids.clear()
                logger.info(f"MockAlarmManager: Stopped alarms: {stopped_ids}")
            else:
                logger.info("MockAlarmManager: No alarms currently sounding to stop.")

        def enable_alarm(self, alarm_id): logger.info(f"MockAlarmManager: Enabled {alarm_id}")
        def disable_alarm(self, alarm_id): logger.info(f"MockAlarmManager: Disabled {alarm_id}")

    mock_alarm_manager_instance = MockAlarmManager()

    def mock_tts_speak(text_to_speak):
        logger.info(f"MockTTS: Speaking -> '{text_to_speak}'")
        return True

    # Use local copies of pin numbers for testing override if not set in env
    test_stop_alarm_pin = BUTTON_STOP_ALARM_PIN if BUTTON_STOP_ALARM_PIN > 0 else 23
    test_snooze_pin = BUTTON_SNOOZE_PIN if BUTTON_SNOOZE_PIN > 0 else 27
    test_speak_time_pin = BUTTON_SPEAK_TIME_PIN if BUTTON_SPEAK_TIME_PIN > 0 else 22

    # Patch config module if needed (for test only)
    import ..config as config_module
    original_pins = {
        'BUTTON_STOP_ALARM_PIN': config_module.BUTTON_STOP_ALARM_PIN,
        'BUTTON_SNOOZE_PIN': config_module.BUTTON_SNOOZE_PIN,
        'BUTTON_SPEAK_TIME_PIN': config_module.BUTTON_SPEAK_TIME_PIN
    }
    if config_module.BUTTON_STOP_ALARM_PIN == 0: config_module.BUTTON_STOP_ALARM_PIN = 23
    if config_module.BUTTON_SNOOZE_PIN == 0: config_module.BUTTON_SNOOZE_PIN = 27
    if config_module.BUTTON_SPEAK_TIME_PIN == 0: config_module.BUTTON_SPEAK_TIME_PIN = 17

    hw_manager = HardwareManager(alarm_manager=mock_alarm_manager_instance, tts_speak_function=mock_tts_speak)
    hw_manager.setup_gpio()

    logger.info("\nHardware buttons set up. Testing event triggers...")

    try:
        # Simulate presses if running with MockButton
        for btn in getattr(hw_manager, "_buttons", []):
            if hasattr(btn, "simulate_press"):
                logger.info(f"\n--- Simulating Button Press on pin {btn.pin} ---")
                btn.simulate_press()
                time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected during test.")
    finally:
        hw_manager.cleanup_gpio()
        # Restore original pin configs
        config_module.BUTTON_STOP_ALARM_PIN = original_pins['BUTTON_STOP_ALARM_PIN']
        config_module.BUTTON_SNOOZE_PIN = original_pins['BUTTON_SNOOZE_PIN']
        config_module.BUTTON_SPEAK_TIME_PIN = original_pins['BUTTON_SPEAK_TIME_PIN']
        logger.debug("Restored original pin configurations in config module.")
    logger.info("--- Hardware Module Test Complete ---")

