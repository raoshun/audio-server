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
# Install Playwright browsers as the root user (required for system‑level
# dependencies).  The browsers are initially placed in the default root
# cache directory.  We then copy them to the appuser's cache directory
# where the non‑root runtime can access them without needing to traverse
# the protected ``/root`` home directory.
RUN python -m playwright install --with-deps && \
    chmod -R a+rx /root/.cache/ms-playwright && \
    mkdir -p /home/appuser/.cache/ms-playwright && \
    cp -r /root/.cache/ms-playwright/* /home/appuser/.cache/ms-playwright && \
    chmod -R a+rx /home/appuser/.cache/ms-playwright && \
    # Diagnostic listing to verify browsers are present at build time
    ls -R /home/appuser/.cache/ms-playwright

# Tell Playwright where to find the browsers for runtime.  Using the
# appuser's cache location avoids permission issues with ``/root``.
ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

# コードから参照されていない mc alias 設定（config.json）の COPY を削除する。
# config.json は .gitignore で除外された秘密情報を含むため CI の checkout 上に
# 存在せず、COPY 自体がビルド失敗の原因になっていた。実行時に読み込む箇所はない。
# ソースのみコピーする（read-only mount は dev 時に上書きする）。
COPY backend/ ./backend/

# Use a non‑root user for runtime security
USER appuser

# Default command – run the FastAPI application defined in search_api.py
CMD ["uvicorn", "backend.app.search_api:app", "--host", "0.0.0.0", "--port", "8000"]

# Ensure the source root is on PYTHONPATH so imports like `import backend` work
ENV PYTHONPATH=/app
