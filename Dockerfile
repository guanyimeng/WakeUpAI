# 1. Use an official Python runtime as a parent image
# Using a Debian-based image, python:3.11-slim-bookworm supports arm64 for Raspberry Pi.
FROM python:3.11-slim-bookworm

# Prevent Python from writing pyc files and ensure output is unbuffered
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
# - mpg123 for audio playback on Pi
# - tini as a lightweight init system for proper signal handling and zombie reaping
RUN apt-get update && apt-get install -y mpg123 tini && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Install Poetry (specific version for reproducibility)
# Consider fetching the latest recommended installation method from Poetry's documentation periodically.
RUN pip install poetry==1.8.2

# Create a non-root user and group
# Using numeric IDs for better portability and to avoid conflicts if base image changes user/group names
RUN groupadd --system --gid 1000 appgroup && \
    useradd --system --uid 1000 --gid appgroup --home-dir /app --shell /sbin/nologin appuser

# Copy only dependency definition files to leverage Docker cache
COPY pyproject.toml poetry.lock /app/

# Install project dependencies using Poetry
# --no-root: install into system Python site-packages, not a Poetry-managed venv inside image
# --only main: install only main dependencies, skip dev dependencies
# --no-interaction --no-ansi: for CI/CD, non-interactive and plain output
RUN poetry install --no-interaction --no-ansi --no-root --only main

# Create directories for runtime data and set permissions
# temp_alarm_audio: for TTS output before playback
# data: for persistent data like alarms.json
RUN mkdir -p /app/temp_alarm_audio /app/data && \
    chown -R appuser:appgroup /app/temp_alarm_audio /app/data
# /app itself will be owned by appuser via COPY --chown.

# Copy the rest of the application code into the container
# Ensure .dockerignore is properly set up to exclude unnecessary files
COPY --chown=appuser:appgroup . /app/

# Switch to the non-root user
USER appuser

# Expose the port the app runs on (informational, actual mapping is in docker run)
# This should match WEB_UI_PORT from config.py (default 8000)
EXPOSE 8000

# Command to run the application
# Using tini as the entrypoint to properly handle signals and reap zombie processes
# For development/simplicity: uses Flask's built-in server (not for production load)
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["poetry", "run", "python", "-m", "wakeupai.webui"]

# For a more production-ready setup, consider Gunicorn (add gunicorn to pyproject.toml):
# CMD ["poetry", "run", "gunicorn", "--bind", "0.0.0.0:8000", "wakeupai.webui:app"]
# If using Gunicorn on port 80, change EXPOSE to 80.
