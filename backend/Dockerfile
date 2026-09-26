# Dockerfile for DWE backend (Navidrome client)
# Uses official slim Python image, installs dependencies and runs the
# FastAPI (or similar) entry point. Adjust the CMD if a different entry
# point is used in the project.

FROM python:3.12-slim

# Set a non‑root user (matches host UID/GID when possible)
ARG PUID=1000
ARG PGID=1000
RUN addgroup --gid $PGID appgroup && \
    adduser --uid $PUID --gid $PGID --disabled-password --gecos "" appuser && \
    mkdir -p /app && chown appuser:appgroup /app

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (read‑only mount will override during dev)
COPY backend/ ./backend/
COPY config.json .

# Use a non‑root user for runtime security
USER appuser

# Default command – run the FastAPI application defined in search_api.py
CMD ["uvicorn", "backend.app.search_api:app", "--host", "0.0.0.0", "--port", "8000"]

# Ensure the source root is on PYTHONPATH so imports like `import backend` work
ENV PYTHONPATH=/app
