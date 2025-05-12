# e:\Dev\WakeUpAI\wakeupai\audio_player.py
import subprocess
import os
import time
import logging

logger = logging.getLogger(__name__)

IS_RASPBERRY_PI = os.path.exists('/proc/cpuinfo') and ('Raspberry Pi' in open('/proc/cpuinfo').read())

def play_audio_file(filepath: str, wait_for_completion: bool = True):
    """
    Plays the given audio file.
    On Raspberry Pi, uses mpg123. Otherwise, logs a message.

    Args:
        filepath (str): The path to the audio file (e.g., .mp3).
        wait_for_completion (bool): If True, the function will block until playback is finished.
                                      If False, playback starts and the function returns immediately.
    """
    if not os.path.exists(filepath):
        logger.error(f"AudioPlayer: File not found - {filepath}")
        return False

    logger.info(f"AudioPlayer: Attempting to play '{filepath}'")
    try:
        if IS_RASPBERRY_PI:
            command = ["mpg123", "-q", filepath] 
            if wait_for_completion:
                logger.info(f"AudioPlayer: Playing '{filepath}' (waiting for completion)...")
                process = subprocess.run(command, check=True, capture_output=True, text=True)
                logger.debug(f"AudioPlayer: mpg123 stdout: {process.stdout.strip() if process.stdout else 'N/A'}")
                logger.info(f"AudioPlayer: Finished playing '{filepath}'.")
            else:
                logger.info(f"AudioPlayer: Starting playback of '{filepath}' (non-blocking)...")
                subprocess.Popen(command)
        else:
            logger.info(f"AudioPlayer (Mock): Pretending to play '{filepath}'. Playback would take ~5 seconds.")
            if wait_for_completion:
                time.sleep(5) # Simulate playback duration
            logger.info(f"AudioPlayer (Mock): Finished '{filepath}'.")
        return True
    except FileNotFoundError:
        logger.error(f"AudioPlayer: mpg123 command not found. Please ensure it is installed and in PATH for Raspberry Pi playback.", exc_info=True)
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"AudioPlayer: mpg123 failed to play '{filepath}'. Return code: {e.returncode}", exc_info=True)
        logger.error(f"mpg123 stderr: {e.stderr.strip() if e.stderr else 'N/A'}")
        logger.error(f"mpg123 stdout: {e.stdout.strip() if e.stdout else 'N/A'}")
        return False
    except Exception as e:
        logger.error(f"AudioPlayer: An unexpected error occurred while trying to play '{filepath}': {e}", exc_info=True)
        return False

if __name__ == '__main__':
    print("--- Audio Player Test ---")
    # Create a dummy mp3 file for testing
    dummy_file_dir = "test_audio_output"
    dummy_filename = "dummy_audio_for_player_test.mp3"

    # Setup basic logging for the __main__ test if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG, 
            format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger.info("Basic logging configured for audio_player.py direct test run.")
    
    if not os.path.exists(dummy_file_dir):
        os.makedirs(dummy_file_dir)
        logger.info(f"Created directory for test audio: {dummy_file_dir}")

    full_dummy_path = os.path.join(dummy_file_dir, dummy_filename)
    
    # Create a small, valid (but silent) MP3 file if one doesn't exist.
    # This is a very minimal MP3 structure (ID3 tag + empty frame).
    # Actual audio content is not needed for testing the player call itself.
    if not os.path.exists(full_dummy_path) or os.path.getsize(full_dummy_path) < 10:
        try:
            with open(full_dummy_path, 'wb') as f:
                # Minimal ID3v1 tag (128 bytes)
                tag_data = bytearray(128)
                tag_data[0:3] = b'TAG'
                tag_data[3:33] = b'Test Title'                # Title (30 chars)
                tag_data[33:63] = b'Test Artist'               # Artist (30 chars)
                tag_data[63:93] = b'Test Album'                # Album (30 chars)
                tag_data[93:97] = b'2023'                  # Year (4 chars)
                # Comment (28 chars), Track (1 byte), Genre (1 byte)
                # For a truly valid MP3, you might need a LAME header or a silent frame.
                # For now, this is just a named .mp3 file for the player to find.
                # A more robust dummy MP3 might be needed if mpg123 is picky.
                f.write(tag_data) # This is just an ID3 tag, not playable audio
            logger.info(f"Created dummy audio file (ID3 tag only): {full_dummy_path}")
            # Actual mpg123 might complain about this file. For robust testing, use a real silent mp3.
        except Exception as e:
            logger.error(f"Error creating dummy audio file: {e}", exc_info=True)

    logger.info("\nTesting blocking playback (mocked if not on Pi or no mpg123):")
    play_audio_file(full_dummy_path, wait_for_completion=True)
    
    logger.info("\nTesting non-blocking playback (mocked if not on Pi or no mpg123):")
    play_audio_file(full_dummy_path, wait_for_completion=False)
    if not IS_RASPBERRY_PI:
        logger.info("(Mock non-blocking call returned immediately, playback 'continues' in background)")
        time.sleep(6) # Give mock non-blocking playback time to 'finish'
    else:
        logger.info("(Real non-blocking call started, you might hear audio now if mpg123 is working)")
        time.sleep(2) # Give it a moment to start

    logger.info("\nTesting with a non-existent file:")
    play_audio_file("non_existent_audio_file.mp3")
    
    logger.info("--- Audio Player Test Complete ---")
