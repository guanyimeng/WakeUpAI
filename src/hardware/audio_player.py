import subprocess
import os
import time
import logging
from typing import Optional
from threading import Event # Added for stop_event

logger = logging.getLogger(__name__)

_playback_process: Optional[subprocess.Popen] = None

def play_audio_file(filepath: str, wait_for_completion: bool = True, stop_event: Optional[Event] = None) -> bool:
    global _playback_process

    if _playback_process and _playback_process.poll() is None:
        logger.info(f"AudioPlayer: Stopping existing playback (PID: {_playback_process.pid}) before starting new audio.")
        stop_audio()

    if not os.path.exists(filepath):
        logger.error(f"AudioPlayer: File not found - {filepath}")
        return False

    logger.info(f"AudioPlayer: Attempting to play '{filepath}'")
    current_process = None # Define current_process to ensure it's always available for cleanup/logging
    try:
        command = ["mpg123", "-q", filepath]
        
        current_process = subprocess.Popen(command)
        _playback_process = current_process # Track the current process globally
        logger.info(f"AudioPlayer: Started playback of '{filepath}' with PID: {_playback_process.pid}.")

        if wait_for_completion:
            logger.debug(f"AudioPlayer: Waiting for playback completion of '{filepath}' (PID: {_playback_process.pid}).")
            while True:
                if _playback_process.poll() is not None: # Process finished
                    break
                if stop_event and stop_event.is_set():
                    logger.info(f"AudioPlayer: Stop event received for '{filepath}' (PID: {_playback_process.pid}). Terminating playback.")
                    stop_audio() # This will terminate _playback_process and set it to None
                    return False # Playback was interrupted
                time.sleep(0.1) # Check periodically
            
            # Check return_code of the process that was being waited upon
            # _playback_process might be None if stop_audio was called from the loop above
            # so we use current_process which is local to this call.
            return_code = current_process.returncode 
            if _playback_process == current_process: 
                _playback_process = None # Clear global handle only if it hasn't been cleared by an interleaving stop_audio() call

            if return_code == 0:
                logger.info(f"AudioPlayer: Playback of '{filepath}' completed successfully.")
                return True
            else:
                # If stop_event caused termination, it results in a non-zero code; this is expected & already logged.
                if not (stop_event and stop_event.is_set()): 
                    logger.warning(f"AudioPlayer: Playback of '{filepath}' finished with error code {return_code}.")
                return False
        else: # Non-blocking
            logger.info(f"AudioPlayer: Playback of '{filepath}' (PID: {_playback_process.pid}) started non-blockingly.")
            return True # Successfully started

    except FileNotFoundError:
        logger.error(f"AudioPlayer: mpg123 command not found.", exc_info=True)
        if current_process and _playback_process and _playback_process.pid == current_process.pid: _playback_process = None
        return False
    except Exception as e:
        logger.error(f"AudioPlayer: An unexpected error occurred while trying to play '{filepath}': {e}", exc_info=True)
        if current_process and _playback_process and _playback_process.pid == current_process.pid: _playback_process = None
        return False

def stop_audio():
    global _playback_process
    if _playback_process and _playback_process.poll() is None:
        pid_for_log = _playback_process.pid
        logger.info(f"AudioPlayer: Attempting to stop current audio playback (PID: {pid_for_log})...")
        try:
            _playback_process.terminate()
            try:
                _playback_process.wait(timeout=0.5)
                logger.info(f"AudioPlayer: Playback process (PID: {pid_for_log}) terminated.")
            except subprocess.TimeoutExpired:
                logger.warning(f"AudioPlayer: mpg123 process (PID: {pid_for_log}) did not terminate quickly. Sending SIGKILL.")
                _playback_process.kill()
                _playback_process.wait(timeout=0.5) 
                logger.info(f"AudioPlayer: Playback process (PID: {pid_for_log}) killed.")
            except Exception as e_wait:
                logger.debug(f"AudioPlayer: Exception during process wait for PID {pid_for_log}: {e_wait}")
        except ProcessLookupError: 
             logger.info(f"AudioPlayer: Process with PID {pid_for_log} already terminated.")
        except Exception as e:
            logger.error(f"AudioPlayer: Error stopping playback for PID {pid_for_log}: {e}", exc_info=True)
        finally:
            _playback_process = None
    else:
        logger.info("AudioPlayer: No active audio playback process was found to stop.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    logger = logging.getLogger(__name__)
    logger.info("Audio_player.py script running for tests.")
    
    # Determine the correct base directory to find the default alarm sound
    # Assuming this script is in src/hardware, and Woke Up Cool Today.mp3 is in src/default
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(script_dir) # This should be the 'src' directory
        test_file = os.path.join(base_dir, "default", "Woke_Up_Cool_Today.mp3")
    except NameError: # __file__ is not defined (e.g. in an interactive session not running as script)
        logger.warning("Could not determine test file path using __file__, attempting relative path.")
        # Fallback for environments where __file__ might not be defined as expected
        # This might be fragile depending on the CWD when the script is run.
        test_file = os.path.join("src", "default", "Woke_Up_Cool_Today.mp3") 

    logger.info(f"Looking for test audio file at: {test_file}")
    
    if os.path.exists(test_file):
        logger.info(f"--- Test 1: Blocking play, stop with event after 3s ---")
        event = Event()
        def stop_it_thread_func():
            time.sleep(3)
            logger.info("Test thread: Setting stop event!")
            event.set()
        
        import threading
        stopper_thread = threading.Thread(target=stop_it_thread_func)
        
        logger.info("Test Main: Starting blocking playback for Test 1...")
        stopper_thread.start()
        play_audio_file(test_file, wait_for_completion=True, stop_event=event)
        stopper_thread.join()
        logger.info("--- Test 1 Finished ---")

        time.sleep(1) # Pause between tests
        logger.info(f"--- Test 2: Blocking play, let it finish (no event set) ---")
        play_audio_file(test_file, wait_for_completion=True, stop_event=Event()) # New event, won't be set
        logger.info("--- Test 2 Finished ---")

        time.sleep(1) # Pause between tests
        logger.info(f"--- Test 3: Non-blocking play, stop with global stop_audio() after 2s ---")
        play_audio_file(test_file, wait_for_completion=False) # Non-blocking
        logger.info("Test Main: Non-blocking playback started for Test 3. Waiting 2s...")
        time.sleep(2)
        stop_audio()
        logger.info("Test Main: stop_audio() called for Test 3.")
        logger.info("--- Test 3 Finished ---")
    else:
        logger.warning(f"Test audio file not found: {test_file}, skipping __main__ playback tests.")

    logger.info("Audio_player.py tests finished.")
