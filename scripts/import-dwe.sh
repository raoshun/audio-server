#!/usr/bin/env bash
set -Eeuo pipefail

VALIDATED_DIR="${DWE_STAGING_DIR:-/srv/dwe/staging}/validated"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-minio.example.local:9000}"
MINIO_BUCKET="${MINIO_BUCKET:-dwe-audio}"
MINIO_AUDIO_PREFIX="${MINIO_AUDIO_PREFIX:-audio}"

if [[ ! -d "$VALIDATED_DIR" ]]; then
  echo "Validated directory not found: $VALIDATED_DIR" >&2
  exit 1
fi

mc alias set local "http://${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY:-replace-me}" "${MINIO_SECRET_KEY:-replace-me}" >/dev/null
mc ls "local/${MINIO_BUCKET}" >/dev/null 2>&1 || mc mb "local/${MINIO_BUCKET}" >/dev/null

find "$VALIDATED_DIR" -type f -name '*.flac' -print0 | while IFS= read -r -d '' file; do
  rel_path="${file#$VALIDATED_DIR/}"
  destination="local/${MINIO_BUCKET}/${MINIO_AUDIO_PREFIX}/${rel_path}"
  echo "Uploading: $file -> $destination"
  mc cp "$file" "$destination"
done

echo "Import complete. Remaining validated files are left in $VALIDATED_DIR until the workflow confirms they are copied to MinIO."
