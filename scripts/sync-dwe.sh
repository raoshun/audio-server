#!/usr/bin/env bash
set -Eeuo pipefail

REMOTE_NAME="${RCLONE_REMOTE:-minio}"
REMOTE_PATH="${RCLONE_REMOTE_PREFIX:-dwe-audio/audio}"
DEST_PATH="${DWE_MUSIC_DIR:-/srv/dwe/music}"
LOG_DIR="${DWE_SYNC_LOG_DIR:-/srv/dwe/sync/logs}"
MODE="${SYNC_MODE:-dry-run}"

mkdir -p "$DEST_PATH" "$LOG_DIR"

TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
LOG_FILE="$LOG_DIR/${TIMESTAMP}.log"

if ! command -v rclone >/dev/null 2>&1; then
  echo "[ERROR] rclone is required but was not found in PATH." >&2
  exit 1
fi

if [[ "${1:-}" == "--apply" ]]; then
  MODE="apply"
fi

if [[ "$MODE" != "apply" ]]; then
  MODE="dry-run"
fi

printf '%s\n' "[$TIMESTAMP] DWE sync start" | tee -a "$LOG_FILE"
printf '%s\n' "Source: ${REMOTE_NAME}:${REMOTE_PATH}" | tee -a "$LOG_FILE"
printf '%s\n' "Destination: ${DEST_PATH}" | tee -a "$LOG_FILE"
printf '%s\n' "Mode: ${MODE}" | tee -a "$LOG_FILE"

CMD=(rclone copy "${REMOTE_NAME}:${REMOTE_PATH}" "$DEST_PATH" --metadata --checksum --create-empty-src-dirs)

if [[ "$MODE" == "dry-run" ]]; then
  CMD+=(--dry-run)
fi

printf '%s\n' "Command: ${CMD[*]}" | tee -a "$LOG_FILE"

if ! "${CMD[@]}" 2>&1 | tee -a "$LOG_FILE"; then
  printf '%s\n' "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] DWE sync failed" | tee -a "$LOG_FILE"
  exit 1
fi

printf '%s\n' "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] DWE sync completed" | tee -a "$LOG_FILE"

echo "Completed with mode: ${MODE}"
