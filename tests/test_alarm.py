# e:\Dev\WakeUpAI\tests\test_alarm.py
import unittest
import os
import datetime
import time
import json
from unittest.mock import patch, MagicMock

# Adjust the path if necessary to import from the wakeupai package
# This assumes tests are run from the project root or wakeupai is in PYTHONPATH
from wakeupai.alarm import Alarm, AlarmManager

# Test alarms file path
TEST_ALARMS_FILE = "test_alarms_unit.json"

class TestAlarmClass(unittest.TestCase):
    """Tests for the Alarm class."""

    def test_alarm_creation_defaults(self):
        """Test basic alarm creation and default values."""
        now = datetime.datetime.now()
        alarm_time = now.time()
        alarm = Alarm(alarm_time=alarm_time, label="Test Default")
        self.assertEqual(alarm.alarm_time, alarm_time)
        self.assertEqual(alarm.label, "Test Default")
        self.assertEqual(alarm.repeat_days, [])
        self.assertTrue(alarm.enabled)
        self.assertFalse(alarm.is_snoozing)
        self.assertIsNone(alarm.snooze_until_datetime)
        self.assertEqual(alarm.feed_type, "daily_news")
        self.assertEqual(alarm.feed_options, {})
        self.assertIsNotNone(alarm.alarm_id)

    def test_alarm_creation_custom(self):
        """Test alarm creation with custom values."""
        alarm_time = datetime.time(8, 30)
        label = "Morning Yoga"
        repeat = [0, 2, 4] # Mon, Wed, Fri
        feed_type = "custom_prompt"
        feed_options = {"prompt": "Yoga time!"}
        alarm = Alarm(
            alarm_time=alarm_time, 
            label=label, 
            repeat_days=repeat, 
            enabled=False,
            feed_type=feed_type,
            feed_options=feed_options,
            alarm_id="yoga123"
        )
        self.assertEqual(alarm.alarm_time, alarm_time)
        self.assertEqual(alarm.label, label)
        self.assertEqual(alarm.repeat_days, sorted(repeat))
        self.assertFalse(alarm.enabled)
        self.assertEqual(alarm.feed_type, feed_type)
        self.assertEqual(alarm.feed_options, feed_options)
        self.assertEqual(alarm.alarm_id, "yoga123")

    def test_alarm_to_from_dict_serialization(self):
        """Test serialization to and from dictionary."""
        alarm_time_obj = datetime.time(10, 0, 0)
        alarm1 = Alarm(
            alarm_time=alarm_time_obj,
            label="Test Dict",
            repeat_days=[1, 3],
            enabled=True,
            feed_type="topic_facts",
            feed_options={"topic": "Python"},
            alarm_id="dict_test_1"
        )
        alarm1.snooze(10) # Snooze it to test snooze_until_timestamp serialization
        snooze_ts_before = alarm1.snooze_until_timestamp

        alarm_dict = alarm1.to_dict()

        expected_dict = {
            "alarm_id": "dict_test_1",
            "alarm_time": "10:00:00",
            "label": "Test Dict",
            "repeat_days": [1, 3],
            "enabled": True,
            "is_snoozing": True, # Snoozing was set
            "snooze_until_timestamp": snooze_ts_before,
            "feed_type": "topic_facts",
            "feed_options": {"topic": "Python"}
        }
        self.assertEqual(alarm_dict, expected_dict)

        alarm2 = Alarm.from_dict(alarm_dict)
        self.assertEqual(alarm2.alarm_id, alarm1.alarm_id)
        self.assertEqual(alarm2.alarm_time, alarm1.alarm_time)
        self.assertEqual(alarm2.label, alarm1.label)
        self.assertEqual(alarm2.repeat_days, alarm1.repeat_days)
        self.assertEqual(alarm2.enabled, alarm1.enabled)
        # Snooze state should be re-evaluated by from_dict if time has passed
        # For this direct test, if snooze_until_timestamp is in future, is_snoozing should be True
        # If snooze_until_timestamp was in the past, from_dict should reset is_snoozing
        if snooze_ts_before and snooze_ts_before > time.time():
            self.assertEqual(alarm2.is_snoozing, alarm1.is_snoozing)
            self.assertEqual(alarm2.snooze_until_timestamp, alarm1.snooze_until_timestamp)
        else: # Snooze time has passed during test execution or was None
            self.assertFalse(alarm2.is_snoozing) # Should be reset
            self.assertIsNone(alarm2.snooze_until_datetime) # Should be reset
        
        self.assertEqual(alarm2.feed_type, alarm1.feed_type)
        self.assertEqual(alarm2.feed_options, alarm1.feed_options)

    def test_alarm_should_trigger_one_time(self):
        """Test should_trigger for a one-time alarm."""
        alarm_time = (datetime.datetime.now() + datetime.timedelta(minutes=1)).time().replace(second=0, microsecond=0)
        alarm = Alarm(alarm_time=alarm_time, label="One Time Test")
        
        current_time_trigger = datetime.datetime.now().replace(hour=alarm_time.hour, minute=alarm_time.minute, second=0, microsecond=0)
        current_time_no_trigger_min_before = current_time_trigger - datetime.timedelta(minutes=1)
        current_time_no_trigger_min_after = current_time_trigger + datetime.timedelta(minutes=1)
        current_time_no_trigger_sec_after = current_time_trigger + datetime.timedelta(seconds=5)

        self.assertTrue(alarm.should_trigger(current_time_trigger))
        self.assertFalse(alarm.should_trigger(current_time_no_trigger_min_before))
        # For one-time, it should ideally only trigger at the exact minute. 
        # The AlarmManager handles disabling it post-trigger.
        self.assertFalse(alarm.should_trigger(current_time_no_trigger_min_after))
        self.assertTrue(alarm.should_trigger(current_time_no_trigger_sec_after)) # Still true within the same minute

        alarm.enabled = False
        self.assertFalse(alarm.should_trigger(current_time_trigger))

    def test_alarm_should_trigger_repeating(self):
        """Test should_trigger for a repeating alarm."""
        # Trigger on Monday at 09:00
        alarm_time = datetime.time(9, 0)
        alarm = Alarm(alarm_time=alarm_time, label="Repeating Test", repeat_days=[0]) # 0 = Monday

        # Monday 09:00:00 -> Should trigger
        monday_trigger = datetime.datetime(2025, 5, 12, 9, 0, 0) # May 12, 2025 is a Monday
        self.assertTrue(alarm.should_trigger(monday_trigger))

        # Monday 09:00:30 -> Should trigger (same minute)
        monday_trigger_secs = datetime.datetime(2025, 5, 12, 9, 0, 30)
        self.assertTrue(alarm.should_trigger(monday_trigger_secs))
        
        # Monday 08:59:00 -> Should NOT trigger
        monday_no_trigger_before = datetime.datetime(2025, 5, 12, 8, 59, 0)
        self.assertFalse(alarm.should_trigger(monday_no_trigger_before))

        # Monday 09:01:00 -> Should NOT trigger (past minute)
        monday_no_trigger_after = datetime.datetime(2025, 5, 12, 9, 1, 0)
        self.assertFalse(alarm.should_trigger(monday_no_trigger_after))

        # Tuesday 09:00:00 -> Should NOT trigger (wrong day)
        tuesday_no_trigger = datetime.datetime(2025, 5, 13, 9, 0, 0) # May 13, 2025 is a Tuesday
        self.assertFalse(alarm.should_trigger(tuesday_no_trigger))

    def test_alarm_should_trigger_snooze(self):
        """Test should_trigger with snooze functionality."""
        alarm_time = (datetime.datetime.now() + datetime.timedelta(minutes=5)).time().replace(second=0, microsecond=0)
        alarm = Alarm(alarm_time=alarm_time, label="Snooze Test")
        
        # Simulate time is now the alarm time
        current_alarm_time = datetime.datetime.now().replace(hour=alarm_time.hour, minute=alarm_time.minute, second=0, microsecond=0)
        self.assertTrue(alarm.should_trigger(current_alarm_time), "Should trigger initially")

        # Snooze the alarm for 9 minutes
        alarm.snooze(minutes=9)
        self.assertTrue(alarm.is_snoozing)
        self.assertIsNotNone(alarm.snooze_until_datetime)
        
        # During snooze period, it should not trigger
        time_during_snooze = current_alarm_time + datetime.timedelta(minutes=1)
        self.assertFalse(alarm.should_trigger(time_during_snooze), "Should not trigger during snooze")

        # After snooze period, it should trigger again at the original alarm time if current time matches
        # or, more accurately, when current time is >= snooze_until_datetime
        time_after_snooze_exact = alarm.snooze_until_datetime
        time_after_snooze_passed = alarm.snooze_until_datetime + datetime.timedelta(seconds=30)
        
        self.assertTrue(alarm.should_trigger(time_after_snooze_exact), "Should trigger exactly when snooze ends")
        self.assertFalse(alarm.is_snoozing, "is_snoozing should be false after snooze period ends and checked")
        
        # Check again with time_after_snooze_passed, alarm should have been reset from snoozing by previous check
        alarm.snooze(minutes=1) # Re-snooze to test again
        self.assertTrue(alarm.is_snoozing)
        self.assertTrue(alarm.should_trigger(time_after_snooze_passed), "Should trigger after snooze period passed")
        self.assertFalse(alarm.is_snoozing, "is_snoozing should be false after snooze period passed and checked")

    def test_alarm_snooze_when_disabled(self):
        alarm = Alarm(alarm_time=datetime.time(7,0), label="Disabled Snooze Test", enabled=False)
        alarm.snooze(5)
        self.assertFalse(alarm.is_snoozing)
        self.assertIsNone(alarm.snooze_until_datetime)

    def test_alarm_update(self):
        alarm = Alarm(alarm_time=datetime.time(7,0), label="Update Test", repeat_days=[0], feed_type="daily_news")
        new_time = datetime.time(8,0)
        new_label = "Updated Label"
        new_repeat = [1,2]
        new_feed_type = "topic_facts"
        new_feed_options = {"topic": "cats"}

        alarm.update(
            alarm_time=new_time, 
            label=new_label, 
            repeat_days=new_repeat, 
            enabled=False,
            feed_type=new_feed_type,
            feed_options=new_feed_options
        )
        self.assertEqual(alarm.alarm_time, new_time)
        self.assertEqual(alarm.label, new_label)
        self.assertEqual(alarm.repeat_days, new_repeat)
        self.assertFalse(alarm.enabled)
        self.assertEqual(alarm.feed_type, new_feed_type)
        self.assertEqual(alarm.feed_options, new_feed_options)

        # Test that disabling also resets snooze
        alarm.update(enabled=True)
        alarm.snooze(5)
        self.assertTrue(alarm.is_snoozing)
        alarm.update(enabled=False)
        self.assertFalse(alarm.is_snoozing)
        self.assertIsNone(alarm.snooze_until_datetime)

class TestAlarmManagerClass(unittest.TestCase):
    """Tests for the AlarmManager class."""

    def setUp(self):
        """Set up for each test method."""
        # Ensure a clean slate for alarms file if it exists
        if os.path.exists(TEST_ALARMS_FILE):
            os.remove(TEST_ALARMS_FILE)
        self.alarm_manager = AlarmManager(alarms_file=TEST_ALARMS_FILE)
        # Ensure logging doesn't clutter test output too much, can be set to WARNING or ERROR
        # logging.getLogger('wakeupai.alarm').setLevel(logging.WARNING) 

    def tearDown(self):
        """Clean up after each test method."""
        if os.path.exists(TEST_ALARMS_FILE):
            try:
                os.remove(TEST_ALARMS_FILE)
            except OSError as e:
                print(f"Error removing test alarms file {TEST_ALARMS_FILE}: {e}")
        # Restore logging level if changed
        # logging.getLogger('wakeupai.alarm').setLevel(logging.INFO) 

    def test_create_and_get_alarm(self):
        alarm_time = datetime.time(7, 0)
        alarm = self.alarm_manager.create_alarm(alarm_time, "Test Alarm 1", alarm_id="test1")
        self.assertIsNotNone(alarm)
        self.assertEqual(len(self.alarm_manager.alarms), 1)
        
        retrieved_alarm = self.alarm_manager.get_alarm("test1")
        self.assertEqual(retrieved_alarm, alarm)
        self.assertEqual(retrieved_alarm.label, "Test Alarm 1")

    def test_remove_alarm(self):
        alarm_time = datetime.time(7, 0)
        self.alarm_manager.create_alarm(alarm_time, "To Be Removed", alarm_id="toberemoved")
        self.assertEqual(len(self.alarm_manager.alarms), 1)
        self.alarm_manager.remove_alarm("toberemoved")
        self.assertEqual(len(self.alarm_manager.alarms), 0)
        self.assertIsNone(self.alarm_manager.get_alarm("toberemoved"))

    def test_update_alarm_in_manager(self):
        alarm_time = datetime.time(7, 0)
        self.alarm_manager.create_alarm(alarm_time, "Original Label", alarm_id="update_me")
        
        new_time = datetime.time(8, 0)
        new_label = "Updated Label"
        updated_alarm = self.alarm_manager.update_alarm("update_me", alarm_time=new_time, label=new_label, enabled=False)
        
        self.assertIsNotNone(updated_alarm)
        self.assertEqual(updated_alarm.alarm_time, new_time)
        self.assertEqual(updated_alarm.label, new_label)
        self.assertFalse(updated_alarm.enabled)

        retrieved_alarm = self.alarm_manager.get_alarm("update_me")
        self.assertEqual(retrieved_alarm.label, new_label)

    def test_save_and_load_alarms(self):
        alarm_time1 = datetime.time(7, 0)
        alarm_time2 = datetime.time(8, 30)
        self.alarm_manager.create_alarm(alarm_time1, "Save Test 1", alarm_id="save1", repeat_days=[0,1], feed_type="topic_facts", feed_options={"topic":"Weather"})
        self.alarm_manager.create_alarm(alarm_time2, "Save Test 2", alarm_id="save2", enabled=False)
        self.assertEqual(len(self.alarm_manager.alarms), 2)

        # Trigger save (implicitly done by create_alarm, but can call directly if needed)
        self.alarm_manager.save_alarms()
        self.assertTrue(os.path.exists(TEST_ALARMS_FILE))

        # Create a new manager to load from the file
        new_manager = AlarmManager(alarms_file=TEST_ALARMS_FILE)
        self.assertEqual(len(new_manager.alarms), 2)

        loaded_alarm1 = new_manager.get_alarm("save1")
        self.assertIsNotNone(loaded_alarm1)
        self.assertEqual(loaded_alarm1.label, "Save Test 1")
        self.assertEqual(loaded_alarm1.alarm_time, alarm_time1)
        self.assertEqual(loaded_alarm1.repeat_days, [0,1])
        self.assertTrue(loaded_alarm1.enabled)
        self.assertEqual(loaded_alarm1.feed_type, "topic_facts")
        self.assertEqual(loaded_alarm1.feed_options, {"topic":"Weather"})

        loaded_alarm2 = new_manager.get_alarm("save2")
        self.assertIsNotNone(loaded_alarm2)
        self.assertEqual(loaded_alarm2.label, "Save Test 2")
        self.assertFalse(loaded_alarm2.enabled)

    def test_check_and_trigger_alarms_one_time(self):
        # Alarm set for 1 minute in the future
        trigger_dt = datetime.datetime.now() + datetime.timedelta(minutes=1)
        alarm_time = trigger_dt.time().replace(second=0, microsecond=0)
        
        alarm = self.alarm_manager.create_alarm(alarm_time, "Trigger Me OneTime", alarm_id="trigger1")
        self.assertTrue(alarm.enabled)

        # Check before time
        time_before = trigger_dt - datetime.timedelta(minutes=2)
        triggered_list_before = self.alarm_manager.check_and_trigger_alarms(current_datetime_override=time_before)
        self.assertEqual(len(triggered_list_before), 0)

        # Check at trigger time
        # Override current_datetime_override for check_and_trigger_alarms if it supports it
        # For now, assuming AlarmManager.check_and_trigger_alarms uses datetime.datetime.now()
        # So we need to control "now" using patch
        with patch('wakeupai.alarm.datetime.datetime') as mock_dt:
            # Mock datetime.now() to return the trigger time
            mock_dt.now.return_value = trigger_dt 
            mock_dt.side_effect = lambda *args, **kw: datetime.datetime(*args, **kw) # Allow other datetime uses
            mock_dt.strptime = datetime.datetime.strptime # Keep strptime working
            mock_dt.fromtimestamp = datetime.datetime.fromtimestamp

            triggered_list_at_time = self.alarm_manager.check_and_trigger_alarms()
            self.assertEqual(len(triggered_list_at_time), 1)
            self.assertEqual(triggered_list_at_time[0].alarm_id, "trigger1")
            self.assertIn("trigger1", self.alarm_manager.actively_sounding_alarm_ids)

            # One-time alarm should be disabled after triggering by check_and_trigger_alarms
            # retrieved_alarm = self.alarm_manager.get_alarm("trigger1")
            # self.assertFalse(retrieved_alarm.enabled)

            # Check again immediately, should not re-trigger (already triggered that minute or disabled)
            triggered_list_again = self.alarm_manager.check_and_trigger_alarms()
            self.assertEqual(len(triggered_list_again), 0)

    def test_check_and_trigger_alarms_snoozed(self):
        trigger_dt = datetime.datetime.now() + datetime.timedelta(minutes=1)
        alarm_time = trigger_dt.time().replace(second=0, microsecond=0)
        alarm = self.alarm_manager.create_alarm(alarm_time, "Snooze Trigger Test", alarm_id="snooze_trigger")
            
        # Trigger and snooze
        self.alarm_manager.check_and_trigger_alarms(current_datetime_override=trigger_dt) # Triggers it, adds to actively_sounding
        self.alarm_manager.request_snooze_for_active_alarms(minutes=9)
        self.assertTrue(alarm.is_snoozing)

        # Check during snooze period
        time_during_snooze = trigger_dt + datetime.timedelta(minutes=5)
        triggered_list_snoozing = self.alarm_manager.check_and_trigger_alarms(current_datetime_override=trigger_dt)
        self.assertEqual(len(triggered_list_snoozing), 0)

        # Check after snooze period
        time_after_snooze = trigger_dt + datetime.timedelta(minutes=10) # 1 min after 9 min snooze from original time
        triggered_list_after_snooze = self.alarm_manager.check_and_trigger_alarms(current_datetime_override=time_after_snooze)
        self.assertEqual(len(triggered_list_after_snooze), 1)
        self.assertEqual(triggered_list_after_snooze[0].alarm_id, "snooze_trigger")
        self.assertFalse(alarm.is_snoozing) # is_snoozing should be reset

    def test_request_snooze_and_mark_complete(self):
        alarm_time = datetime.time(10,0)
        alarm = self.alarm_manager.create_alarm(alarm_time, "Snooze Mark Test", alarm_id="snooze_mark")
        
        # Manually add to actively_sounding_alarm_ids to simulate it was triggered
        self.alarm_manager.actively_sounding_alarm_ids.add("snooze_mark")
        self.assertTrue(alarm.enabled)

        snoozed_labels = self.alarm_manager.request_snooze_for_active_alarms(minutes=5)
        self.assertIn("Snooze Mark Test", snoozed_labels)
        retrieved_alarm = self.alarm_manager.get_alarm("snooze_mark")
        self.assertTrue(retrieved_alarm.is_snoozing)
        self.assertIsNotNone(retrieved_alarm.snooze_until_datetime)

        # Still in active set because processing loop hasn't marked it complete
        self.assertIn("snooze_mark", self.alarm_manager.actively_sounding_alarm_ids)

        self.alarm_manager.mark_alarm_processing_complete("snooze_mark")
        self.assertNotIn("snooze_mark", self.alarm_manager.actively_sounding_alarm_ids)

    def test_load_alarm_with_past_snooze(self):
        alarm_id = "past_snooze_test"
        alarm_time = datetime.time(11,0)
        # Create an alarm dict as if it was saved while snoozing, but snooze time is now in the past
        past_snooze_timestamp = time.time() - 1000 # 1000 seconds in the past
        alarm_data = {
            "alarm_id": alarm_id,
            "alarm_time": alarm_time.strftime("%H:%M:%S"),
            "label": "Past Snooze",
            "repeat_days": [],
            "enabled": True,
            "is_snoozing": True, 
            "snooze_until_timestamp": past_snooze_timestamp,
            "feed_type": "daily_news",
            "feed_options": {}
        }
        with open(TEST_ALARMS_FILE, 'w') as f:
            json.dump([alarm_data], f)

        # Create new manager to load this
        new_manager = AlarmManager(alarms_file=TEST_ALARMS_FILE)
        loaded_alarm = new_manager.get_alarm(alarm_id)
        self.assertIsNotNone(loaded_alarm)
        self.assertFalse(loaded_alarm.is_snoozing, "is_snoozing should be reset as snooze time is past")
        self.assertIsNone(loaded_alarm.snooze_until_datetime, "snooze_until_datetime should be reset")

if __name__ == '__main__':
    unittest.main()
