import schedule
import time
from threading import Thread

alarm_active = True  # Flag to control alarm state

def alarm_message(alarm_name):
    global alarm_active
    while alarm_active:
        print(f"Alarm Triggered: {alarm_name}. Press Enter to stop.")
        time.sleep(1)  # Repeat alarm message
    print(f"Alarm '{alarm_name}' stopped.")

def stop_alarm():
    global alarm_active
    alarm_active = False

def schedule_alarms(alarm_times):
    for alarm in alarm_times:
        alarm_time = alarm["time"]
        alarm_name = alarm["name"]
        schedule.every().day.at(alarm_time).do(alarm_message, alarm_name)
        print(f"Scheduled alarm '{alarm_name}' at {alarm_time}")

# List of alarms
alarms = [
    {"name": "Morning Alarm", "time": "20:44"},
    {"name": "Lunch Reminder", "time": "20:45"},
]

# Schedule alarms
schedule_alarms(alarms)

# Run scheduler in a separate thread
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)
scheduler_thread = Thread(target=run_scheduler)
scheduler_thread.start()

# Wait for user input to stop the alarm
print("Scheduler is running. Press Enter to stop any alarm.")
input()  # Wait for Enter key
stop_alarm()