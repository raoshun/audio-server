"""LLM プロバイダーの抽象化と Ollama 実装（Issue #12）.

プレイリスト作成で使う。ユニットテストは実際の Ollama へ接続しない
（`get_llm_client()` をモックへ差し替える）。実機の動作確認時のみ
localhost:11434 の軽量モデルを使う。

共通コーディング規則の遵守:
* 秘密情報（API キー）は使わない。Ollama は家庭内ネットワーク上の
  ローカルサービスであり、認証情報を持たない。設定値も平文でハードコードしない。
* LLM の出力は構造化 JSON schema で検証し、そのまま URL や Navidrome
  API パラメータへ連結しない。
"""

import json
from typing import Any, Protocol

import httpx

from backend.app.config import Settings


class LlmError(Exception):
    """LLM 呼び出しで発生するエラーの基底。"""


class LlmUnavailableError(LlmError):
    """Ollama に接続できない、またはタイムアウトした。"""


class LlmOutputError(LlmError):
    """LLM の出力が JSON として解釈できない、または期待した形ではない。"""


class LLMProvider(Protocol):
    """LLM プロバイダーの抽象。テストではこの形を満たすモックを注入する。"""

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """JSON schema を使って LLM を呼び出し、構造化結果を dict で返す。"""
        ...


class OllamaClient(LLMProvider):
    """Ollama の `/api/generate` を使う LLM プロバイダー.

    `format` に JSON schema を渡すことで自由記述ではなく検証可能な
    構造化出力を得る。接続先は設定（環境変数）からのみ取得する。
    """

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
    ):
        self.settings = settings
        # 設定から接続先・モデル・タイムアウトを取得する（平文の秘密情報は扱わない）。
        self.base_url = str(settings.ollama_url).rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout_seconds
        # テストでは MockTransport を注入してネットワークへ出さない。
        self._transport = transport

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Ollama を呼び出し、構造化出力を dict で返す。"""
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "format": schema,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": self.settings.ollama_num_predict,
            },
        }
        # Ollama の generate エンドポイントを呼ぶ（ローカル専用・認証情報なし）。
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as http:
            try:
                response = await http.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                raise LlmUnavailableError(f"Ollama に接続できません: {exc}") from exc

        return self._parse_output(data)

    def _parse_output(self, data: dict[str, Any]) -> dict[str, Any]:
        """Ollama の応答から構造化結果を取り出す。

        `format` に schema を渡した場合は dict で返るが、モデルによっては
        JSON 文字列として返すため、両方の形を受け付ける。
        """
        content = data.get("response")
        if isinstance(content, dict):
            return content
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                raise LlmOutputError("LLM の出力が JSON として読めません") from exc
            if isinstance(parsed, dict):
                return parsed
        raise LlmOutputError("LLM の出力が空または期待した形ではありません")


def get_llm_client() -> LLMProvider:
    """設定から LLM プロバイダーを生成する（テストではモックへ差し替える）。"""
    return OllamaClient(Settings())
