#!/usr/bin/env bash
set -Eeuo pipefail

DWE_MUSIC_DIR="${DWE_MUSIC_DIR:-/srv/dwe/music}"
DWE_NAVIDROME_DATA_DIR="${DWE_NAVIDROME_DATA_DIR:-/srv/dwe/navidrome/data}"
DWE_STAGING_DIR="${DWE_STAGING_DIR:-/srv/dwe/staging}"

mkdir -p "$DWE_MUSIC_DIR" "$DWE_NAVIDROME_DATA_DIR" "$DWE_STAGING_DIR" \
  "$DWE_STAGING_DIR/incoming" "$DWE_STAGING_DIR/validated" "$DWE_STAGING_DIR/rejected"

if [[ ! -d "$DWE_MUSIC_DIR" ]]; then
  echo "Local music directory missing: $DWE_MUSIC_DIR" >&2
  exit 1
fi

if [[ ! -d "$DWE_NAVIDROME_DATA_DIR" ]]; then
  echo "Navidrome data directory missing: $DWE_NAVIDROME_DATA_DIR" >&2
  exit 1
fi

printf 'Validated local clone directories:\n'
printf ' - music: %s\n' "$DWE_MUSIC_DIR"
printf ' - navidrome data: %s\n' "$DWE_NAVIDROME_DATA_DIR"
printf ' - staging: %s\n' "$DWE_STAGING_DIR"

if command -v find >/dev/null 2>&1; then
  files=$(find "$DWE_MUSIC_DIR" -type f | head -n 20)
  if [[ -n "$files" ]]; then
    echo "Sample files in local clone:"
    printf '%s\n' "$files"
  else
    echo "No files found in the local clone yet; this is expected before the first sync or import."
  fi
fi

if command -v ffprobe >/dev/null 2>&1; then
  mapfile -d '' audio_files < <(find "$DWE_MUSIC_DIR" -type f \( -iname '*.flac' -o -iname '*.mp3' -o -iname '*.m4a' -o -iname '*.aac' -o -iname '*.ogg' -o -iname '*.wav' \) -print0)
  if (( ${#audio_files[@]} > 0 )); then
    echo "Checking audio files with ffprobe..."
    for file in "${audio_files[@]}"; do
      ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$file" >/dev/null || {
        echo "Unreadable audio file detected: $file" >&2
        exit 1
      }
    done
    echo "All audio files in the local clone are readable."
  else
    echo "No audio files found in the local clone yet."
  fi
else
  echo "ffprobe is not installed; skipping audio validation in this environment."
fi

echo "Local clone verification completed. Navidrome may now be started in read-only mode against $DWE_MUSIC_DIR."
