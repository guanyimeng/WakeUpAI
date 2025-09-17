#!/usr/bin/env python3
"""
WakeUpAI Web Server Entry Point

This module provides a web-based interface for configuring and managing alarms.
It can run alongside or instead of the hardware-based interface.
"""

import sys
import os
import logging
import argparse
from threading import Thread
import time

# Adjust the Python path to include the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.alarm.newalarm import AlarmScheduler
from src.web.api import run_web_server
from src.config import WEB_UI_HOST, WEB_UI_PORT, OPENAI_API_KEY

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='WakeUpAI Web Server')
    parser.add_argument('--host', default=WEB_UI_HOST, help='Host to bind to')
    parser.add_argument('--port', type=int, default=WEB_UI_PORT, help='Port to bind to')
    parser.add_argument('--hardware', action='store_true', help='Also run hardware interface')
    parser.add_argument('--alarms-file', help='Path to alarms JSON file')
    
    args = parser.parse_args()
    
    logger.info("Starting WakeUpAI Web Server...")
    
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY is not set. Feed generation and TTS will use defaults or fail.")
    
    # Initialize the alarm scheduler
    alarm_scheduler = AlarmScheduler(args.alarms_file)
    
    # Start the alarm scheduler
    alarm_scheduler.start()
    logger.info("Alarm scheduler started.")
    
    hardware_manager = None
    
    # Optionally start hardware interface
    if args.hardware:
        try:
            from src.hardware.hardware import HardwareManager, GPIO_LIB
            hardware_manager = HardwareManager(alarm_manager=alarm_scheduler)
            hardware_manager.setup_gpio()
            logger.info("Hardware interface initialized.")
            
            if GPIO_LIB == "mock":
                logger.info("Running with MOCK GPIO.")
        except ImportError as e:
            logger.warning(f"Could not import hardware modules: {e}")
            logger.warning("Hardware interface will not be available.")
        except Exception as e:
            logger.error(f"Failed to initialize hardware interface: {e}")
    
    try:
        # Run the web server (this blocks)
        run_web_server(alarm_scheduler, args.host, args.port)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        logger.info("Initiating shutdown sequence.")
        if hardware_manager:
            hardware_manager.cleanup_gpio()
        if alarm_scheduler:
            alarm_scheduler.stop()
        logger.info("WakeUpAI Web Server shut down gracefully.")

if __name__ == "__main__":
    main()