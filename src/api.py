
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
