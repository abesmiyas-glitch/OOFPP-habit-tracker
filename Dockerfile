# ─────────────────────────────────────────────────────────────────────────────
# Habit Tracker – Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
#
# Build:
#   docker build --no-cache -t habit-tracker .
#
# Run (interactive CLI):
#   docker run -it habit-tracker
#
# Run with sample habits pre-loaded:
#   docker run -it habit-tracker --seed
#
# Run tests:
#   docker run --rm --entrypoint python habit-tracker -m unittest test_habit_tracker -v
#
# Persist data between container runs:
#   docker run -it -v "$(pwd)/data:/app/data" habit-tracker
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# Install dependencies (rich + pytest)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY . .

# Create a data directory for the SQLite database
RUN mkdir -p /app/data

# Set the database path to the persistent data directory
ENV HABIT_DB_PATH=/app/data/habits.db

# Set terminal type to support 256 colors for CLI output
ENV TERM=xterm-256color

# Default command — start the interactive CLI
ENTRYPOINT ["python", "cli.py"]
