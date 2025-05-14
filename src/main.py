import os
import datetime, time
import json
import logging
from alarm.alarm import AlarmManager

if __name__ == "__main__":
    now = datetime.datetime.now()
    alarm_time = now + datetime.timedelta(minutes=1)
    alarm_time_str = alarm_time.strftime("%H:%M")
    print(alarm_time_str)
    alarm_time = alarm_time_str # Set alarm time (24-hour format)
    schedule_alarm(alarm_time)

    # Start scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.start()

    # Simulate button interaction
    print("Press 'Enter' to stop the alarm.")
    input()  # Wait for user input
    stop_alarm()
