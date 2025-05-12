import datetime
import time
import json
import os
import logging

logger = logging.getLogger(__name__)

class Alarm:
    """Represents a single alarm with its properties and states."""
    def __init__(self, alarm_time: datetime.time, label: str, repeat_days: list = None, enabled: bool = True, alarm_id: str = None, feed_type: str = "daily_news", feed_options: dict = None):
        """
        Initializes an Alarm object.

        Args:
            alarm_time (datetime.time): The time the alarm should go off.
            label (str): A descriptive label for the alarm.
            repeat_days (list, optional): A list of integers representing days of the week
                                         (0=Monday, 1=Tuesday, ..., 6=Sunday) for repetition.
                                         Defaults to None (no repetition, one-time alarm).
                                         An empty list also means a one-time alarm.
            enabled (bool, optional): Whether the alarm is currently active. Defaults to True.
            alarm_id (str, optional): A unique identifier for the alarm. Auto-generated if None.
        """
        self.alarm_id = alarm_id if alarm_id else str(time.time()) # Simple unique ID
        self.alarm_time = alarm_time # datetime.time object
        self.label = label
        self.repeat_days = sorted(list(set(repeat_days))) if repeat_days else [] # Ensure unique, sorted list or empty
        self.enabled = enabled
        self.is_snoozing = False
        # Store snooze_until as a timestamp (float) for JSON serialization, or None
        self.snooze_until_timestamp = None
        self.feed_type = feed_type # e.g., "daily_news", "topic_facts", "custom_prompt"
        self.feed_options = feed_options if feed_options is not None else {} # e.g., {"topic": "Space"} or {"prompt": "Tell me a joke"}

    @property
    def snooze_until_datetime(self):
        """Returns the snooze_until_timestamp as a datetime object, or None."""
        if self.snooze_until_timestamp:
            return datetime.datetime.fromtimestamp(self.snooze_until_timestamp)
        return None

    @snooze_until_datetime.setter
    def snooze_until_datetime(self, dt_object: datetime.datetime | None):
        """Sets snooze_until_timestamp from a datetime object."""
        if dt_object:
            self.snooze_until_timestamp = dt_object.timestamp()
        else:
            self.snooze_until_timestamp = None

    def __str__(self):
        repeat_str = "One-time"
        if self.repeat_days:
            days_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            try:
                repeat_str = ", ".join([days_map[day] for day in self.repeat_days])
            except IndexError:
                repeat_str = "Invalid repeat days" # Should not happen with validation
        state = "Enabled" if self.enabled else "Disabled"
        if self.is_snoozing and self.snooze_until_datetime:
            state += f", Snoozing until {self.snooze_until_datetime.strftime('%H:%M:%S')}"
        feed_info = f"Feed: {self.feed_type}"
        if self.feed_options:
            feed_info += f" ({self.feed_options})"
        return f"Alarm ID: {self.alarm_id} - {self.label} at {self.alarm_time.strftime('%H:%M')} ({repeat_str}), State: {state}, {feed_info}"

    def update(self, alarm_time: datetime.time = None, label: str = None, repeat_days: list = None, enabled: bool = None, feed_type: str = None, feed_options: dict = None):
        """Updates alarm properties. Only provided fields are updated."""
        if alarm_time is not None:
            self.alarm_time = alarm_time
        if label is not None:
            self.label = label
        if repeat_days is not None:
            self.repeat_days = sorted(list(set(repeat_days))) if repeat_days else []
        if enabled is not None:
            self.enabled = enabled
            if not enabled: # If disabling, also cancel snooze
                self.is_snoozing = False
                self.snooze_until_datetime = None # Uses the setter
        if feed_type is not None:
            self.feed_type = feed_type
        # For feed_options, if an empty dict is passed, it means clear existing options.
        # If None is passed, it means no change.
        if feed_options is not None: 
            self.feed_options = feed_options
        logger.info(f"Alarm '{self.label}' (ID: {self.alarm_id}) updated.")

    def enable(self):
        """Enables the alarm and resets any snooze state."""
        self.enabled = True
        self.is_snoozing = False
        self.snooze_until_datetime = None # Uses the setter
        logger.info(f"Alarm '{self.label}' (ID: {self.alarm_id}) enabled.")

    def disable(self):
        """Disables the alarm and resets any snooze state."""
        self.enabled = False
        self.is_snoozing = False
        self.snooze_until_datetime = None # Uses the setter
        logger.info(f"Alarm '{self.label}' (ID: {self.alarm_id}) disabled.")

    def snooze(self, minutes: int = 9):
        """
        Snoozes the alarm for a specified number of minutes if it's currently enabled.
        """
        if self.enabled:
            self.is_snoozing = True
            snooze_dt = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            self.snooze_until_datetime = snooze_dt # Uses the setter to store as timestamp
            logger.info(f"Alarm '{self.label}' (ID: {self.alarm_id}) snoozed for {minutes} minutes until {snooze_dt.strftime('%H:%M:%S')}.")
        else:
            logger.warning(f"Cannot snooze alarm '{self.label}' (ID: {self.alarm_id}) as it is not enabled.")

    def to_dict(self) -> dict:
        """Converts the Alarm object to a dictionary for JSON serialization."""
        return {
            "alarm_id": self.alarm_id,
            "alarm_time": self.alarm_time.strftime("%H:%M:%S"), # Store time as string
            "label": self.label,
            "repeat_days": self.repeat_days,
            "enabled": self.enabled,
            "is_snoozing": self.is_snoozing, # Persist current snooze state
            "snooze_until_timestamp": self.snooze_until_timestamp,
            "feed_type": self.feed_type,
            "feed_options": self.feed_options
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Alarm":
        """Creates an Alarm object from a dictionary."""
        alarm_time = datetime.datetime.strptime(data["alarm_time"], "%H:%M:%S").time()
        alarm = cls(
            alarm_time=alarm_time,
            label=data["label"],
            repeat_days=data["repeat_days"],
            enabled=data["enabled"],
            alarm_id=data["alarm_id"],
            # Older data might not have feed_type/feed_options
            feed_type=data.get("feed_type", "daily_news"), 
            feed_options=data.get("feed_options", {})
        )
        alarm.is_snoozing = data.get("is_snoozing", False)
        loaded_snooze_timestamp = data.get("snooze_until_timestamp")
        if loaded_snooze_timestamp is not None:
            alarm.snooze_until_timestamp = loaded_snooze_timestamp # Directly set the timestamp

        # Now, check if the snooze time (if any) has passed.
        # The snooze_until_datetime property will convert the timestamp for comparison.
        if alarm.is_snoozing and alarm.snooze_until_datetime and alarm.snooze_until_datetime < datetime.datetime.now():
            logger.info(f"Snooze time for loaded alarm '{alarm.label}' (ID: {alarm.alarm_id}) has passed. Resetting snooze state.")
            alarm.is_snoozing = False
            alarm.snooze_until_datetime = None # Uses the setter to clear the timestamp
        return alarm

    def should_trigger(self, current_datetime: datetime.datetime) -> bool:
        """
        Checks if the alarm should be triggered based on the current datetime,
        repeat settings, enabled state, and snooze state.
        """
        if not self.enabled:
            return False

        if self.is_snoozing:
            if self.snooze_until_datetime and current_datetime >= self.snooze_until_datetime:
                # Snooze period is over, alarm should sound again.
                self.is_snoozing = False
                self.snooze_until_datetime = None
                return True
            else:
                return False # Still snoozing or snooze time not reached

        # Check if current time matches alarm time (hour and minute)
        if current_datetime.hour == self.alarm_time.hour and current_datetime.minute == self.alarm_time.minute:
            # If no repeat days, it's a one-time alarm (or meant for today only if not handled by manager)
            if not self.repeat_days:
                return True

            # If repeat_days are set, check if today is one of them
            current_day_of_week = current_datetime.weekday() # Monday is 0 and Sunday is 6
            if current_day_of_week in self.repeat_days:
                return True
        return False

class AlarmManager:
    """Manages a collection of alarms."""
    def __init__(self, alarms_file: str = "alarms.json"):
        self.alarms = {} # Dictionary to store alarms, keyed by alarm_id
        self._last_triggered_minute = {} # key: alarm_id, value: (hour, minute) tuple of last trigger
        self.alarms_file = alarms_file
        self.actively_sounding_alarm_ids = set() # Stores IDs of alarms currently being processed (sounded/sounding)
        self.load_alarms()

    def add_alarm_obj(self, alarm: Alarm):
        """Adds an already created Alarm object."""
        if alarm.alarm_id in self.alarms:
            logger.error(f"Alarm with ID {alarm.alarm_id} already exists. Cannot add '{alarm.label}'.")
            return None
        self.alarms[alarm.alarm_id] = alarm
        logger.info(f"Alarm '{alarm.label}' (ID: {alarm.alarm_id}) added.")
        self.save_alarms() # Save after adding
        return alarm

    def create_alarm(self, alarm_time: datetime.time, label: str, repeat_days: list = None, enabled: bool = True, alarm_id: str = None, feed_type: str = "daily_news", feed_options: dict = None) -> Alarm:
        """Creates a new alarm and adds it to the manager."""
        alarm = Alarm(alarm_time, label, repeat_days, enabled, alarm_id, feed_type, feed_options)
        return self.add_alarm_obj(alarm)

    def remove_alarm(self, alarm_id: str):
        """Removes an alarm by its ID."""
        if alarm_id in self.alarms:
            removed_label = self.alarms[alarm_id].label
            del self.alarms[alarm_id]
            if alarm_id in self._last_triggered_minute: # Clean up cache
                del self._last_triggered_minute[alarm_id]
            logger.info(f"Alarm '{removed_label}' (ID: {alarm_id}) removed.")
            self.save_alarms() # Save after removing
        else:
            logger.warning(f"Alarm with ID '{alarm_id}' not found for removal.")

    def update_alarm(self, alarm_id: str, alarm_time: datetime.time = None, label: str = None, repeat_days: list = None, enabled: bool = None, feed_type: str = None, feed_options: dict = None) -> Alarm | None:
        """Updates an existing alarm and saves all alarms."""
        alarm = self.get_alarm(alarm_id)
        if alarm:
            alarm.update(alarm_time=alarm_time, label=label, repeat_days=repeat_days, enabled=enabled, feed_type=feed_type, feed_options=feed_options)
            self.save_alarms() # Save after updating
            return alarm
        else:
            logger.warning(f"Alarm with ID '{alarm_id}' not found for update.")
            return None

    def enable_alarm(self, alarm_id: str):
        alarm = self.get_alarm(alarm_id)
        if alarm:
            alarm.enable() # This already resets snooze
            self.save_alarms()
        else:
            logger.warning(f"Alarm with ID '{alarm_id}' not found for enabling.")

    def disable_alarm(self, alarm_id: str):
        alarm = self.get_alarm(alarm_id)
        if alarm:
            alarm.disable() # This already resets snooze
            self.save_alarms()
        else:
            logger.warning(f"Alarm with ID '{alarm_id}' not found for disabling.")

    def snooze_alarm(self, alarm_id: str, minutes: int = 9):
        alarm = self.get_alarm(alarm_id)
        if alarm:
            if alarm.enabled: # Only snooze if enabled
                alarm.snooze(minutes)
                self.save_alarms()
            else:
                logger.warning(f"Alarm '{alarm.label}' (ID: {alarm_id}) is disabled, cannot snooze.")
        else:
            logger.warning(f"Alarm with ID '{alarm_id}' not found for snoozing.")

    def get_alarm(self, alarm_id: str) -> Alarm | None:
        """Retrieves an alarm by its ID."""
        return self.alarms.get(alarm_id)

    def list_alarms(self):
        """Logs all managed alarms at INFO level. Returns a list of alarm string representations."""
        alarm_strings = []
        if not self.alarms:
            logger.info("No alarms set.")
            return alarm_strings
        # Removed the print statements here, individual alarm logging happens below
        # Consider if a header/footer log for the list is still desired when called externally
        # logger.info("--- All Alarms List --- ") # Example if you want a list header
        for alarm_obj in self.alarms.values(): # Iterate directly over alarm objects
            alarm_str = str(alarm_obj)
            logger.info(alarm_str) # Log each alarm's string representation
            alarm_strings.append(alarm_str)
        # logger.info("--- End of Alarm List ---") # Example if you want a list footer
        return alarm_strings

    def save_alarms(self):
        """Saves all current alarms to the JSON file."""
        data_to_save = [alarm.to_dict() for alarm in self.alarms.values()]
        try:
            with open(self.alarms_file, 'w') as f:
                json.dump(data_to_save, f, indent=4)
            logger.info(f"Alarms successfully saved to {self.alarms_file}")
        except IOError as e:
            logger.error(f"Error saving alarms to {self.alarms_file}", exc_info=True)

    def load_alarms(self):
        """Loads alarms from the JSON file."""
        if not os.path.exists(self.alarms_file):
            logger.info(f"Alarms file {self.alarms_file} not found. Starting with no alarms.")
            return

        try:
            with open(self.alarms_file, 'r') as f:
                alarms_data = json.load(f)
                loaded_count = 0
                for alarm_data in alarms_data:
                    try:
                        alarm = Alarm.from_dict(alarm_data)
                        self.alarms[alarm.alarm_id] = alarm
                        loaded_count += 1
                    except Exception as e: # Catch errors during individual alarm parsing
                        logger.error(f"Error loading an alarm from data: {alarm_data}. Error: {e}", exc_info=True)
            logger.info(f"Alarms loaded from {self.alarms_file}. {loaded_count} of {len(alarms_data) if isinstance(alarms_data, list) else 'N/A'} items processed.")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading alarms from {self.alarms_file}. Starting with no alarms.", exc_info=True)
            self.alarms = {} # Ensure alarms is empty if loading fails
        # After loading, re-evaluate snooze states that might have passed
        now = datetime.datetime.now()
        for alarm_id in list(self.alarms.keys()): # Iterate over a copy of keys for safe modification
            alarm = self.alarms[alarm_id]
            if alarm.is_snoozing and alarm.snooze_until_datetime and alarm.snooze_until_datetime < now:
                logger.info(f"Alarm '{alarm.label}' (ID: {alarm.alarm_id}) snooze time has passed while inactive. Resetting snooze state.")
                alarm.is_snoozing = False
                alarm.snooze_until_datetime = None # Uses setter
                # self.save_alarms() # Optional: save immediately after this auto-correction

    def request_snooze_for_active_alarms(self, minutes: int = 9) -> list[str]:
        """
        Attempts to snooze all alarms currently in the actively_sounding_alarm_ids set.
        These are alarms that have been triggered and are likely making sound or about to.
        Returns a list of labels of alarms for which snooze was activated.
        """
        snoozed_labels = []
        if not self.actively_sounding_alarm_ids:
            logger.info("Snooze requested, but no alarms are currently actively sounding.")
            return snoozed_labels

        logger.info(f"Snooze requested for actively sounding alarms. IDs to check: {self.actively_sounding_alarm_ids}")
        # Iterate over a copy because snoozing might modify states that could affect iteration (though unlikely here)
        for alarm_id in list(self.actively_sounding_alarm_ids):
            alarm = self.get_alarm(alarm_id)
            if alarm and alarm.enabled: # Ensure alarm exists and is enabled
                logger.debug(f"Attempting to snooze active alarm via request: {alarm.label} (ID: {alarm_id})")
                self.snooze_alarm(alarm_id, minutes) # This existing method handles the snooze logic and saving
                snoozed_labels.append(alarm.label)
            elif alarm and not alarm.enabled:
                logger.warning(f"Alarm {alarm.label} (ID: {alarm_id}) is in active set but now disabled. Cannot snooze via request.")
            elif not alarm:
                logger.warning(f"Alarm ID {alarm_id} was in active set but not found in manager during snooze request. Removing from active set.")
                self.actively_sounding_alarm_ids.discard(alarm_id)
        
        if snoozed_labels:
            logger.info(f"Snooze successfully activated via request for: {', '.join(snoozed_labels)}")
        else:
            logger.info("No enabled active alarms were available to snooze via request (or found in active set).")
        return snoozed_labels

    def mark_alarm_processing_complete(self, alarm_id: str):
        """
        Called by the alarm handling loop after an alarm's audio has finished playing
        or if its processing failed. This removes it from the set of actively sounding alarms.
        """
        if alarm_id in self.actively_sounding_alarm_ids:
            logger.debug(f"Marking alarm processing complete for ID: {alarm_id}. Active set: {self.actively_sounding_alarm_ids}")
            self.actively_sounding_alarm_ids.discard(alarm_id)
        else:
            # This might happen if an alarm was removed while it was also in actively_sounding_alarm_ids
            logger.debug(f"Tried to mark {alarm_id} complete, but it wasn't in active set: {self.actively_sounding_alarm_ids}")

    def check_and_trigger_alarms(self,current_datetime_override=None) -> list[Alarm]:
        """
        Checks all managed alarms and returns a list of alarms that should be triggered.
        This method should be called periodically (e.g., every few seconds, or once per minute).
        Handles logic to ensure an alarm only triggers once per minute unless snoozed.
        """
        if current_datetime_override:
            now=current_datetime_override
        else:
            now = datetime.datetime.now()
        current_time_minute_tuple = (now.hour, now.minute)
        triggered_alarms_now = []

        for alarm_id, alarm in self.alarms.items():
            if alarm.should_trigger(now):
                # Check if it already triggered this minute (unless it just came off snooze)
                if not alarm.is_snoozing and self._last_triggered_minute.get(alarm_id) == current_time_minute_tuple:
                    continue # Already triggered for this minute

                print(f"--- ACTION: TRIGGERING ALARM: {alarm.label} (ID: {alarm_id}) ---")
                # Actual sound/feed playing would happen after this function returns,
                # based on the alarms in triggered_alarms_now.
                
                self.actively_sounding_alarm_ids.add(alarm_id)
                triggered_alarms_now.append(alarm)
                self._last_triggered_minute[alarm_id] = current_time_minute_tuple

                # For true one-time alarms (no repeat days), disable them after triggering
                # (unless it was a snooze that just ended, in which case it's not truly "one-time" anymore for this instance)
                if not alarm.repeat_days and alarm.alarm_id not in self.actively_sounding_alarm_ids and not alarm.is_snoozing: # if it just came out of snooze, it has already been snoozed.
                    logger.info(f"Disabling one-time alarm '{alarm.label}' (ID: {alarm.alarm_id}) after triggering.")
                    alarm.disable() # This method now logs its action
            else:
                # If alarm is not triggering now, but was marked as triggered for a *previous* minute, clear that old mark.
                if self._last_triggered_minute.get(alarm_id) and self._last_triggered_minute.get(alarm_id) != current_time_minute_tuple:
                    del self._last_triggered_minute[alarm_id]
        
        return triggered_alarms_now

if __name__ == '__main__':
    # Example Usage:
    alarms_file_path = "test_alarms.json" # Use a test-specific file
    # Clean up old test file if it exists, for a fresh run each time for some tests
    # For testing persistence, you might want to comment out the remove line sometimes
    if os.path.exists(alarms_file_path):
        try:
            os.remove(alarms_file_path)
            # Use a direct print here if logger for __main__ is not set up yet or for clarity in test setup
            print(f"DEBUG (alarm.py __main__): Removed test alarms file: {alarms_file_path}")
        except Exception as e_remove_test_alarms:
            print(f"WARNING (alarm.py __main__): Could not remove test alarms file {alarms_file_path}: {e_remove_test_alarms}")

    # Setup basic logging for the __main__ test if not already configured (e.g. by webui importing this module)
    if not logging.getLogger().handlers: # Check if root logger has handlers
        logging.basicConfig(
            level=logging.DEBUG, # Use DEBUG for testing this module
            format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        # logger instance for this module is already created at the top
        logger.info("Basic logging configured for alarm.py direct test run.")

    manager = AlarmManager(alarms_file=alarms_file_path) # AlarmManager init logs its actions
    # The following print is now redundant as AlarmManager.load_alarms() logs this.
    # logger.info(f"--- Initial alarms count after loading: {len(manager.alarms)} ---")
    manager.list_alarms() # This method now logs each alarm

    # Create alarms - use specific IDs to test persistence and avoid duplicates on re-runs
    news_alarm_id = "news_alarm_001"
    checkin_alarm_id = "checkin_alarm_002"
    
    # Storing original alarm times for printout, as they might be updated.
    original_news_alarm_time_str = ""
    original_checkin_alarm_time_str = ""

    # Create alarms - these actions are logged by the manager methods
    if not manager.get_alarm(news_alarm_id):
        plus_1_min = (datetime.datetime.now() + datetime.timedelta(minutes=1)).time().replace(second=0, microsecond=0)
        original_news_alarm_time_str = plus_1_min.strftime('%H:%M')
        manager.create_alarm(alarm_time=plus_1_min, label="Morning News", repeat_days=[0, 1, 2, 3, 4], alarm_id=news_alarm_id, feed_type="daily_news", feed_options={"country": "world"})
    else:
        existing_alarm = manager.get_alarm(news_alarm_id)
        if existing_alarm:
            original_news_alarm_time_str = existing_alarm.alarm_time.strftime('%H:%M')

    if not manager.get_alarm(checkin_alarm_id):
        plus_2_min = (datetime.datetime.now() + datetime.timedelta(minutes=2)).time().replace(second=0, microsecond=0)
        original_checkin_alarm_time_str = plus_2_min.strftime('%H:%M')
        manager.create_alarm(alarm_time=plus_2_min, label="Custom Fun Fact", alarm_id=checkin_alarm_id, feed_type="topic_facts", feed_options={"topic": "funfact about birds"})
    else:
        existing_alarm = manager.get_alarm(checkin_alarm_id)
        if existing_alarm:
             original_checkin_alarm_time_str = existing_alarm.alarm_time.strftime('%H:%M')

    manager.list_alarms() # This method now logs each alarm

    # Test updating an alarm
    if manager.get_alarm(news_alarm_id):
        logger.info(f"\n--- Test: Updating '{news_alarm_id}' (Morning News -> Daily Briefing, feed to US news) ---")
        new_time_3_min = (datetime.datetime.now() + datetime.timedelta(minutes=3)).time().replace(second=0, microsecond=0)
        original_news_alarm_time_str = new_time_3_min.strftime('%H:%M')
        manager.update_alarm(news_alarm_id, alarm_time=new_time_3_min, label="Daily Briefing", enabled=True, feed_type="daily_news", feed_options={"country": "US"})
        # updated_alarm = manager.get_alarm(news_alarm_id) # Alarm object is logged by list_alarms or directly if needed
        # logger.info(f"After update: {updated_alarm}")

    # Test disabling/enabling using manager methods
    if manager.get_alarm(checkin_alarm_id):
        logger.info(f"\n--- Test: Toggling '{checkin_alarm_id}' ---")
        # logger.info(f"Original state: {manager.get_alarm(checkin_alarm_id)}") # The methods themselves log actions
        manager.disable_alarm(checkin_alarm_id)
        manager.enable_alarm(checkin_alarm_id)

    logger.info("\n--- Test: Starting alarm check loop (simulated) ---")
    logger.info(f"Current time for test: {datetime.datetime.now().strftime('%H:%M:%S')}")
    # Alarms details are logged by list_alarms above, or by individual create/update calls.

    try:
        for i in range(36): # Simulate checking every 5 seconds for 3 minutes
            logger.debug(f"Test Loop {i+1} - Time: {datetime.datetime.now().strftime('%H:%M:%S')}")
            triggered_alarms = manager.check_and_trigger_alarms() # This method logs when it finds alarms
            
            if triggered_alarms:
                for triggered_alarm in triggered_alarms:
                    logger.info(f"  -> Test Main loop: Indication that '{triggered_alarm.label}' (ID: {triggered_alarm.alarm_id}) is ringing!")
                    # Actual processing (feed, tts, play) would happen in the main app's loop using alarm_handler.
                    # For this direct test of alarm.py, we just note it would trigger.
                    if triggered_alarm.alarm_id == news_alarm_id and triggered_alarm.enabled:
                        snooze_this_alarm = True # Assume we want to test snoozing it
                        if triggered_alarm.is_snoozing:
                            if triggered_alarm.snooze_until_datetime and datetime.datetime.now() < triggered_alarm.snooze_until_datetime:
                                snooze_this_alarm = False 
                        
                        if snooze_this_alarm:
                            logger.info(f"  -> Test: Simulating snooze for '{triggered_alarm.label}' (ID: {triggered_alarm.alarm_id}) for 1 minute via manager.")
                            manager.snooze_alarm(triggered_alarm.alarm_id, minutes=1) 
                        elif triggered_alarm.is_snoozing : 
                            logger.debug(f"  -> Test: '{triggered_alarm.label}' is already snoozing. Snooze ends at {triggered_alarm.snooze_until_datetime.strftime('%H:%M:%S') if triggered_alarm.snooze_until_datetime else 'N/A'}")
            
            # Check if all test alarms are now disabled (e.g. one-time alarms that triggered and were disabled)
            all_disabled = True
            for alarm_obj_id in [news_alarm_id, checkin_alarm_id]:
                alarm_to_check = manager.get_alarm(alarm_obj_id)
                if alarm_to_check and alarm_to_check.enabled:
                    all_disabled = False
                    break
            if all_disabled and len(manager.alarms) > 0: # Ensure there were alarms to begin with
                logger.info("All test alarms are now disabled (likely one-time alarms triggered). Exiting test loop.")
                break
            if not manager.alarms:
                logger.info("No alarms left to check. Exiting test loop.")
                break

            time.sleep(5) # Check every 5 seconds
    except KeyboardInterrupt:
        logger.info("\nAlarm check test loop interrupted by user.")
    finally:
        logger.info("\n--- Test: Final Alarm States ---")
        manager.list_alarms()
