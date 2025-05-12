# WakeUpAI

## Description
A Raspberry Pi based Alarm, using OpenAI API to generate feeds and speak them out as Alarm sounds to wake up people softly with their interested content.

## Features
*   **Core Alarm:** Multiple alarms, time setup, repeat, label, snooze.
*   **Text-to-Speech:** Feeds speech under 5 minutes.
*   **Feed Generation:**
    *   Daily news from the internet.
    *   Topic-based feeds/fun facts via prompting (e.g., Animal world fun facts).
    *   Customizable user prompts for morning feeds.
*   **Web UI:** Interface for alarm creation and feed prompt configuration.
*   **Hardware Integration (Raspberry Pi 5):**
    *   Three buttons: enable/disable, snooze, speak current time.
    *   Speaker output.

## Prerequisites
*   Python 3.9+ (as specified in `pyproject.toml`)
*   Poetry (for dependency management)
*   Docker (for containerized deployment)
*   Raspberry Pi 5 (for target deployment)
*   OpenAI API Key

## Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd WakeUpAI
    ```

2.  **Set up environment variables:**
    Copy the `.env_example` file to `.env` and fill in your actual API keys and configurations:
    ```bash
    cp .env_example .env
    # Now edit .env with your values
    ```

3.  **Install dependencies using Poetry:**
    If you have Poetry installed globally:
    ```bash
    poetry install
    ```
    This will create a virtual environment and install all necessary packages.

4.  **Activate the virtual environment:**
    ```bash
    poetry shell
    ```

## Usage

(Details on how to run the application, e.g., `python -m wakeupai.webui` or using uvicorn/gunicorn if it's a web app, will go here.)

## Configuration

The application is configured via environment variables listed in the `.env` file. Refer to `.env_example` for a list of required variables.

## Deployment

### Docker

1.  **Build the Docker image:**
    ```bash
    docker build -t wakeupai .
    ```

2.  **Run the Docker container:**
    Make sure your `.env` file is present or pass environment variables via the `docker run` command.
    ```bash
    docker run -d --env-file .env -p 8000:80 --name wakeupai_container wakeupai
    ```
    *(Adjust port mapping `-p 8000:80` as needed. The internal port is assumed to be 80 based on the example Dockerfile CMD. This might need to change.)*

### Raspberry Pi 5

(Specific instructions for deploying and running on Raspberry Pi 5, including hardware setup, will go here.)

## Tests

To run tests:
```bash
poetry run pytest
```

## Contributing

(Optional: Guidelines for contributing to the project.)
