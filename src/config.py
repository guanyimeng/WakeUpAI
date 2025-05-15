import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables from a .env file if it exists
# This is useful for local development.
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Assuming .env is in the project root
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    logger.info(f"Loaded environment variables from {dotenv_path}")
else:
    # Try loading .env from the current working directory if it's different from the project root
    # (e.g. when running tests from the root)
    if os.path.exists(".env"):
        load_dotenv()
        logger.info("Loaded environment variables from local .env")
    else:
        logger.info("No .env file found. Relying on system environment variables.")

class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass

# --- OpenAI API Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    # In a real application, you might raise ConfigError here or handle it gracefully
    # For now, we'll log a warning, as the app might have features not requiring OpenAI
    logger.warning("OPENAI_API_KEY is not set in environment variables. OpenAI-dependent features will fail.")
    # raise ConfigError("OPENAI_API_KEY is not set in environment variables.")

# --- Application Logging Configuration ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if LOG_LEVEL not in VALID_LOG_LEVELS:
    logger.warning(f"Invalid LOG_LEVEL '{LOG_LEVEL}' specified in environment. Defaulting to INFO.")
    LOG_LEVEL = "INFO"

# --- Text-to-Speech Configuration (Example) ---
# Maximum duration for generated speech in seconds (5 minutes)
TTS_MAX_DURATION_SECONDS = int(os.getenv("TTS_MAX_DURATION_SECONDS", 5 * 60))
# Voice or model to use for TTS (this will depend on the TTS library chosen)
# Valid OpenAI voices: "alloy", "echo", "fable", "onyx", "nova", "shimmer"
TTS_VOICE_MODEL = os.getenv("TTS_VOICE_MODEL", "ash") # Example, changed to a valid default

# --- Feed Generation Configuration (Example) ---
# Default number of news articles to fetch
FEEDS_NEWS_ARTICLE_COUNT = int(os.getenv("FEEDS_NEWS_ARTICLE_COUNT", 5))
# Example News API Key (if using a specific service)
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
# if not NEWS_API_KEY: # Only warn if you plan to use a news service that needs it
#     logger.info("NEWS_API_KEY is not set. Some news feed features might be unavailable.")

# --- Web UI Configuration (Example) ---
WEB_UI_HOST = os.getenv("WEB_UI_HOST", "0.0.0.0")
WEB_UI_PORT = int(os.getenv("WEB_UI_PORT", 8000))

# --- Hardware Configuration (Raspberry Pi - GPIO pins) ---
# These are placeholders and depend on your actual wiring.
# Using BCM numbering convention for GPIO pins.
BUTTON_STOP_ALARM_PIN = int(os.getenv("BUTTON_STOP_ALARM_PIN", 17)) # Set to GPIO 17 for Stop Alarm
BUTTON_SNOOZE_PIN = int(os.getenv("BUTTON_SNOOZE_PIN", 0))         # Disabled
BUTTON_SPEAK_TIME_PIN = int(os.getenv("BUTTON_SPEAK_TIME_PIN", 0))   # Disabled

# --- Alarms Configuration ---
# Defaulting to a path inside /app/data/ for easier Docker volume mounting
# The actual directory /app/data will be created in Dockerfile
ALARMS_FILE_PATH = os.getenv("ALARMS_FILE_PATH", "/app/data/alarms.json")


# Example of how to use these configurations in other modules:
# from wakeupai.config import OPENAI_API_KEY, LOG_LEVEL
# logger.debug(f"OpenAI Key Loaded: {'Yes' if OPENAI_API_KEY else 'No'}") # Can be noisy
# logger.debug(f"Log Level Set To: {LOG_LEVEL}")

if __name__ == '__main__':
    # Setup basic logging for the __main__ test if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO, # Use INFO for testing this module directly
            format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger.info("Basic logging configured for config.py direct test run.")

    logger.info("--- Configuration Settings (as per config.py) ---")
    logger.info(f"OpenAI API Key Loaded: {'Yes' if OPENAI_API_KEY else 'No - WARNING, features will fail.'}")
    logger.info(f"Log Level: {LOG_LEVEL}")
    logger.info(f"TTS Max Duration: {TTS_MAX_DURATION_SECONDS} seconds")
    logger.info(f"TTS Voice Model: {TTS_VOICE_MODEL}")
    logger.info(f"News Article Count: {FEEDS_NEWS_ARTICLE_COUNT}")
    logger.info(f"News API Key Loaded: {'Yes' if NEWS_API_KEY else 'No - INFO (if service used)'}")
    logger.info(f"Web UI Host: {WEB_UI_HOST}")
    logger.info(f"Web UI Port: {WEB_UI_PORT}")
    logger.info(f"Alarms JSON Path: {ALARMS_FILE_PATH}")
    logger.info(f"Button Pins (Stop Alarm, Snooze, Speak Time): {BUTTON_STOP_ALARM_PIN}, {BUTTON_SNOOZE_PIN}, {BUTTON_SPEAK_TIME_PIN}")
    logger.info("-------------------------------------------------")
    logger.info("To test .env loading, ensure a .env file exists in the project root (e.g., e:\\Dev\\WakeUpAI\\.env)")
    logger.info("Example .env content: OPENAI_API_KEY=\"your_key\" LOG_LEVEL=\"DEBUG\"")
