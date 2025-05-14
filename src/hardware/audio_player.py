import subprocess
import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Store the playback process globally
_playback_process: Optional[subprocess.Popen] = None

def play_audio_file(filepath: str):
    global _playback_process

    # Stop any currently playing audio before starting a new one
    if _playback_process:
        logger.info(f"AudioPlayer: Stopping existing playback before starting new audio.")
        stop_audio() # Call the stop function

    if not os.path.exists(filepath):
        logger.error(f"AudioPlayer: File not found - {filepath}")
        return False

    logger.info(f"AudioPlayer: Attempting to play '{filepath}'")
    try:
        command = ["mpg123", "-q", filepath]
        logger.info(f"AudioPlayer: Starting playback of '{filepath}' (non-blocking)...")
        _playback_process = subprocess.Popen(command)
        return True
    except FileNotFoundError:
        logger.error(f"AudioPlayer: mpg123 command not found. ", exc_info=True)
        _playback_process = None
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"AudioPlayer: mpg123 failed to play '{filepath}'. Return code: {e.returncode}", exc_info=True)
        logger.error(f"mpg123 stderr: {e.stderr.strip() if e.stderr else 'N/A'}")
        logger.error(f"mpg123 stdout: {e.stdout.strip() if e.stdout else 'N/A'}")
        _playback_process = None
        return False
    except Exception as e:
        logger.error(f"AudioPlayer: An unexpected error occurred while trying to play '{filepath}': {e}", exc_info=True)
        _playback_process = None
        return False


def stop_audio():
    global _playback_process
    if _playback_process:
        logger.info(f"AudioPlayer: Attempting to stop current audio playback (PID: {_playback_process.pid if hasattr(_playback_process, 'pid') else 'N/A'})...")
        try:
            _playback_process.terminate()
            if isinstance(_playback_process, subprocess.Popen):
                try:
                    _playback_process.wait(timeout=0.5) # Don't block for too long
                except subprocess.TimeoutExpired:
                    logger.warning(f"AudioPlayer: mpg123 process (PID: {_playback_process.pid}) did not terminate quickly. Sending SIGKILL.")
                    _playback_process.kill() # Force kill if terminate didn't work quickly
                except Exception as e_wait:
                    logger.debug(f"AudioPlayer: Exception during process wait after terminate: {e_wait}")
            logger.info(f"AudioPlayer: Stop signal sent to playback process.")
        except Exception as e:
            logger.error(f"AudioPlayer: Error stopping playback: {e}", exc_info=True)
        finally:
            _playback_process = None # Clear the process handle
    else:
        logger.info("AudioPlayer: No audio playback process was recorded as active.")

# =============================================================================================================================
if __name__ == '__main__':
    
    print("--- Audio Player Test ---")
    real_audio_filepath = os.path.join("src", "default", "default_alarm_sound.mp3")

    # Setup basic logging for the __main__ test if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG, 
            format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        # Check if __name__ is already configured to avoid re-adding handlers if imported elsewhere
        if not any(isinstance(h, logging.StreamHandler) for h in logging.getLogger().handlers):
             logging.getLogger().addHandler(logging.StreamHandler())
        logger.info("Basic logging configured for audio_player.py direct test run.")
    
    # Check if the real audio file exists
    if not os.path.exists(real_audio_filepath):
        logger.error(f"Real test audio file not found at: {real_audio_filepath}")
        logger.error("Cannot proceed with real audio tests.")
        # Exit or skip tests if the file is mandatory
        # For now, we'll just skip playing it and log the error
        real_audio_filepath = None # Mark as not found

    if real_audio_filepath:
        logger.info(f"nUsing test audio file: {real_audio_filepath}")

        logger.info("nTesting non-blocking playback:")
        play_audio_file(real_audio_filepath)
        logger.info("(Real non-blocking call started, you might hear audio now if mpg123 is working)")
        time.sleep(2) # Give it a moment to start

    logger.info("nTesting with a non-existent file:")
    play_audio_file("non_existent_audio_file.mp3")
    
    logger.info("--- Audio Player Test Complete ---")

    # Wait 10 seconds to kill
    time.sleep(10)
    stop_audio()