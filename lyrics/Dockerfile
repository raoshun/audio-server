# NVIDIA CUDA runtime base image (Ubuntu 22.04) suitable for GPU inference.
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Install system dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

# Create a virtual environment and ensure it is on PATH.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

# Install Python dependencies.
COPY lyrics/requirements.txt /app/requirements.txt
# Upgrade pip to the latest version to avoid resolver issues with older pip versions.
RUN pip install --upgrade --no-cache-dir pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy application code into a package directory.
# Copy the lyrics package source.
# Copy the contents of the lyrics source directory into a dedicated package folder.
COPY lyrics/ /app/lyrics/
# Set the working directory and PYTHONPATH so that the "lyrics" package is importable.
WORKDIR /app
ENV PYTHONPATH="/app"

# Use a non‑root user (UID/GID can be overridden at build time).
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appgroup && \
    useradd -m -u ${UID} -g ${GID} appuser
# Create the cache directory and set ownership while still root.
RUN mkdir -p /models && chown ${UID}:${GID} /models
USER appuser

# Default command runs the module.
CMD ["python", "-m", "lyrics"]
