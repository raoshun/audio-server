"""Lyrics transcription entry point.

This module is executed inside the Docker ``lyrics`` service via
``python -m lyrics``.  It reads configuration from environment variables,
loads a ``faster-whisper`` model, transcribes the given audio file and
writes an ``.lrc`` file next to the source audio.

Key features required by the user story:

* ``WHISPER_COMPUTE_TYPE`` defaults to ``auto`` so that a GPU‑only
  configuration will automatically fall back to CPU when a GPU is not
  available.
* The implementation attempts to load the model with the requested
  ``device`` and ``compute_type`` and, on failure, retries with a safe
  CPU configuration.
* Each Whisper segment may contain multiple lines of text – they are
  converted to separate LRC lines while preserving the segment start
  timestamp.
* ``FORCE`` and ``DRY_RUN`` flags control overwriting existing ``.lrc``
  files.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List

from faster_whisper import WhisperModel  # type: ignore


class Settings:
    """Simple runtime configuration read from environment variables.

    The container supplies reasonable defaults; the user can override any
    value at ``docker compose run`` time.
    """

    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "large-v3")
    WHISPER_LANGUAGE: str = os.getenv("WHISPER_LANGUAGE", "en")
    WHISPER_DEVICE: str | None = os.getenv(
        "WHISPER_DEVICE"
    )  # ``auto`` or ``cpu`` etc.
    WHISPER_COMPUTE_TYPE: str = os.getenv(
        "WHISPER_COMPUTE_TYPE", "auto"
    )
    WHISPER_VAD_FILTER: bool = (
        os.getenv("WHISPER_VAD_FILTER", "false").lower() == "true"
    )
    WHISPER_VAD_THRESHOLD: float = float(
        os.getenv("WHISPER_VAD_THRESHOLD", "0.5")
    )
    WHISPER_BEAM_SIZE: int = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
    WHISPER_TEMPERATURE: float = float(
        os.getenv("WHISPER_TEMPERATURE", "0.0")
    )

    DWE_MUSIC_DIR: str = os.getenv("DWE_MUSIC_DIR", "/music")
    DWE_LYRICS_DIR: str = os.getenv("DWE_LYRICS_DIR", "/music")
    FORCE: bool = os.getenv("FORCE", "false").lower() == "true"
    DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"

    # Cache directory for Whisper model files inside the container.
    # Docker compose mounts host ./models → /models, persisting the model.
    WHISPER_MODEL_CACHE_DIR: str = os.getenv(
        "WHISPER_MODEL_CACHE_DIR", "/models"
    )


def _format_timestamp(seconds: float) -> str:
    """Return an LRC timestamp string ``[MM:SS.xx]``.

    ``seconds`` may contain fractional part; we keep two decimal places.
    """
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"[{minutes:02d}:{secs:05.2f}]"


def _segment_to_lrc_lines(segment: object) -> List[str]:
    """Convert a Whisper segment (dict or ``Segment`` object) to LRC lines.

    The function is tolerant to the concrete type returned by
    ``faster-whisper`` – older versions yielded plain ``dict`` objects,
    while newer releases return a ``Segment`` dataclass instance.  Both
    provide ``start`` (float) and ``text`` (str) attributes/keys.  If the
    text contains line breaks, each logical line receives the same start
    timestamp, matching the behaviour expected by most LRC players.
    """
    # Retrieve ``start`` and ``text`` regardless of dict or object.
    if isinstance(segment, dict):
        start = segment.get("start", 0.0)
        text = segment.get("text", "").strip()
    else:
        # Assume a ``Segment`` dataclass with ``start`` and ``text``
        # attributes.
        start = getattr(segment, "start", 0.0)
        text = getattr(segment, "text", "").strip()

    if not text:
        return []

    timestamp = _format_timestamp(start)
    lines: List[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if clean:
            lines.append(f"{timestamp}{clean}")
    return lines


def _load_model(settings: Settings) -> WhisperModel:
    """Load a Whisper model with fallback logic.

    The primary attempt uses ``WHISPER_DEVICE`` (if set) and
    ``WHISPER_COMPUTE_TYPE``.  If that fails – for example because the
    requested compute type is not supported on CPU – we retry with a safe
    CPU configuration (device ``cpu`` and compute type ``int8``)."""

    device = settings.WHISPER_DEVICE or "auto"
    compute_type = settings.WHISPER_COMPUTE_TYPE
    # Use a writable temporary directory for model downloads. ``/tmp`` is
    # world‑writable inside the container and avoids permission issues with
    # mounted volumes.
    # Use the cache directory defined in Settings; Docker mounts host ./models
    # to this location, so the model persists across container runs.
    download_root = settings.WHISPER_MODEL_CACHE_DIR
    # Ensure the cache directory exists before attempting to download.
    Path(download_root).mkdir(parents=True, exist_ok=True)
    try:
        return WhisperModel(
            settings.WHISPER_MODEL,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
        )
    except RuntimeError as exc:  # pragma: no cover – exercised
        # via runtime error.
        print(
            f"[WARN] Failed to load model with device={device} "
            f"compute_type={compute_type}: {exc}"
        )
        # Fallback to CPU with a more universally supported compute type.
        fallback_device = "cpu"
        fallback_compute = "int8"
        print(
            f"[INFO] Falling back to device={fallback_device} "
            f"compute_type={fallback_compute}"
        )
        return WhisperModel(
            settings.WHISPER_MODEL,
            device=fallback_device,
            compute_type=fallback_compute,
            download_root=download_root,
        )


def _transcribe(audio_path: Path, settings: Settings) -> List[dict]:
    """Run Whisper transcription and return a list of segment dicts.

    ``faster-whisper`` yields segments as a generator. Converting the
    iterable to a list ensures the caller can safely use ``len()`` and
    iterate multiple times.
    """
    model = _load_model(settings)
    # ``faster-whisper`` accepts ``vad_filter`` (bool) and an optional
    # ``vad_parameters`` dict.
    # Previously, a non‑existent ``vad_threshold`` argument was passed,
    # causing a ``TypeError``. We now forward the threshold via
    # ``vad_parameters``.
    # ``faster-whisper`` returns a ``(segments, info)`` tuple.
    # The original code attempted to access ``result.segments`` which raises
    # an ``AttributeError``. We unpack the tuple and convert the segment
    # iterable to a list.
    result = model.transcribe(
        str(audio_path),
        language=settings.WHISPER_LANGUAGE,
        vad_filter=settings.WHISPER_VAD_FILTER,
        vad_parameters={"threshold": settings.WHISPER_VAD_THRESHOLD},
        beam_size=settings.WHISPER_BEAM_SIZE,
        temperature=settings.WHISPER_TEMPERATURE,
    )
    segments, _ = result  # type: ignore[assignment]
    # Convert the potentially lazy iterable to a concrete list.
    return list(segments)


def _write_lrc(
    lrc_path: Path, lrc_lines: Iterable[str], dry_run: bool
) -> None:
    if dry_run:
        print(
            f"[DRY_RUN] Would write {len(list(lrc_lines))} lines to {lrc_path}"
        )
        return
    lrc_path.write_text("\n".join(lrc_lines) + "\n", encoding="utf-8")
    print(f"[INFO] Wrote LRC file: {lrc_path}")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe audio to LRC using faster-whisper."
    )
    parser.add_argument(
        "audio",
        type=Path,
        help="Path to the source audio file (e.g. .flac)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing .lrc file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files, only print actions",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    # CLI flags override environment variables.
    if args.force:
        settings.FORCE = True
    if args.dry_run:
        settings.DRY_RUN = True

    audio_path: Path = args.audio
    if not audio_path.is_file():
        print(f"[ERROR] Audio file not found: {audio_path}", file=sys.stderr)
        return 1

    lrc_path = audio_path.with_suffix('.lrc')
    if lrc_path.exists() and not settings.FORCE:
        print(
            f"[INFO] LRC already exists ({lrc_path}); "
            "use --force to overwrite."
        )
        return 0

    print(f"[INFO] Transcribing {audio_path} → {lrc_path}")
    segments = _transcribe(audio_path, settings)
    print(f"[INFO] Received {len(segments)} segments from Whisper")

    lrc_lines: List[str] = []
    for seg in segments:
        lrc_lines.extend(_segment_to_lrc_lines(seg))

    _write_lrc(lrc_path, lrc_lines, settings.DRY_RUN)
    return 0


if __name__ == "__main__":
    sys.exit(main())
