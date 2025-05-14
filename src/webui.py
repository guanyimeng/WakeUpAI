
import os
import datetime
import json
import logging

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List, Optional

# Assuming your project structure is e:DevWakeUpAI
# Adjust these paths if your structure is different
SRC_DIR = Path(__file__).parent.resolve() # Should be e:DevWakeUpAIsrc
PROJECT_ROOT = SRC_DIR.parent # Should be e:DevWakeUpAI

# Add project root to sys.path to allow imports from sibling directories like 'alarm', 'hardware'
import sys
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR)) # Also add src itself if modules are there directly

try:
    from alarm.alarm import AlarmManager, Alarm
    from hardware.audio_player import play_audio_file, stop_audio # Added stop_audio
    from config import OPENAI_API_KEY # For context, not directly used in UI for now
except ImportError as e:
    logging.error(f"Error importing project modules: {e}. Check PYTHONPATH and file locations.")
    # Fallback for when running in a restricted environment or if imports fail.
    # This allows the file to be written but it won't run correctly without the modules.
    class AlarmManager:
        def __init__(self, alarms_file): self.alarms = {}; self.alarms_file = alarms_file; self.load_alarms()
        def load_alarms(self): logging.info("Mock AlarmManager: Load called"); self.alarms = {}
        def save_alarms(self): logging.info("Mock AlarmManager: Save called")
        def get_alarm(self, alarm_id): return None
        def create_alarm(self, **kwargs): logging.info(f"Mock: Create alarm with {kwargs}"); return Alarm(**kwargs) if 'alarm_id' in kwargs else Alarm(alarm_id="mock", **kwargs)
        def update_alarm(self, alarm_id, **kwargs): logging.info(f"Mock: Update alarm {alarm_id} with {kwargs}")
        def remove_alarm(self, alarm_id): logging.info(f"Mock: Remove alarm {alarm_id}")
        def enable_alarm(self, alarm_id): logging.info(f"Mock: Enable alarm {alarm_id}")
        def disable_alarm(self, alarm_id): logging.info(f"Mock: Disable alarm {alarm_id}")

    class Alarm:
        def __init__(self, alarm_time, label, repeat_days=None, enabled=True, alarm_id=None, feed_type="daily_news", feed_options=None):
            self.alarm_id = alarm_id or str(datetime.datetime.now().timestamp())
            self.alarm_time = alarm_time
            self.label = label
            self.repeat_days = repeat_days or []
            self.enabled = enabled
            self.feed_type = feed_type
            self.feed_options = feed_options or {}
        def to_dict(self): return self.__dict__
        def strftime(self, fmt): return "mock_time" # for templates if alarm_time is not datetime.time

    def play_audio_file(filepath, wait_for_completion=True): logging.info(f"Mock: Play audio {filepath}")
    def stop_audio(): logging.info("Mock: Stop audio")


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Setup FastAPI app and templates
app = FastAPI()
templates_dir = SRC_DIR / "templates"
static_dir = SRC_DIR / "static"

# Mount static files (CSS, JS) - ensure 'static' directory exists in 'src'
if not static_dir.exists():
    static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=str(templates_dir))

# Path to the alarms JSON file
ALARMS_FILE = PROJECT_ROOT / "alarms.json"
alarm_manager = AlarmManager(alarms_file=str(ALARMS_FILE))

# Default audio file for testing
DEFAULT_ALARM_SOUND_PATH = SRC_DIR / "default" / "default_alarm_sound.mp3"


# --- Helper Functions ---
def parse_form_data_for_alarm(
    alarm_time_str: str,
    label: str,
    repeat_days_str: Optional[str],
    feed_type: str,
    feed_options_str: Optional[str],
    enabled_form: Optional[str]
):
    """Parses form data and returns a dictionary of alarm properties."""
    try:
        alarm_time = datetime.datetime.strptime(alarm_time_str, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM.")

    repeat_days: List[int] = []
    if repeat_days_str:
        try:
            repeat_days = sorted(list(set(int(d.strip()) for d in repeat_days_str.split(',') if d.strip())))
            if not all(0 <= day <= 6 for day in repeat_days):
                raise ValueError("Days must be between 0 (Mon) and 6 (Sun).")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid repeat days: {e}")

    feed_options: dict = {}
    if feed_options_str and feed_options_str.strip():
        try:
            feed_options = json.loads(feed_options_str)
            if not isinstance(feed_options, dict):
                raise ValueError("Feed options must be a valid JSON object.")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format for feed options.")
        except ValueError as e:
             raise HTTPException(status_code=400, detail=str(e))


    enabled = enabled_form == "on" # Checkbox value is "on" if checked

    return {
        "alarm_time": alarm_time,
        "label": label,
        "repeat_days": repeat_days,
        "enabled": enabled,
        "feed_type": feed_type if feed_type and feed_type.strip() else "daily_news",
        "feed_options": feed_options,
    }

# --- FastAPI Routes ---

@app.get("/", response_class=HTMLResponse)
async def route_get_all_alarms(request: Request):
    """Displays the main page with a list of all alarms."""
    alarms = sorted(alarm_manager.alarms.values(), key=lambda x: x.alarm_time if hasattr(x, 'alarm_time') and x.alarm_time else datetime.time(0,0) )
    return templates.TemplateResponse("main.html", {"request": request, "alarms": alarms})

@app.get("/alarm/new", response_class=HTMLResponse)
async def route_get_new_alarm_form(request: Request):
    """Displays the form to create a new alarm."""
    return templates.TemplateResponse("edit.html", {"request": request, "alarm": None})

@app.post("/alarm/new")
async def route_post_new_alarm(
    request: Request,
    alarm_time: str = Form(...),
    label: str = Form(...),
    repeat_days: Optional[str] = Form(None),
    feed_type: Optional[str] = Form("daily_news"),
    feed_options: Optional[str] = Form("{}"),
    enabled: Optional[str] = Form(None), # HTML form submits "on" for checked, or field is absent
):
    """Processes the form submission for creating a new alarm."""
    alarm_data = parse_form_data_for_alarm(alarm_time, label, repeat_days, feed_type, feed_options, enabled)
    alarm_manager.create_alarm(**alarm_data)
    return RedirectResponse("/", status_code=303) # Use 303 for POST-redirect-GET

@app.get("/alarm/edit/{alarm_id}", response_class=HTMLResponse)
async def route_get_edit_alarm_form(request: Request, alarm_id: str):
    """Displays the form to edit an existing alarm."""
    alarm = alarm_manager.get_alarm(alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return templates.TemplateResponse("edit.html", {"request": request, "alarm": alarm})

@app.post("/alarm/edit/{alarm_id}")
async def route_post_edit_alarm(
    request: Request,
    alarm_id: str,
    alarm_time: str = Form(...),
    label: str = Form(...),
    repeat_days: Optional[str] = Form(None),
    feed_type: Optional[str] = Form("daily_news"),
    feed_options: Optional[str] = Form("{}"),
    enabled: Optional[str] = Form(None),
):
    """Processes the form submission for updating an existing alarm."""
    if not alarm_manager.get_alarm(alarm_id):
        raise HTTPException(status_code=404, detail="Alarm not found")
    alarm_data = parse_form_data_for_alarm(alarm_time, label, repeat_days, feed_type, feed_options, enabled)
    alarm_manager.update_alarm(alarm_id=alarm_id, **alarm_data)
    return RedirectResponse("/", status_code=303)

@app.post("/alarm/delete/{alarm_id}")
async def route_delete_alarm(alarm_id: str):
    """Deletes an alarm."""
    alarm = alarm_manager.get_alarm(alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    alarm_manager.remove_alarm(alarm_id)
    return RedirectResponse("/", status_code=303)

@app.post("/alarm/toggle/{alarm_id}")
async def route_toggle_alarm_enabled(alarm_id: str):
    """Toggles the enabled state of an alarm."""
    alarm = alarm_manager.get_alarm(alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    if alarm.enabled:
        alarm_manager.disable_alarm(alarm_id)
    else:
        alarm_manager.enable_alarm(alarm_id)
    return RedirectResponse("/", status_code=303)

@app.post("/alarm/test/{alarm_id}")
async def route_test_alarm_sound(alarm_id: str):
    """Tests the sound for a given alarm (plays a default sound)."""
    alarm = alarm_manager.get_alarm(alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found to test.")

    sound_to_play = DEFAULT_ALARM_SOUND_PATH
    if not sound_to_play.exists():
        logging.warning(f"Default alarm sound not found at {sound_to_play}. Cannot test sound.")
        raise HTTPException(status_code=500, detail=f"Default sound file missing: {sound_to_play.name}")

    logging.info(f"Testing sound for alarm '{alarm.label}' (ID: {alarm_id}) using {sound_to_play}")
    # Stop any currently playing audio before starting a new one for test.
    stop_audio() 
    play_audio_file(str(sound_to_play), wait_for_completion=False)
    return RedirectResponse("/", status_code=303)

@app.post("/alarm/stop_all_audio") # New route
async def route_stop_all_audio():
    """Stops any currently playing alarm audio."""
    logging.info("WebUI: Received request to stop all audio.")
    stop_audio()
    return RedirectResponse("/", status_code=303)


if __name__ == "__main__":
    import uvicorn
    # Make sure alarms.json exists or AlarmManager handles it gracefully
    if not ALARMS_FILE.exists():
        logging.info(f"Alarms file {ALARMS_FILE} not found. AlarmManager will create an empty one.")
        # You might want to create an empty JSON array file if your AlarmManager expects it
        # with open(ALARMS_FILE, 'w') as f:
        #     json.dump([], f)

    # Check if default sound exists
    if not DEFAULT_ALARM_SOUND_PATH.exists():
        logging.error(f"CRITICAL: Default alarm sound '{DEFAULT_ALARM_SOUND_PATH}' is missing!")
        # Create a dummy file if it does not exist, so the app can start
        # In a real scenario, you'd ensure this file is deployed.
        try:
            DEFAULT_ALARM_SOUND_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(DEFAULT_ALARM_SOUND_PATH, 'w') as f:
                f.write("dummy mp3 content") # Not a real mp3
            logging.info(f"Created dummy default sound file at {DEFAULT_ALARM_SOUND_PATH}")
        except Exception as e:
            logging.error(f"Could not create dummy sound file: {e}")


    logging.info(f"Starting Uvicorn server for webui.py. Templates: {templates_dir}, Alarms: {ALARMS_FILE}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
