from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import os
from ..alarm.newalarm import AlarmScheduler
from ..config import WEB_UI_HOST, WEB_UI_PORT

logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class AlarmCreate(BaseModel):
    alarm_time: str = Field(..., description="Alarm time in HH:MM format", example="07:30")
    name: str = Field(..., description="Alarm name", example="Morning News")
    feed_type: str = Field(default="daily_news", description="Type of feed content", example="daily_news")
    feed_options: Dict[str, Any] = Field(default_factory=dict, description="Feed generation options")
    enabled: bool = Field(default=True, description="Whether the alarm is enabled")

class AlarmUpdate(BaseModel):
    alarm_time: Optional[str] = Field(None, description="Alarm time in HH:MM format")
    name: Optional[str] = Field(None, description="Alarm name")
    feed_type: Optional[str] = Field(None, description="Type of feed content")
    feed_options: Optional[Dict[str, Any]] = Field(None, description="Feed generation options")
    enabled: Optional[bool] = Field(None, description="Whether the alarm is enabled")

class AlarmResponse(BaseModel):
    id: str
    alarm_time: str
    name: str
    feed_type: str
    feed_options: Dict[str, Any]
    enabled: bool
    is_active: Optional[bool] = False

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None

# Global alarm scheduler instance
alarm_scheduler: Optional[AlarmScheduler] = None

def create_app(scheduler: AlarmScheduler = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    global alarm_scheduler
    
    app = FastAPI(
        title="WakeUpAI Alarm Configuration API",
        description="REST API for managing WakeUpAI alarm configurations",
        version="1.0.0"
    )
    
    # Set the global scheduler
    alarm_scheduler = scheduler or AlarmScheduler()
    
    # Setup static files and templates
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    
    # Create directories if they don't exist
    os.makedirs(static_dir, exist_ok=True)
    os.makedirs(templates_dir, exist_ok=True)
    
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates = Jinja2Templates(directory=templates_dir)
    
    # API Routes
    @app.get("/api/alarms", response_model=List[AlarmResponse])
    async def get_alarms():
        """Get all alarms."""
        try:
            alarms_data = alarm_scheduler.get_alarms_data()
            alarms = []
            for alarm_data in alarms_data:
                # Get the actual task to check if it's active
                task = alarm_scheduler.get_alarm_by_id(alarm_data["id"])
                alarm_response = AlarmResponse(
                    id=alarm_data["id"],
                    alarm_time=alarm_data["alarm_time"],
                    name=alarm_data["name"],
                    feed_type=alarm_data["feed_type"],
                    feed_options=alarm_data["feed_options"],
                    enabled=alarm_data["enabled"],
                    is_active=task.is_active if task else False
                )
                alarms.append(alarm_response)
            return alarms
        except Exception as e:
            logger.error(f"Error getting alarms: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @app.post("/api/alarms", response_model=APIResponse)
    async def create_alarm(alarm: AlarmCreate):
        """Create a new alarm."""
        try:
            task = alarm_scheduler.add_alarm(
                alarm_time_str=alarm.alarm_time,
                name=alarm.name,
                feed_type=alarm.feed_type,
                feed_options=alarm.feed_options
            )
            
            if not task:
                raise HTTPException(status_code=400, detail="Failed to create alarm")
            
            # Update enabled status if needed
            if not alarm.enabled:
                alarm_scheduler.update_alarm(task.id, enabled=alarm.enabled)
            
            return APIResponse(
                success=True,
                message=f"Alarm '{alarm.name}' created successfully",
                data={"id": task.id}
            )
        except Exception as e:
            logger.error(f"Error creating alarm: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/api/alarms/{alarm_id}", response_model=APIResponse)
    async def update_alarm(alarm_id: str, alarm: AlarmUpdate):
        """Update an existing alarm."""
        try:
            success = alarm_scheduler.update_alarm(
                alarm_id=alarm_id,
                alarm_time_str=alarm.alarm_time,
                name=alarm.name,
                feed_type=alarm.feed_type,
                feed_options=alarm.feed_options,
                enabled=alarm.enabled
            )
            
            if not success:
                raise HTTPException(status_code=404, detail="Alarm not found")
            
            return APIResponse(
                success=True,
                message="Alarm updated successfully"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating alarm: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/api/alarms/{alarm_id}", response_model=APIResponse)
    async def delete_alarm(alarm_id: str):
        """Delete an alarm."""
        try:
            success = alarm_scheduler.remove_alarm_by_id(alarm_id)
            
            if not success:
                raise HTTPException(status_code=404, detail="Alarm not found")
            
            return APIResponse(
                success=True,
                message="Alarm deleted successfully"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting alarm: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/alarms/{alarm_id}/stop", response_model=APIResponse)
    async def stop_alarm(alarm_id: str):
        """Stop a specific active alarm."""
        try:
            task = alarm_scheduler.get_alarm_by_id(alarm_id)
            if not task:
                raise HTTPException(status_code=404, detail="Alarm not found")
            
            if not task.is_active:
                return APIResponse(
                    success=True,
                    message="Alarm is not currently active"
                )
            
            task.stop()
            return APIResponse(
                success=True,
                message=f"Alarm '{task.name}' stopped successfully"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error stopping alarm: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/alarms/stop-all", response_model=APIResponse)
    async def stop_all_alarms():
        """Stop all active alarms."""
        try:
            stopped_any = alarm_scheduler.stop_active_alarms()
            message = "All active alarms stopped" if stopped_any else "No active alarms to stop"
            return APIResponse(
                success=True,
                message=message
            )
        except Exception as e:
            logger.error(f"Error stopping all alarms: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/feed-types")
    async def get_feed_types():
        """Get available feed types and their options."""
        return {
            "feed_types": [
                {
                    "id": "daily_news",
                    "name": "Daily News",
                    "description": "Latest news from around the world",
                    "options": {
                        "country": {
                            "type": "select",
                            "default": "US",
                            "choices": ["US", "UK", "CA", "AU", "DE", "FR", "JP"]
                        }
                    }
                },
                {
                    "id": "topic_facts",
                    "name": "Topic Facts",
                    "description": "Fun facts about a specific topic",
                    "options": {
                        "topic": {
                            "type": "text",
                            "default": "science",
                            "placeholder": "Enter a topic (e.g., space, animals, history)"
                        }
                    }
                },
                {
                    "id": "custom_prompt",
                    "name": "Custom Prompt",
                    "description": "Custom AI-generated content",
                    "options": {
                        "prompt": {
                            "type": "textarea",
                            "default": "",
                            "placeholder": "Enter your custom prompt for AI content generation"
                        }
                    }
                }
            ]
        }
    
    # Web UI Routes
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        """Serve the main web UI."""
        return templates.TemplateResponse("index.html", {"request": request})
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "scheduler_running": alarm_scheduler._scheduler_thread.is_alive() if alarm_scheduler._scheduler_thread else False}
    
    return app

def run_web_server(scheduler: AlarmScheduler, host: str = None, port: int = None):
    """Run the web server with the given alarm scheduler."""
    import uvicorn
    
    app = create_app(scheduler)
    host = host or WEB_UI_HOST
    port = port or WEB_UI_PORT
    
    logger.info(f"Starting WakeUpAI web server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")