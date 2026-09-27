"""Skill lint checker
=======================

Validates that every ``SKILL.md`` under ``.github/skills`` contains only
Japanese text.  Any line with Latin letters (A‑Z, a‑z) is reported, except the
literal filename ``SKILL.md`` which may appear in a header.

The script exits with status 1 on violations so it can be integrated into the
``make lint`` CI step.
"""

import pathlib
import re
import sys


def has_english(text: str) -> bool:
    """Return ``True`` if *text* contains disallowed Latin letters.

    Allowed exceptions (English may appear without triggering a lint error):
    * The literal filename ``SKILL.md``.
    * URLs – any substring matching ``http://`` or ``https://``.
    * Markdown links – ``[text](url)`` patterns.
        * Inline or block code fences – lines that start with ````` or contain
            backticks `` ` ``.
    * Common command‑line invocations (e.g., ``make``, ``docker``, ``git``,
      ``curl``, ``pip``, ``python``, ``uv``, ``poetry``, ``ruff``, ``pytest``,
      ``npm`` or ``node``) that appear at the start of a line, optionally
      preceded by whitespace.
    * Lines that are pure whitespace.
    """
    # Empty or whitespace‑only lines are never violations.
    if not text.strip():
        return False

    stripped = text.strip()

    # Allow the filename itself.
    if stripped.lower() == "skill.md":
        return False

    # Allow URLs.
    if re.search(r"https?://", stripped):
        return False

    # Allow markdown link syntax.
    if re.search(r"\[[^\]]+\]\([^\)]+\)", stripped):
        return False

    # Allow code fences or inline code.
    if stripped.startswith("```") or "`" in stripped:
        return False

    # Allow common command‑line invocations at line start.
    # Combine the pattern over two strings to stay within line‑length limits.
    pattern = (
        r"^\s*(make|docker|git|curl|pip|python|uv|poetry|ruff|pytest|"
        r"npm|node)\b"
    )
    if re.match(pattern, text):
        return False

    # Finally, detect any remaining Latin letters.
    return bool(re.search(r"[A-Za-z]", text))


def main() -> int:
    root = pathlib.Path(".")
    pattern = "**/.github/skills/**/SKILL.md"
    failed = False
    for path in root.glob(pattern):
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                if has_english(line):
                    print(
                        f"[skill‑lint] {path}:{i}: English text -> "
                        f"{line.rstrip()}"
                    )
                    failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
