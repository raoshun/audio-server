"""Lyrics transcriber package.

Provides a CLI entry point (``python -m lyrics``) that scans a music
directory for ``.flac`` files, runs ``faster-whisper`` on each file and
writes LRC lyric files next to the source audio.

The implementation follows the specification attached by the user.  It
uses environment variables for configuration to keep the Docker image
stateless and to allow overrides at runtime.
"""

# Export nothing by default; the package is executed as a module.
