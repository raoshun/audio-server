#!/usr/bin/env bash
set -Eeuo pipefail

STAGING_DIR="${DWE_STAGING_DIR:-/srv/dwe/staging}"
VALIDATED_DIR="${STAGING_DIR}/validated"
REJECTED_DIR="${STAGING_DIR}/rejected"

mkdir -p "$VALIDATED_DIR" "$REJECTED_DIR"

if [[ ! -d "$STAGING_DIR/incoming" ]]; then
  echo "No incoming directory found at $STAGING_DIR/incoming" >&2
  exit 1
fi

shopt -s nullglob
incoming_files=("$STAGING_DIR/incoming"/*.flac)

if [[ ${#incoming_files[@]} -eq 0 ]]; then
  echo "No FLAC files found in $STAGING_DIR/incoming"
  exit 0
fi

for src in "${incoming_files[@]}"; do
  base="$(basename "$src")"
  if ! ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$src" >/dev/null 2>&1; then
    echo "Rejecting invalid FLAC: $src"
    mv "$src" "$REJECTED_DIR/$base"
    continue
  fi

  if ! metaflac --export-tags-to=- "$src" >/dev/null 2>&1; then
    echo "Rejecting missing/invalid tags: $src"
    mv "$src" "$REJECTED_DIR/$base"
    continue
  fi

  echo "Validating: $src"
  mv "$src" "$VALIDATED_DIR/$base"
done

echo "Validation complete. Files accepted: $VALIDATED_DIR"
