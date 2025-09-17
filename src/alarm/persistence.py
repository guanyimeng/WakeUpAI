import json
import os
import logging
from typing import List, Dict, Any, Optional
from ..config import ALARMS_FILE_PATH

logger = logging.getLogger(__name__)

class AlarmPersistence:
    """Handles saving and loading alarm configurations to/from JSON file."""
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or ALARMS_FILE_PATH
        self._ensure_directory_exists()
    
    def _ensure_directory_exists(self):
        """Ensure the directory for the alarms file exists."""
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created directory for alarms file: {directory}")
            except Exception as e:
                logger.error(f"Failed to create directory {directory}: {e}")
                # Fallback to current directory
                self.file_path = "alarms.json"
                logger.warning(f"Using fallback alarms file path: {self.file_path}")
    
    def save_alarms(self, alarms: List[Dict[str, Any]]) -> bool:
        """Save alarms list to JSON file."""
        try:
            with open(self.file_path, 'w') as f:
                json.dump(alarms, f, indent=2)
            logger.info(f"Saved {len(alarms)} alarms to {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save alarms to {self.file_path}: {e}")
            return False
    
    def load_alarms(self) -> List[Dict[str, Any]]:
        """Load alarms list from JSON file."""
        if not os.path.exists(self.file_path):
            logger.info(f"Alarms file {self.file_path} does not exist. Starting with empty alarm list.")
            return []
        
        try:
            with open(self.file_path, 'r') as f:
                alarms = json.load(f)
            logger.info(f"Loaded {len(alarms)} alarms from {self.file_path}")
            return alarms
        except Exception as e:
            logger.error(f"Failed to load alarms from {self.file_path}: {e}")
            return []
    
    def alarm_to_dict(self, alarm_task) -> Dict[str, Any]:
        """Convert AlarmTask object to dictionary for serialization."""
        return {
            "id": getattr(alarm_task, 'id', None),
            "alarm_time": alarm_task.alarm_time,
            "name": alarm_task.name,
            "feed_type": alarm_task.feed_type,
            "feed_options": alarm_task.feed_options,
            "enabled": alarm_task.enabled
        }
    
    def dict_to_alarm_data(self, alarm_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Convert dictionary to alarm data for creating AlarmTask."""
        return {
            "alarm_time_str": alarm_dict["alarm_time"],
            "name": alarm_dict["name"],
            "feed_type": alarm_dict.get("feed_type", "daily_news"),
            "feed_options": alarm_dict.get("feed_options", {}),
            "enabled": alarm_dict.get("enabled", True),
            "id": alarm_dict.get("id")
        }