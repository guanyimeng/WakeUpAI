# e:\Dev\WakeUpAI\wakeupai\webui.py
import os
import datetime
import time
import threading # For the background alarm checking thread
import atexit # To handle cleanup on exit
import logging # Added for logging
from flask import Flask, render_template, request, redirect, url_for, flash

from wakeupai.alarm import AlarmManager, Alarm
from wakeupai.config import (
    ALARMS_FILE_PATH, WEB_UI_HOST, WEB_UI_PORT, OPENAI_API_KEY,
    BUTTON_ENABLE_DISABLE_PIN, BUTTON_SNOOZE_PIN, BUTTON_SPEAK_TIME_PIN # For hardware setup check
)
from wakeupai.feeds import FEED_GENERATORS
from wakeupai.tts import text_to_speech_openai
from wakeupai.audio_player import play_audio_file
from wakeupai.alarm_handler import process_single_triggered_alarm, TEMP_AUDIO_DIR
from wakeupai.hardware import HardwareManager, IS_RASPBERRY_PI

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24) # Needed for flash messages

# --- Logging Setup ---
# Get log level from config, default to INFO if not set or invalid
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
if log_level_str not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    log_level_str = "INFO"
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__) # Create a logger for this module (webui)
# You can also get the root logger: logging.getLogger()
# Flask's app.logger will also use this basicConfig if not configured separately.

logger.info(f"Logging initialized with level: {log_level_str}")

# Initialize core components
alarm_manager = AlarmManager(alarms_file=ALARMS_FILE_PATH)

# --- TTS and Playback Function for Hardware Manager and direct calls ---
def speak_text_via_tts_and_play(text: str, lang: str = "en") -> bool:
    """
    Generates speech from text using OpenAI TTS and plays it.
    Uses a temporary file for the audio.
    Args:
        text (str): The text to speak.
        lang (str): Language code (OpenAI TTS generally auto-detects or uses context from text).
    Returns:
        bool: True if successful, False otherwise.
    """
    if not text:
        print("SpeakText: No text provided.")
        return False
    if not OPENAI_API_KEY:
        print("SpeakText: OpenAI API key not configured. Cannot speak text.")
        # Optionally play a local "error" sound if this happens
        return False

    try:
        # Create a unique filename for the temporary audio output
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        temp_filename = f"speech_output_{timestamp_str}.mp3"
        temp_filepath = os.path.join(TEMP_AUDIO_DIR, temp_filename) # Use the same temp dir as alarm_handler

        print(f"SpeakText: Generating speech for: '{text[:50]}...' to {temp_filepath}")
        tts_success = text_to_speech_openai(text_input=text, output_filepath=temp_filepath)

        if not tts_success:
            print("SpeakText: TTS generation failed.")
            return False

        print(f"SpeakText: Playing audio: {temp_filepath}")
        playback_success = play_audio_file(temp_filepath, wait_for_completion=True)

        # Cleanup temporary file
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
                print(f"SpeakText: Cleaned up temp audio file {temp_filepath}")
            except Exception as e_remove:
                print(f"SpeakText: Error removing temp audio file {temp_filepath}: {e_remove}")
        
        return playback_success
    except Exception as e:
        print(f"SpeakText: Error in speak_text_via_tts_and_play: {e}")
        return False

hardware_manager = HardwareManager(alarm_manager=alarm_manager, tts_speak_function=speak_text_via_tts_and_play)

# --- Background Alarm Checking Thread --- 
shutdown_event = threading.Event()
ALARM_CHECK_INTERVAL_SECONDS = 10 # Check for alarms every 10 seconds

def alarm_checking_loop():
    """Periodically checks for and processes triggered alarms."""
    print("Alarm checking loop started.")
    while not shutdown_event.is_set():
        try:
            # print(f"DEBUG: Alarm loop check at {datetime.datetime.now().strftime('%H:%M:%S')}") # Verbose
            # The system_enabled flag from hardware_manager controls actual sound playback in process_single_triggered_alarm
            current_system_enabled_status = getattr(hardware_manager, 'system_enabled', True)
            
            triggered_alarms = alarm_manager.check_and_trigger_alarms()
            if triggered_alarms:
                print(f"AlarmChecker: Found {len(triggered_alarms)} alarm(s) to trigger.")
            
            for alarm_instance in triggered_alarms:
                if shutdown_event.is_set(): break # Check again before processing long alarm
                print(f"AlarmChecker: Processing '{alarm_instance.label}'")
                try:
                    process_single_triggered_alarm(alarm_instance, system_is_enabled=current_system_enabled_status)
                except Exception as e_process:
                    print(f"AlarmChecker: Error processing alarm {alarm_instance.alarm_id} ('{alarm_instance.label}'): {e_process}")
                finally:
                    # Always mark processing as complete for this alarm, even if it failed,
                    # so it's removed from the actively_sounding_alarm_ids set.
                    alarm_manager.mark_alarm_processing_complete(alarm_instance.alarm_id)
                    print(f"AlarmChecker: Finished processing attempt for '{alarm_instance.label}'. Active alarms: {alarm_manager.actively_sounding_alarm_ids}")
                
                if shutdown_event.is_set(): break # Check after processing
        except Exception as e_loop:
            print(f"AlarmChecker: Error in alarm checking loop: {e_loop}")
            # Avoid rapid failing loops, wait a bit before retrying on major error
            shutdown_event.wait(ALARM_CHECK_INTERVAL_SECONDS * 2) 
        
        # Wait for the next check interval or until shutdown is signaled
        shutdown_event.wait(ALARM_CHECK_INTERVAL_SECONDS)
    print("Alarm checking loop stopped.")

# Helper to parse form data for days of the week
def parse_repeat_days(form_data):
    return sorted([int(day) for day in form_data.getlist("repeat_days")])

@app.route("/")
def index():
    """Display all alarms and a form to add a new one."""
    alarms = sorted(alarm_manager.alarms.values(), key=lambda x: x.alarm_time)
    available_feed_types = list(FEED_GENERATORS.keys())
    # For simplicity, we won't pass all feed options structures here yet
    # That would require more complex form generation on the frontend.
    return render_template("index.html", 
                           alarms=alarms, 
                           available_feed_types=available_feed_types, 
                           openai_configured=bool(OPENAI_API_KEY))

@app.route("/add_alarm", methods=["POST"])
def add_alarm():
    """Process the new alarm form."""
    try:
        alarm_time_str = request.form["alarm_time"]
        alarm_time_obj = datetime.datetime.strptime(alarm_time_str, "%H:%M").time()
        label = request.form["label"]
        repeat_days = parse_repeat_days(request.form)
        feed_type = request.form.get("feed_type", "daily_news")
        feed_options = {}
        if feed_type == "daily_news":
            feed_options["country"] = request.form.get("feed_option_news_country", "world")
        elif feed_type == "topic_facts":
            topic = request.form.get("feed_option_topic")
            if not topic:
                flash("Topic is required for 'topic_facts' feed type.", "error")
                return redirect(url_for("index"))
            feed_options["topic"] = topic
        elif feed_type == "custom_prompt":
            prompt = request.form.get("feed_option_custom_prompt")
            if not prompt:
                flash("Prompt is required for 'custom_prompt' feed type.", "error")
                return redirect(url_for("index"))
            feed_options["prompt"] = prompt

        alarm_manager.create_alarm(
            alarm_time=alarm_time_obj,
            label=label,
            repeat_days=repeat_days,
            enabled=True, # New alarms are enabled by default
            feed_type=feed_type,
            feed_options=feed_options
        )
        flash(f"Alarm '{label}' added successfully!", "success")
    except ValueError as e:
        logger.error(f"Error adding alarm for label '{request.form.get('label', 'N/A')}' due to ValueError: {e}", exc_info=True)
        flash(f"Error adding alarm: Invalid time format or data. Details: {e}", "error")
    except Exception as e:
        logger.error(f"An unexpected error occurred while adding alarm for label '{request.form.get('label', 'N/A')}': {e}", exc_info=True)
        flash(f"An unexpected error occurred: {e}", "error")
    return redirect(url_for("index"))

@app.route("/edit_alarm/<alarm_id>", methods=["GET", "POST"])
def edit_alarm(alarm_id):
    """Display a form to edit an alarm and process the update."""
    alarm = alarm_manager.get_alarm(alarm_id)
    if not alarm:
        flash(f"Alarm with ID {alarm_id} not found.", "error")
        return redirect(url_for("index"))

    available_feed_types = list(FEED_GENERATORS.keys())

    if request.method == "POST":
        try:
            alarm_time_str = request.form["alarm_time"]
            alarm_time_obj = datetime.datetime.strptime(alarm_time_str, "%H:%M").time()
            label = request.form["label"]
            repeat_days = parse_repeat_days(request.form)
            enabled = "enabled" in request.form
            feed_type = request.form.get("feed_type", alarm.feed_type)
            feed_options = {}

            if feed_type == "daily_news":
                feed_options["country"] = request.form.get("feed_option_news_country", alarm.feed_options.get("country", "world"))
            elif feed_type == "topic_facts":
                topic = request.form.get("feed_option_topic", alarm.feed_options.get("topic"))
                if not topic:
                    flash("Topic is required for 'topic_facts' feed type.", "error")
                    return render_template("edit_alarm.html", alarm=alarm, available_feed_types=available_feed_types, openai_configured=bool(OPENAI_API_KEY))
                feed_options["topic"] = topic
            elif feed_type == "custom_prompt":
                prompt = request.form.get("feed_option_custom_prompt", alarm.feed_options.get("prompt"))
                if not prompt:
                    flash("Prompt is required for 'custom_prompt' feed type.", "error")
                    return render_template("edit_alarm.html", alarm=alarm, available_feed_types=available_feed_types, openai_configured=bool(OPENAI_API_KEY))
                feed_options["prompt"] = prompt
            
alarm_manager.update_alarm(
                alarm_id,
                alarm_time=alarm_time_obj,
                label=label,
                repeat_days=repeat_days,
                enabled=enabled,
                feed_type=feed_type,
                feed_options=feed_options
            )
            flash(f"Alarm '{label}' updated successfully!", "success")
            return redirect(url_for("index"))
        except ValueError as e:
            logger.error(f"Error updating alarm {alarm_id} ('{alarm.label if alarm else 'N/A'}') due to ValueError: {e}", exc_info=True)
            flash(f"Error updating alarm: Invalid time format or data. Details: {e}", "error")
        except Exception as e:
            logger.error(f"An unexpected error occurred while updating alarm {alarm_id} ('{alarm.label if alarm else 'N/A'}'): {e}", exc_info=True)
            flash(f"An unexpected error occurred while updating: {e}", "error")
        # If error, fall through to re-render the edit form with current alarm data
    
    return render_template("edit_alarm.html", alarm=alarm, available_feed_types=available_feed_types, openai_configured=bool(OPENAI_API_KEY))

@app.route("/delete_alarm/<alarm_id>", methods=["POST"])
def delete_alarm(alarm_id):
    """Delete an alarm."""
    alarm = alarm_manager.get_alarm(alarm_id)
    if alarm:
        # AlarmManager.remove_alarm logs its own success/failure at INFO/WARNING
        alarm_manager.remove_alarm(alarm_id)
        flash(f"Alarm '{alarm.label}' deleted successfully attempt initiated.", "success") # Message implies attempt
    else:
        logger.warning(f"Attempt to delete non-existent alarm with ID {alarm_id}.")
        flash(f"Alarm with ID {alarm_id} not found for deletion.", "error")
    return redirect(url_for("index"))

@app.route("/toggle_alarm/<alarm_id>", methods=["POST"])
def toggle_alarm(alarm_id):
    """Enable or disable an alarm."""
    alarm = alarm_manager.get_alarm(alarm_id)
    if alarm:
        if alarm.enabled:
            alarm_manager.disable_alarm(alarm_id)
            # AlarmManager methods log their own actions
            alarm_manager.disable_alarm(alarm_id)
            flash(f"Alarm '{alarm.label}' disabled.", "info")
        else:
            alarm_manager.enable_alarm(alarm_id)
            flash(f"Alarm '{alarm.label}' enabled.", "info")
    else:
        logger.warning(f"Attempt to toggle non-existent alarm with ID {alarm_id}.")
        flash(f"Alarm with ID {alarm_id} not found for toggle.", "error")
    return redirect(url_for("index"))

# Note: A dedicated /snooze_alarm/<alarm_id> route is tricky without knowing if an alarm is actively ringing 
# from the web UI's perspective. Snoozing is primarily handled by the alarm checking loop and hardware.
# We can add a button to the UI that, if an alarm *is* ringing (state not easily known here), could
# conceptually call a snooze method if the backend supported such an interaction for a *currently* ringing alarm.

def run_webui():
    """Runs the Flask development server."""
    # In a production Docker environment, you'd use a proper WSGI server like Gunicorn.
    # Example: poetry run gunicorn -w 4 -b 0.0.0.0:8000 wakeupai.webui:app
    # The Dockerfile CMD will need to be updated for this.
    logger.info(f"Starting Flask web UI on http://{WEB_UI_HOST}:{WEB_UI_PORT}")
    # Set debug=False for production or when running with Gunicorn
    # use_reloader=False is important when running background threads managed by the app itself,
    # otherwise, Flask's reloader might start the thread twice or cause issues.
    app.run(host=WEB_UI_HOST, port=WEB_UI_PORT, debug=False, use_reloader=False)

def cleanup_on_exit():
    logger.info("Application exiting. Cleaning up...")
    shutdown_event.set() # Signal the alarm checking thread to stop
    if hasattr(alarm_thread, 'is_alive') and alarm_thread.is_alive():
        logger.info("Waiting for alarm checking thread to finish...")
        alarm_thread.join(timeout=ALARM_CHECK_INTERVAL_SECONDS + 5) # Wait a bit longer than interval
        if alarm_thread.is_alive():
            logger.warning("Alarm thread did not stop in time.")
    
    if IS_RASPBERRY_PI or (isinstance(hardware_manager.GPIO, object) and hardware_manager.GPIO.__class__.__name__ == 'MockGPIO'):
         # Only call cleanup if GPIO was likely initialized (real or mock)
        if hardware_manager and hasattr(hardware_manager, 'cleanup_gpio')):
            hardware_manager.cleanup_gpio() # This method should have its own logging
    logger.info("Cleanup complete. Goodbye.")

# Register cleanup function to be called on exit
atexit.register(cleanup_on_exit)


if __name__ == "__main__":
    logger.info("--- WakeUpAI Application Starting ---")
    # Setup hardware buttons
    if IS_RASPBERRY_PI:
        logger.info("Attempting to set up GPIO for hardware buttons...")
        if BUTTON_ENABLE_DISABLE_PIN > 0 or BUTTON_SNOOZE_PIN > 0 or BUTTON_SPEAK_TIME_PIN > 0:
            hardware_manager.setup_gpio() # This method should have its own logging
        else:
            logger.warning("No valid GPIO pins configured for buttons in config.py. Hardware buttons will not function.")
    else:
        logger.info("Not on a Raspberry Pi, or RPi.GPIO not available. Hardware buttons will use MockGPIO if pins are configured.")
        if hasattr(hardware_manager, 'GPIO') and isinstance(hardware_manager.GPIO, object) and hardware_manager.GPIO.__class__.__name__ == 'MockGPIO':
            if BUTTON_ENABLE_DISABLE_PIN > 0 or BUTTON_SNOOZE_PIN > 0 or BUTTON_SPEAK_TIME_PIN > 0:
                 hardware_manager.setup_gpio() # This method should have its own logging
            else:
                 logger.info("No pins configured for MockGPIO in config, manual trigger via GPIO.trigger_event() in code needed for testing mock HW.")

    # Start the alarm checking thread
    alarm_thread = threading.Thread(target=alarm_checking_loop, daemon=True)
    alarm_thread.start()

    # Create dummy templates if they don't exist for basic testing without full HTML
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    
    dummy_index_html = os.path.join(template_dir, "index.html")
    if not os.path.exists(dummy_index_html):
        with open(dummy_index_html, "w") as f:
            f.write("<h1>WakeUpAI Alarms (Dummy Index)</h1><p>{{ alarms|length }} alarm(s).</p><p><a href='/edit_alarm/some_id_that_might_not_exist'>Dummy Edit Link (will fail if no such alarm)</a></p>")
            print(f"Created dummy {dummy_index_html}")

    dummy_edit_html = os.path.join(template_dir, "edit_alarm.html")
    if not os.path.exists(dummy_edit_html):
        with open(dummy_edit_html, "w") as f:
            f.write("<h1>Edit Alarm (Dummy)</h1><p>Alarm: {{ alarm.label }}</p>")
            print(f"Created dummy {dummy_edit_html}")

    run_webui()
