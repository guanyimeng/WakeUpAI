# WakeUpAI

Don't forget to star it if you like this project!

## Description
A Raspberry Pi based Alarm, using OpenAI API to generate feeds and speak them out as Alarm sounds to wake up people softly with their interested content.

## Features
*   **Core Alarm:** Multiple alarms, time setup, repeat, label, snooze.
*   **Text-to-Speech:** Feeds speech under 5 minutes.
*   **Feed Generation:**
    *   Daily news from the internet.
    *   Topic-based feeds/fun facts via prompting (e.g., Animal world fun facts).
    *   Customizable user prompts for morning feeds.
*   **Hardware Integration (Raspberry Pi):**
    *   Three buttons: enable/disable alarm, snooze (feature to be fully integrated with `newalarm.py`), speak current time.
    *   Speaker output.
*   **Web UI (Planned/Optional):** The original README mentioned a Web UI. While `src/main.py` doesn't launch one, FastAPI and Jinja2 are in `pyproject.toml`, suggesting this might be a future or optional feature. If a Web UI for alarm management exists, details should be added here.

## Prerequisites
*   Python 3.9+ (as specified in `pyproject.toml`)
*   Poetry (for dependency management)
*   Raspberry Pi (tested with Raspberry Pi 5, other models with GPIO might work)
*   OpenAI API Key
*   Speaker connected to Raspberry Pi
*   Push buttons connected to GPIO pins (see `src/config.py` for default pin numbers)

## Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd WakeUpAI
    ```

2.  **Set up environment variables:**
    Copy the `.env_example` file to `.env` and fill in your actual OpenAI API key and any other configurations:
    ```bash
    cp .env_example .env
    # Now edit .env with your values (primarily OPENAI_API_KEY)
    ```

3.  **Install dependencies using Poetry:**
    It's recommended to do this on your Raspberry Pi, or in an environment that matches its architecture if cross-compiling.
    ```bash
    poetry install
    ```


## Usage

1.  **Ensure all hardware (buttons, speaker) is correctly connected to your Raspberry Pi.**
2.  **Verify that your `.env` file is correctly set up with the `OPENAI_API_KEY`.**
3.  **Run the application from the project root directory:**
    ```bash
    poetry python -m src.main
    ```
    The application will initialize predefined alarms (as coded in `src/main.py`) and start listening for button presses.

    *   The console will display logs, including when alarms are scheduled and triggered.
    *   Refer to `src/config.py` for default GPIO pin assignments for buttons.
    *   Alarms and feed generation are managed by `src/alarm/newalarm.py` and `src/wakeupai/feeds.py`.

## Configuration

*   **Environment Variables:** The primary configuration is done via the `.env` file. See `.env_example` for required variables, especially `OPENAI_API_KEY`.
*   **Alarm Definitions:** Currently, alarms are hardcoded for demonstration in `src/main.py` (`initialize_alarms` function). For persistent or user-defined alarms, this would need to be modified to load from a configuration file or a database.
*   **GPIO Pins:** Button pin configurations are in `src/config.py`.
*   **Feed Content:** Feed generation options (e.g., news country, topics) are set when alarms are added in the code.

