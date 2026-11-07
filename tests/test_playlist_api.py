"""プレイリスト API とサービスのユニットテスト（Issue #12）。

実際の Ollama へは接続しない。LLM プロバイダーはダミーへ差し替え、
Navidrome もダミークライアントで置き換える。
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.llm_client import LlmUnavailableError
from backend.app.playlist_service import CatalogTrack, build_prompt, create_playlist
from backend.app.search_api import app

client = TestClient(app)


class DummyNavidromeClient:
    """カタログとして返すトラック一覧を持つダミークライアント。"""

    def __init__(self, results):
        self._results = results

    async def get_all_tracks(self):
        # Navidrome は読み取り専用で参照する（テストでは固定値を返す）。
        return {"results": self._results}


class DummyLlmClient:
    """固定の構造化出力を返すダミー LLM プロバイダー。"""

    def __init__(self, output, model: str = "gemma4:e2b"):
        self._output = output
        self.model = model
        self.calls: list[dict] = []

    async def complete_json(self, system_prompt: str, user_prompt: str, schema: dict):
        self.calls.append(
            {"system": system_prompt, "user": user_prompt, "schema": schema}
        )
        return self._output


def test_create_playlist_endpoint_success(monkeypatch):
    """指示からプレイリストが作成されることを検証する。"""
    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: DummyNavidromeClient(
            [
                {"id": "t1", "title": "Song One", "artist": "Artist A"},
                {"id": "t2", "title": "Song Two", "artist": "Artist B"},
            ]
        ),
    )
    monkeypatch.setattr(
        "backend.app.search_api.get_llm_client",
        lambda: DummyLlmClient({"playlist": [{"id": "t2", "reason": "落ち着く曲"}]}),
    )

    response = client.post("/api/v1/playlist", json={"instruction": "静かな曲から始めて"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["catalog_size"] == 2
    assert len(payload["playlist"]) == 1
    assert payload["playlist"][0]["id"] == "t2"
    assert payload["playlist"][0]["title"] == "Song Two"
    assert payload["playlist"][0]["reason"] == "落ち着く曲"


def test_create_playlist_endpoint_502_on_invalid_llm_output(monkeypatch):
    """LLM が JSON として読めない出力を返した場合 502 になる。"""
    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: DummyNavidromeClient([{"id": "t1", "title": "Song One"}]),
    )
    monkeypatch.setattr(
        "backend.app.search_api.get_llm_client",
        lambda: DummyLlmClient({"unexpected": "shape"}),
    )

    response = client.post("/api/v1/playlist", json={"instruction": "好きな曲"})
    assert response.status_code == 502
    assert response.json()["detail"] == "invalid LLM output"


def test_create_playlist_endpoint_503_on_llm_unavailable(monkeypatch):
    """Ollama に接続できない場合は 503 になる。"""

    class FailingLlmClient:
        model = "gemma4:e2b"

        async def complete_json(self, system_prompt, user_prompt, schema):
            raise LlmUnavailableError("Ollama に接続できません")

    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: DummyNavidromeClient([{"id": "t1", "title": "Song One"}]),
    )
    monkeypatch.setattr("backend.app.search_api.get_llm_client", lambda: FailingLlmClient())

    response = client.post("/api/v1/playlist", json={"instruction": "好きな曲"})
    assert response.status_code == 503
    assert response.json()["detail"] == "LLM service unavailable"


def test_create_playlist_endpoint_validation_error():
    """空の指示は 422（Pydantic バリデーション）になる。"""
    response = client.post("/api/v1/playlist", json={"instruction": ""})
    assert response.status_code == 422


def test_create_playlist_endpoint_503_on_navidrome_error(monkeypatch):
    """Navidrome 障害は 503 になる。"""

    class FailingNavidromeClient:
        async def get_all_tracks(self):
            raise RuntimeError("Navidrome unavailable")

    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: FailingNavidromeClient(),
    )
    monkeypatch.setattr(
        "backend.app.search_api.get_llm_client",
        lambda: DummyLlmClient({"playlist": []}),
    )

    response = client.post("/api/v1/playlist", json={"instruction": "好きな曲"})
    assert response.status_code == 503
    assert response.json()["detail"] == "service unavailable"


@pytest.mark.asyncio
async def test_create_playlist_filters_unknown_ids():
    """catalog に無い id（LLM が創作した曲）は除外される。"""
    settings = Settings(
        navidrome_url="http://navidrome:4533",
        navidrome_user="testuser",
        navidrome_password="testpass",
    )
    navidrome = DummyNavidromeClient(
        [
            {"id": "t1", "title": "Song One", "artist": "Artist A"},
            {"id": "t2", "title": "Song Two", "artist": "Artist B"},
        ]
    )
    llm = DummyLlmClient(
        {
            "playlist": [
                {"id": "t2", "reason": "二番目の曲"},
                {"id": "ghost", "reason": "存在しない曲"},
                {"id": "t2", "reason": "重複"},
                {"id": "t1", "reason": "一番目の曲"},
            ]
        }
    )

    result = await create_playlist("二番目の曲から", 10, navidrome, llm, settings)
    ids = [item.id for item in result.playlist]
    assert ids == ["t2", "t1"]
    assert result.model == "gemma4:e2b"
    assert result.catalog_size == 2
    # LLM へ渡すプロンプトには catalog が JSON で含まれる。
    assert "catalog" in llm.calls[0]["user"]


@pytest.mark.asyncio
async def test_create_playlist_respects_limit():
    """曲数上限（limit）で結果が切れる。"""
    settings = Settings(
        navidrome_url="http://navidrome:4533",
        navidrome_user="testuser",
        navidrome_password="testpass",
    )
    navidrome = DummyNavidromeClient(
        [{"id": f"t{i}", "title": f"Song {i}"} for i in range(1, 6)]
    )
    llm = DummyLlmClient({"playlist": [{"id": f"t{i}"} for i in range(1, 6)]})

    result = await create_playlist("5曲", 3, navidrome, llm, settings)
    assert [item.id for item in result.playlist] == ["t1", "t2", "t3"]


@pytest.mark.asyncio
async def test_create_playlist_empty_catalog():
    """カタログが空なら LLM を呼ばず空のプレイリストを返す。"""
    settings = Settings(
        navidrome_url="http://navidrome:4533",
        navidrome_user="testuser",
        navidrome_password="testpass",
    )
    llm = DummyLlmClient({"playlist": [{"id": "t1"}]})
    result = await create_playlist("好きな曲", 10, DummyNavidromeClient([]), llm, settings)

    assert result.playlist == []
    assert result.catalog_size == 0
    assert llm.calls == []


def test_build_prompt_uses_requested_limit():
    """プロンプトの選曲数上限は catalog 件数ではなく要求された limit である。

    catalog 件数を上限として LLM へ渡すと、全件分の選曲理由を書こうとして
    応答がトークン上限で切り詰められ JSON が壊れる（502 の原因）。
    """
    catalog = [CatalogTrack(id=f"t{i}", title=f"Song {i}") for i in range(1, 4)]
    prompt = build_prompt("2曲だけ", catalog, 2)
    assert "選曲数上限: 2" in prompt
    assert "catalog（3件）" in prompt
    assert "曲数上限: 3" not in prompt


@pytest.mark.asyncio
async def test_create_playlist_catalog_limit():
    """LLM へ渡すカタログは playlist_catalog_limit で切れる。"""
    settings = Settings(
        navidrome_url="http://navidrome:4533",
        navidrome_user="testuser",
        navidrome_password="testpass",
        playlist_catalog_limit=2,
    )
    navidrome = DummyNavidromeClient(
        [{"id": f"t{i}", "title": f"Song {i}"} for i in range(1, 6)]
    )
    llm = DummyLlmClient({"playlist": [{"id": "t3"}]})

    result = await create_playlist("3番目の曲", 10, navidrome, llm, settings)
    # t3 はカタログ（先頭2件）に含まれないため除外される。
    assert result.catalog_size == 2
    assert result.playlist == []
