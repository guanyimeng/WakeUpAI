import schedule
import time
import logging
from threading import Thread, Event
from ..wakeupai.feeds import generate_feed_content
from ..wakeupai.tts import text_to_speech_openai
from ..hardware.audio_player import play_audio_file, stop_audio
from ..config import OPENAI_API_KEY
import os
import datetime

logger = logging.getLogger(__name__) 

TEMP_AUDIO_DIR = os.path.join("src", "audio_files", "temp_alarm_audio")
if not os.path.exists(TEMP_AUDIO_DIR):
    try:
        os.makedirs(TEMP_AUDIO_DIR)
        logger.info(f"Created temporary audio directory: {TEMP_AUDIO_DIR}")
    except Exception as e:
        logger.critical(f"Could not create temporary audio directory {TEMP_AUDIO_DIR}: {e}", exc_info=True)
        TEMP_AUDIO_DIR = tempfile.gettempdir()
        logger.warning(f"Using system temp directory as fallback for temp audio: {TEMP_AUDIO_DIR}")

class AlarmTask:
    def __init__(self, alarm_time, name, feed_type="daily_news", feed_options=None):
        self.alarm_time = alarm_time
        self.name = name
        self.feed_type = feed_type
        self.feed_options = feed_options if feed_options is not None else {}
        self.job = None
        self.enabled = True
        self.is_active = False # Indicates if the alarm sound is currently playing or should be playing
        self.stop_event = Event()

    def _generate_and_play_audio(self):
        logger.info(f"--- Processing Triggered Alarm --- Name: '{self.name}' at {self.alarm_time}")
        self.is_active = True
        self.stop_event.clear() # Set flag to Flase

        if not OPENAI_API_KEY:
            logger.error(f"OpenAI API key not configured. Cannot generate feed or speech for alarm '{self.name}'.")
            self._play_default_sound()
            self.is_active = False
            return

        logger.info(f"Generating feed content for '{self.name}' (Type: {self.feed_type}, Options: {self.feed_options})")
        feed_text = generate_feed_content(feed_type=self.feed_type, options=self.feed_options)

        if not feed_text:
            logger.warning(f"Failed to generate feed content for '{self.name}'. Playing a generic sound.")
            self._play_default_sound()
            self.is_active = False
            return

        logger.debug(f"Feed content for '{self.name}' (first 80 chars): '{feed_text[:80]}...'")

        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label_part = "".join(c if c.isalnum() else '_' for c in self.name[:20])
        temp_audio_filename = f"alarm_{safe_label_part}_{timestamp_str}.mp3"
        temp_audio_filepath = os.path.join(TEMP_AUDIO_DIR, temp_audio_filename)

        logger.info(f"Generating speech for '{self.name}' to file: {temp_audio_filepath}")
        tts_success = text_to_speech_openai(text_input=feed_text, output_filepath=temp_audio_filepath)

        if not tts_success:
            logger.warning(f"Failed to generate speech for '{self.name}'. Playing a generic sound.")
            self._play_default_sound()
            self.is_active = False
            return
        
        if self.stop_event.is_set():
            logger.info(f"Stop event received before playing audio for '{self.name}'.")
            self._cleanup_audio_file(temp_audio_filepath)
            self.is_active = False
            return

        logger.info(f"Playing alarm audio for '{self.name}': {temp_audio_filepath}")
        
        playback_success = play_audio_file(
            filepath=temp_audio_filepath, 
            wait_for_completion=True, 
            stop_event=self.stop_event
        )

        if not playback_success:
            # If playback failed OR was stopped by user, this is false.
            # We only play default or log generic failure if it wasn't a user-initiated stop.
            if not self.stop_event.is_set():
                logger.warning(f"Playback failed for '{self.name}' (File: {temp_audio_filepath}) and not due to user stop. Playing default sound if configured.")
                self._play_default_sound() 
            else:
                logger.info(f"Playback for '{self.name}' was stopped by user request.")
        else:
            logger.info(f"Playback finished for '{self.name}'.")

        self._cleanup_audio_file(temp_audio_filepath) # Cleanup in all cases after attempting to play generated audio
        self.is_active = False
        logger.info(f"--- Finished processing alarm: '{self.name}' ---")

    def _play_default_sound(self):
        # This is a fallback, so it should also be interruptible if it's a long sound.
        default_sound_path = os.path.join("src", "default", "Woke Up Cool Today.mp3")
        if os.path.exists(default_sound_path):
            if not self.stop_event.is_set(): # Don't start default if already stopping
                logger.info(f"Playing default alarm sound for '{self.name}'.")
                play_audio_file(
                    filepath=default_sound_path, 
                    wait_for_completion=True, # Make it blocking
                    stop_event=self.stop_event  # Make it stoppable
                )
            else:
                logger.info(f"Skipping default sound for '{self.name}' as stop event is already set.")
        else:
            logger.error(f"Default alarm sound not found at {default_sound_path}")
            
    def _cleanup_audio_file(self, filepath):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.debug(f"Cleaned up temporary audio file: {filepath}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary audio file {filepath}: {e}", exc_info=True)

    def run(self):
        # Run the audio generation and playback in a new thread to keep scheduler responsive
        if not self.is_active: # Prevent multiple concurrent runs for the same alarm if scheduler is too fast
            logger.info(f"Alarm Triggered: {self.name}")
            # self._generate_and_play_audio() # direct call if not threading
            alarm_thread = Thread(target=self._generate_and_play_audio)
            alarm_thread.daemon = True # Allows main program to exit even if threads are running
            alarm_thread.start()
        else:
            logger.info(f"Alarm '{self.name}' is already active. Skipping new trigger.")


    def schedule(self):
        logger.info(f"Scheduling alarm '{self.name}' at {self.alarm_time}")
        self.job = schedule.every().day.at(self.alarm_time).do(self.run)

    def cancel(self):
        if self.job:
            schedule.cancel_job(self.job)
            logger.info(f"Canceled alarm: {self.name}")
        self.stop() # Also ensure any active playback is stopped

    def stop(self):
        logger.info(f"Attempting to stop alarm: {self.name}")
        if self.is_active:
            self.stop_event.set() # Signal the audio playing thread/function to stop
            stop_audio() # Call the global audio stop function
            logger.info(f"Stop signal sent to alarm '{self.name}'.")
        else:
            logger.info(f"Alarm '{self.name}' is not currently active.")


class AlarmScheduler:
    def __init__(self):
        self.alarms = [] # List of AlarmTask objects
        self._scheduler_thread = None
        self._stop_scheduler_event = Event()
        self._active_alarm_tasks = [] # Keep track of tasks that are currently sounding

    def add_alarm(self, alarm_time_str: str, name: str, feed_type: str = "daily_news", feed_options: dict = None):
        try:
            # Validate time format
            datetime.datetime.strptime(alarm_time_str, "%H:%M")
        except ValueError:
            logger.error(f"Invalid time format for alarm '{name}': {alarm_time_str}. Please use HH:MM.")
            return None
            
        task = AlarmTask(alarm_time_str, name, feed_type, feed_options)
        task.schedule()
        self.alarms.append(task)
        logger.info(f"Alarm '{name}' added and scheduled for {alarm_time_str}.")
        return task

    def remove_alarm(self, name: str):
        for task in self.alarms:
            if task.name == name:
                task.cancel()
                self.alarms.remove(task)
                logger.info(f"Alarm '{name}' removed.")
                return
        logger.warning(f"Alarm '{name}' not found for removal.")
        
    def stop_active_alarms(self):
        logger.info("Stopping all active alarms...")
        stopped_any = False
        for task in self.alarms:
            if task.is_active:
                task.stop()
                stopped_any = True
        if not stopped_any:
            logger.info("No alarms were actively sounding.")
        return stopped_any


    def run_pending(self):
        schedule.run_pending()

    def start(self):
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.info("Scheduler is already running.")
            return

        self._stop_scheduler_event.clear()
        self._scheduler_thread = Thread(target=self._run_scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info("Alarm scheduler started.")

    def _run_scheduler_loop(self):
        logger.info("Scheduler thread started.")
        while not self._stop_scheduler_event.is_set():
            self.run_pending()
            time.sleep(1)
        logger.info("Scheduler thread stopped.")

    def stop(self):
        logger.info("Stopping alarm scheduler...")
        self._stop_scheduler_event.set()
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5) # Wait for scheduler thread to finish
            if self._scheduler_thread.is_alive():
                logger.warning("Scheduler thread did not stop in time.")
        self.stop_active_alarms() # Ensure all alarms are stopped
        logger.info("Alarm scheduler and all alarms should be stopped.")

    def list_alarms(self):
        if not self.alarms:
            print("No alarms scheduled.")
            return
        print("Scheduled alarms:")
        for task in self.alarms:
            print(f"- {task.name} at {task.alarm_time} (Next run: {task.job.next_run if task.job else 'N/A'})")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')

    scheduler = AlarmScheduler()

    # Example Alarms
    # Note: For testing, choose times in the near future.
    now = datetime.datetime.now()
    alarm_time_1 = (now + datetime.timedelta(minutes=1)).strftime("%H:%M")
    alarm_time_2 = (now + datetime.timedelta(minutes=2)).strftime("%H:%M")

    scheduler.add_alarm(alarm_time_1, "Morning News Briefing", feed_type="daily_news", feed_options={"country": "US"})
    scheduler.add_alarm(alarm_time_2, "Quick Fact", feed_type="topic_facts", feed_options={"topic": "space exploration"})
    
    scheduler.list_alarms()
    scheduler.start()

    try:
        # Keep the main thread alive to allow scheduler to run
        # Stop after a certain time for testing, or use input() for manual stop
        start_time = time.time()
        # Run for 3 minutes for testing
        while time.time() - start_time < 180: # Run for 3 minutes
            if not scheduler._scheduler_thread or not scheduler._scheduler_thread.is_alive():
                logger.info("Scheduler thread seems to have stopped unexpectedly.")
                break
            time.sleep(5)
            logger.debug(f"Main thread alive. Active alarms: {[t.name for t in scheduler.alarms if t.is_active]}")
            # Example: stop a specific alarm after some time (e.g., if it was triggered)
            # if time.time() - start_time > 70 and scheduler.alarms[0].is_active: # after 70 seconds
            #     print(f"Dev: Manually stopping alarm {scheduler.alarms[0].name} from main test loop")
            #     scheduler.alarms[0].stop()


    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        print("Stopping scheduler...")
        scheduler.stop()
        print("Scheduler stopped. Exiting.")

