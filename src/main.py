import time
import logging
import sys
import os

# Adjust the Python path to include the project root (if main.py is in src)
# This allows for absolute imports from the project's perspective
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.alarm.newalarm import AlarmScheduler
from src.hardware.hardware import HardwareManager, GPIO_LIB
from src.wakeupai.tts import text_to_speech_openai # For speak time function
from src.config import (
    BUTTON_STOP_ALARM_PIN,
    BUTTON_SNOOZE_PIN, # Snooze button not used in newalarm.py logic directly, but can be adapted if needed
    BUTTON_SPEAK_TIME_PIN,
    OPENAI_API_KEY
)
import datetime

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout) # Ensure logs go to console
    ]
)
logger = logging.getLogger(__name__) # Logger for this main.py file


# --- Global Variables & Setup ---
alarm_scheduler = AlarmScheduler()
hardware_manager = None # Will be initialized in main()


def initialize_alarms():
    """Initializes a predefined set of alarms."""
    logger.info("Initializing predefined alarms...")
    # Example: Add a daily news alarm 1 minute from now for testing
    # In a real scenario, these would come from a config file or database
    now = datetime.datetime.now()
    test_alarm_time = (now + datetime.timedelta(minutes=1)).strftime("%H:%M")
    
    alarm_scheduler.add_alarm(
        alarm_time_str=test_alarm_time, 
        name="Daily News Digest",
        feed_type="daily_news",
        feed_options={"country": "US"}
    )

    alarm_scheduler.add_alarm(
        alarm_time_str=(now + datetime.timedelta(minutes=3)).strftime("%H:%M"),
        name="Tech Facts",
        feed_type="topic_facts",
        feed_options={"topic": "Anthropology"}
    )

    alarm_scheduler.add_alarm(
        alarm_time_str=(now + datetime.timedelta(minutes=5)).strftime("%H:%M"),
        name="Wrong Input",
        feed_type="wrong_input",
        feed_options={}
    )
    alarm_scheduler.list_alarms()


def main():
    global hardware_manager
    logger.info("Starting WakeUpAI Alarm System...")

    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY is not set. Feed generation and TTS will use defaults or fail.")

    # Initialize Alarms
    initialize_alarms()

    # Initialize HardwareManager
    # HardwareManager no longer handles TTS feedback itself or other audio playback.
    hardware_manager = HardwareManager(
        alarm_manager=alarm_scheduler # Hardware manager will call alarm_scheduler.stop_active_alarms()
    )
    hardware_manager.setup_gpio() # Setup GPIO buttons
    
    if GPIO_LIB == "mock":
        logger.info("Running with MOCK GPIO. You can simulate button presses if MockButton has a simulate_press method and it's called.")
        # Example of how you might simulate a press for testing if needed:
        # if hasattr(hardware_manager._buttons[0], 'simulate_press'):
        #     logger.info("Simulating a stop button press via mock...")
        #     hardware_manager._buttons[0].simulate_press() # Simulate stop button if it's the first

    # Start the Alarm Scheduler (this starts its own thread)
    alarm_scheduler.start()

    logger.info("Application is running. Press Ctrl+C to exit.")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1) 
            # The main loop can be used for other tasks if necessary,
            # but for now, it just keeps the program running while scheduler and GPIO events work in background.
            if not alarm_scheduler._scheduler_thread or not alarm_scheduler._scheduler_thread.is_alive():
                logger.error("Alarm scheduler thread has unexpectedly stopped! Attempting to restart.")
                alarm_scheduler.start()
                if not alarm_scheduler._scheduler_thread or not alarm_scheduler._scheduler_thread.is_alive():
                    logger.critical("Failed to restart alarm scheduler thread. Exiting.")
                    break # Exit if restart fails

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        logger.info("Initiating shutdown sequence.")
        if hardware_manager:
            hardware_manager.cleanup_gpio()
        if alarm_scheduler:
            alarm_scheduler.stop() # Stops the scheduler thread and any active alarms
        logger.info("WakeUpAI Alarm System shut down gracefully.")

if __name__ == "__main__":
    main()
