#!/usr/bin/env bash

# update-metadata.sh
# Replace the "artist" and "albumartist" tags of all FLAC files directly under the given directory.
# Supports a dry‑run mode to preview the files that would be processed and the new artist name.
# Usage: ./update-metadata.sh [-n|--dry-run] [directory] [artist]
#   -n, --dry-run   Show what would be changed without modifying files.
#   directory       Target directory (default: current directory)
#   artist          Artist name to set (default: "Disney's World of English")

# Prevent history expansion which interferes with paths containing '!'
set +H
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: $0 [-n|--dry-run] [directory] [artist]
  -n, --dry-run   Show target files and the artist name without changing tags.
  directory        Directory containing FLAC files (default: current directory).
  artist           Artist name to write (default: "Disney's World of English").
EOF
}

DRY_RUN=false

# Parse optional flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

TARGET_DIR="${1:-.}"
# Expand a leading tilde to the user's home directory
if [[ "$TARGET_DIR" == "~"* ]]; then
  TARGET_DIR="${HOME}${TARGET_DIR:1}"
fi
# Unescape any backslash‑escaped characters (e.g., spaces, '!') supplied by the caller
TARGET_DIR=$(printf '%b' "$TARGET_DIR")
ARTIST="${2:-Disney\'s World of English}"
# Remove any backslash characters that may have been introduced by shell escaping
ARTIST="${ARTIST//\\/}"

# Verify that the target is a directory
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Error: $TARGET_DIR is not a directory" >&2
  exit 1
fi

shopt -s nullglob
flac_files=("$TARGET_DIR"/*.flac)
if [[ ${#flac_files[@]} -eq 0 ]]; then
  echo "No FLAC files found directly under $TARGET_DIR"
  exit 0
fi

if $DRY_RUN; then
  echo "Dry‑run mode: the following files would be updated with artist=$ARTIST:"
  for f in "${flac_files[@]}"; do
    # Show only the filename (no base path)
    filename="$(basename "$f")"
    # Retrieve the current Artist tag; suppress errors if tag missing
    current_artist=$(metaflac --show-tag=artist "$f" 2>/dev/null | head -n1 | cut -d= -f2-)
    if [[ -z "$current_artist" ]]; then
      current_artist="<none>"
    fi
    # Align columns: filename left‑justified in a 50‑character field
    printf "  %-50s current Artist: %s\n" "$filename" "$current_artist"
  done
  exit 0
fi

for f in "${flac_files[@]}"; do
  echo "Updating tags for $f"
  metaflac --remove-tag=artist --remove-tag=albumartist "$f" || true
  metaflac --set-tag="artist=${ARTIST}" --set-tag="albumartist=${ARTIST}" "$f"
done

echo "All done."
