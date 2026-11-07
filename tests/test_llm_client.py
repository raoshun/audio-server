"""Ollama クライアントのユニットテスト（Issue #12）。

テストは実際の Ollama（localhost:11434）へ接続しない。`httpx.MockTransport`
を注入して応答形のみ検証する。実機の動作確認は README の手順で行う。
"""

import httpx
import pytest

from backend.app.config import Settings
from backend.app.llm_client import (
    LlmOutputError,
    LlmUnavailableError,
    OllamaClient,
    get_llm_client,
)


def make_client(handler) -> OllamaClient:
    """テスト用の Settings に MockTransport を差し込んだクライアントを返す。"""
    settings = Settings(
        navidrome_url="http://navidrome:4533",
        navidrome_user="testuser",
        navidrome_password="testpass",
        ollama_model="gemma4:e2b",
    )
    return OllamaClient(settings, httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_complete_json_dict_response():
    """format に schema を渡した実際の形（dict の response）を検証する。"""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["payload"] = request.content
        return httpx.Response(200, json={"response": {"playlist": [{"id": "t1"}]}})

    client = make_client(handler)
    result = await client.complete_json("system", "user", {"type": "object"})

    assert result == {"playlist": [{"id": "t1"}]}
    assert captured["path"] == "/api/generate"


@pytest.mark.asyncio
async def test_complete_json_string_response():
    """モデルが JSON 文字列で返す形も受け付けることを検証する。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": '{"playlist": [{"id": "t2"}]}'})

    client = make_client(handler)
    result = await client.complete_json("system", "user", {"type": "object"})

    assert result == {"playlist": [{"id": "t2"}]}


@pytest.mark.asyncio
async def test_complete_json_output_error():
    """JSON として読めない出力は LlmOutputError になる。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "not json"})

    client = make_client(handler)
    with pytest.raises(LlmOutputError):
        await client.complete_json("system", "user", {"type": "object"})


@pytest.mark.asyncio
async def test_complete_json_unavailable_on_connection_error():
    """接続できない場合は LlmUnavailableError になる。"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = make_client(handler)
    with pytest.raises(LlmUnavailableError):
        await client.complete_json("system", "user", {"type": "object"})


@pytest.mark.asyncio
async def test_complete_json_unavailable_on_http_status_error():
    """Ollama がエラーステータスを返した場合も LlmUnavailableError。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    client = make_client(handler)
    with pytest.raises(LlmUnavailableError):
        await client.complete_json("system", "user", {"type": "object"})


def test_get_llm_client_uses_settings():
    """ファクトリは設定からモデル名と接続先を得る（平文の秘密情報は使わない）。"""
    client = get_llm_client()
    assert client.model
    assert str(client.base_url).startswith("http")
