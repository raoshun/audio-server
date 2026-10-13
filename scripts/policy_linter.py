"""共通コーディング規則（common-coding-rules）のポリシーリンター.

`.github/skills/common-coding-rules/SKILL.md` に定義されたルールを
リポジトリ全体のソース（Python / Shell / JS / TS / Vue / Dockerfile）へ
適用する。検出項目:

1. CRITICAL: MinIO への直接書き込み（単一の真実のソース侵害）。
2. HIGH: 秘密情報の平文（環境変数・コメント内の実値）。
3. MEDIUM: API コール周辺の日本語解説欠落。
4. WARNING: 英語を主言語とするコメント（日本語品質ルール）。

CRITICAL 検出時のみ終了コード 1 を返す。警告は `make lint` の出力として
報告し、修正判断はレビュー側へ委ねる。
"""

import pathlib
import re
import sys

# --- 設定 ---

# 走査対象のディレクトリ（リポジトリルートからの相対）。
SCAN_ROOTS = ["backend", "tests", "scripts", "frontend"]

# 走査から除外するディレクトリ名（ビルド成果物・キャッシュ）。
EXCLUDE_DIRS = {
    "node_modules",
    "dist",
    "__pycache__",
    ".vitest_cache",
    ".git",
}

# 走査対象の拡張子（ソースコード全体をカバーする）。
SOURCE_EXTS = {
    ".py",
    ".sh",
    ".js",
    ".ts",
    ".vue",
    ".dockerfile",
    ".yml",
    ".yaml",
    ".json",
}

# 秘密キーとして扱う語（HIGH）。
SECRET_KEYWORDS = [
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "credential",
    "access_key",
    "auth_token",
]

# 秘密キー + 実値の割り当てを拾う正規表現。
# プレースホルダ（replace-me 等）は実値ではないため除外する。
SECRET_PATTERN = re.compile(
    rf"({'|'.join(SECRET_KEYWORDS)})\s*[:=]\s*(?P<value>['\"][^'\"]*['\"]|[A-Za-z0-9_\-]{{8,}})",
    re.IGNORECASE,
)

# 型注釈・フィールド宣言・関数呼び出しは実値ではないため秘密検出から除外する。
NON_SECRET_VALUE_PATTERN = re.compile(
    r"^(SecretStr|Secret[A-Za-z]*|Field|BaseModel|str|bytes|None)$",
)

# 明らかなプレースホルダ（誤検出回避）。
PLACEHOLDER_PATTERN = re.compile(
    r"(replace|change|example|dummy|placeholder|insert|my[-_]secrets?|"
    r"your[-_]|<[^>]+>|\*{3,}|x{4,})",
    re.IGNORECASE,
)

# テストフィクスチャで使う値（実値ではないため HIGH にしない）。
DUMMY_VALUE_PATTERN = re.compile(
    r"^(secret|test\w*|dummy\w*|sample\w*|user|username|password|changeme|"
    r"placeholder|example\w*)$",
    re.IGNORECASE,
)

# MinIO への直接書き込み（CRITICAL）。AST ではなく正規表現で近似する。
MINIO_WRITE_PATTERN = re.compile(
    r"\.(upload|upload_file|put_object|write|save|create|post|copy|rm|remove)\s*\("
    r"[^\n]*minio",
    re.IGNORECASE,
)

# 解説が必要となる API コール（MEDIUM）。
API_CALL_PATTERN = re.compile(
    r"(requests\.(get|post|put|delete|session)|httpx\.(get|post|put|delete)|"
    r"client\.(get|post|put|delete)|\bfetch\s*\()",
    re.IGNORECASE,
)

# 日本語文字（ひらがな・カタカナ・漢字）。
JAPANESE_PATTERN = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]")

# 機械が解釈するトークン（日本語品質ルールで原文維持が許容される語）。
TECH_TOKEN_PATTERN = re.compile(
    r"\b(python|node|docker|compose|make|pytest|vitest|jsdom|ruff|api|url|uri|"
    r"http|https|json|yaml|yml|env|cli|ast|regex|sql|navidrome|minio|rclone|"
    r"frontend|backend|src|dist|cdn|sfc|spa|ui|id|ok|error|warning|note)\b",
    re.IGNORECASE,
)

# 英語主体のコメント検出（WARNING）。3文字以上の英単語が日本語より多い。
LATIN_WORD_PATTERN = re.compile(r"[A-Za-z]{3,}")

# 行頭コメントの種別（言語別）。
COMMENT_PREFIXES = ("#", "//", "/*", "*", "<!--", '"""', "'''")

# shebang（`#!/usr/bin/env bash`）はコメント本文ではなく実行指定のため言語チェックから除外する。
SHEBANG_PATTERN = re.compile(r"^#!")

# 単独のファイル名・パスだけからなるコメントは技術トークンのため除外する。
FILENAME_ONLY_PATTERN = re.compile(r"^[\w./\-]+$")

# コード断片（例示）からなるコメントは技術トークンのため除外する。
CODE_SNIPPET_PATTERN = re.compile(r"[=<>{}]|\.\w+\(|\bdef\b|\bfunction\b|\bimport\b")


class PolicyLinter:
    def __init__(self, root_dir: str = "."):
        self.root_dir = pathlib.Path(root_dir)
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def report(self, level: str, path: pathlib.Path, line_no: int, message: str) -> None:
        msg = f"[{level}] {path}:{line_no}: {message}"
        if level == "CRITICAL":
            self.errors.append(msg)
        elif level in ("HIGH", "MEDIUM", "WARNING"):
            self.warnings.append(msg)
        else:
            self.notes.append(msg)

    def is_excluded(self, path: pathlib.Path) -> bool:
        return any(part in EXCLUDE_DIRS for part in path.parts)

    def comment_body(self, line: str) -> str | None:
        """行がコメント（または docstring）の場合、本文を返す。"""
        stripped = line.strip()
        for prefix in COMMENT_PREFIXES:
            if stripped.startswith(prefix):
                return stripped[len(prefix):].strip()
        return None

    def check_comment_language(self, path: pathlib.Path, line_no: int, body: str) -> None:
        """日本語品質ルール: 英語を主言語とするコメントを警告する。"""
        if not body:
            return
        # shebang（`#!/usr/bin/env bash`）は実行指定のため言語チェックから除外する。
        if body.startswith("!"):
            return
        # 技術トークンだけのコメント（ファイル名・パス・コード断片）は許容する。
        if FILENAME_ONLY_PATTERN.match(body) or CODE_SNIPPET_PATTERN.search(body):
            return
        words = LATIN_WORD_PATTERN.findall(body)
        if not words:
            return
        if JAPANESE_PATTERN.search(body):
            return
        residual = [w for w in words if not TECH_TOKEN_PATTERN.fullmatch(w)]
        if residual:
            self.report(
                "WARNING", path, line_no,
                f"英語主体のコメント（日本語品質ルール）。日本語へ翻訳する: {body[:60]}",
            )

    def nearby_comment(self, lines: list[str], index: int) -> str:
        """API コール行に対する直前のコメント行（または直前の行）を返す。"""
        # 直上の行がコメントであれば、そのコメントブロック全体（最大5行）を見る。
        block: list[str] = []
        i = index - 1
        while i >= 0 and len(block) < 5:
            stripped = lines[i].strip()
            if not stripped:
                if block:
                    break
                i -= 1
                continue
            if self.comment_body(lines[i]) is None:
                break
            block.append(stripped)
            i -= 1
        if block:
            return " ".join(block)
        # 関数レベルのコメント（数行上）も解説として認める。
        for j in range(index - 1, max(index - 7, -1), -1):
            body = self.comment_body(lines[j])
            if body:
                return body
        return lines[index - 1] if index > 0 else ""

    def check_file(self, path: pathlib.Path) -> None:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            return

        for i, line in enumerate(lines, start=1):
            # 1. 秘密情報の平文（HIGH）
            match = SECRET_PATTERN.search(line)
            if match and not PLACEHOLDER_PATTERN.search(match.group(0)):
                value = match.group("value").strip("\"'")
                # 型注釈・フィールド宣言、またはテスト用のダミー値は実値ではない。
                if NON_SECRET_VALUE_PATTERN.match(value) or DUMMY_VALUE_PATTERN.match(value):
                    continue
                self.report("HIGH", path, i, "平文の秘密情報の可能性。環境変数または秘密管理へ移す。")

            # 2. MinIO への直接書き込み（CRITICAL）
            if MINIO_WRITE_PATTERN.search(line):
                self.report(
                    "CRITICAL", path, i,
                    "MinIO への直接書き込み検出。単一の真実のソース侵害の可能性。",
                )

            # 3. API コール周辺の日本語解説欠落（MEDIUM）
            # tests/ 配下の TestClient 呼び出しは外部 API 呼び出しではないため
            # 本ルールから除外する（日本語品質の WARNING は tests も対象）。
            if API_CALL_PATTERN.search(line) and "tests" not in path.parts:
                comment = self.comment_body(line)
                context = comment or self.nearby_comment(lines, i - 1)
                if not JAPANESE_PATTERN.search(context):
                    self.report(
                        "MEDIUM", path, i,
                        "API コールに日本語の解説コメントがない。",
                    )

            # 4. 日本語品質（WARNING）
            body = self.comment_body(line)
            if body:
                self.check_comment_language(path, i, body)

    def run(self) -> int:
        for root in SCAN_ROOTS:
            base = self.root_dir / root
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file() or self.is_excluded(path):
                    continue
                if path.suffix not in SOURCE_EXTS and path.name != "Dockerfile":
                    continue
                self.check_file(path)

        if self.errors:
            print("\n❌ CRITICAL ERRORS FOUND:")
            for err in self.errors:
                print(err)

        if self.warnings:
            print(f"\n⚠️ WARNINGS FOUND ({len(self.warnings)}):")
            for warn in self.warnings:
                print(warn)

        if self.notes:
            print(f"\nℹ️ NOTES ({len(self.notes)}):")
            for note in self.notes:
                print(note)

        if not self.errors and not self.warnings:
            print("✅ 共通コーディング規則チェック通過。")

        return 1 if self.errors else 0


if __name__ == "__main__":
    sys.exit(PolicyLinter().run())
