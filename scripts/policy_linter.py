"""Policy Linter
=======================

This script enforces the coding and security policies defined in
`.github/skills/common-coding-rules/SKILL.md`.

It checks for:
1.  CRITICAL: Direct MinIO writes.
2.  HIGH: Plaintext secrets in code or comments.
3.  MEDIUM: Missing Japanese comments near API calls.
"""

import pathlib
import re
import sys

# --- Configuration ---

# Patterns for Secret Detection (HIGH)
SECRET_KEYWORDS = [
    r"api_key", r"password", r"secret", r"token", r"credential", r"auth_token"
]
# A regex that matches a keyword followed by an assignment or in a comment
# Using f-string to avoid .format() placeholder collision with {8,}
SECRET_PATTERN = re.compile(
    rf"({'|'.join(SECRET_KEYWORDS)})\s*[:=]\s*['\"][a-zA-Z0-9_\-]{{8,}}['\"]",
    re.IGNORECASE
)

# Patterns for MinIO direct write (CRITICAL)
# For now, a simple regex. In a more advanced version, we would use AST.
MINIO_WRITE_PATTERN = re.compile(
    r"\.(upload|put|write|save|create|post)\s*\(.*minio.*",
    re.IGNORECASE
)

# Patterns for API calls that should have Japanese comments (MEDIUM)
API_CALL_PATTERN = re.compile(
    r"(requests\.(get|post|put|delete)|client\.(get|post|put|delete))",
    re.IGNORECASE
)

# Regex for Japanese characters (Unicode range)
JAPANESE_PATTERN = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]")

# --- Implementation ---


class PolicyLinter:
    def __init__(self, root_dir="."):
        self.root_dir = pathlib.Path(root_dir)
        self.errors = []
        self.warnings = []
        self.notes = []

    def report(self, level, path, line_no, message):
        msg = f"[{level}] {path}:{line_no}: {message}"
        if level == "CRITICAL":
            self.errors.append(msg)
        elif level == "HIGH" or level == "MEDIUM":
            self.warnings.append(msg)
        else:
            self.notes.append(msg)

    def check_file(self, file_path: pathlib.Path):
        with file_path.open(encoding="utf-8") as f:
            lines = f.readlines()

        # 1. Regex-based scans (Secret and MinIO write)
        for i, line in enumerate(lines, start=1):
            # Check for Secrets (HIGH)
            if SECRET_PATTERN.search(line):
                self.report(
                    "HIGH", file_path, i, "Potential plaintext secret."
                )

            # Check for MinIO direct write (CRITICAL)
            if MINIO_WRITE_PATTERN.search(line):
                # Note: A real check would verify the approved client was used.
                self.report(
                    "CRITICAL", file_path, i,
                    "Direct MinIO write attempt detected."
                )

            # Check for API calls and missing Japanese comments (MEDIUM)
            if API_CALL_PATTERN.search(line):
                # Look at the previous line for a comment
                prev_line = lines[i - 2] if i > 1 else ""
                if not JAPANESE_PATTERN.search(prev_line) and "#" in prev_line:
                    self.report(
                        "MEDIUM", file_path, i,
                        "API call detected without a Japanese "
                        "descriptive comment."
                    )
                elif (
                    not JAPANESE_PATTERN.search(prev_line)
                    and "#" not in prev_line
                ):
                    # If no comment at all, documentation is also a concern.
                    self.report(
                        "MEDIUM", file_path, i,
                        "API call detected. Please add a Japanese "
                        "descriptive comment."
                    )

    def run(self):
        # Target only backend files
        for path in self.root_dir.glob("backend/**/*.py"):
            if path.is_file():
                self.check_file(path)

        # Print results
        if self.errors:
            print("\n❌ CRITICAL ERRORS FOUND:")
            for err in self.errors:
                print(err)

        if self.warnings:
            print("\n⚠️ WARNINGS FOUND:")
            for warn in self.warnings:
                print(warn)

        if self.notes:
            print("\nℹ️ NOTES:")
            for note in self.notes:
                print(note)

        return 1 if self.errors else 0


if __name__ == "__main__":
    sys.exit(PolicyLinter().run())
