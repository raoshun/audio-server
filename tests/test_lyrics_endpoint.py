"""Tests for the ``/api/v1/lyrics/{track_id}`` endpoint.

The endpoint reads synced lyrics from Navidrome's OpenSubsonic
``getLyricsBySongId`` via ``NavidromeClient.get_lyrics``. To avoid network
calls, the ``get_client`` factory is monkey-patched with a dummy client that
returns a fixed lyrics payload.
"""

from fastapi.testclient import TestClient

from backend.app.search_api import app

client = TestClient(app)


def _patch_client(monkeypatch, factory):
    # ``get_client`` をダミークライアント工場へ差し替える（テストはネットワークを使わない）。
    monkeypatch.setattr("backend.app.search_api.get_client", factory)


def test_get_lyrics_success(monkeypatch):
    class DummyLyricsClient:
        async def get_lyrics(self, track_id: str):
            return {
                "track_id": track_id,
                "synced": True,
                "lines": [
                    {"start": 0, "text": "First line"},
                    {"start": 11640, "text": "Second line"},
                ],
            }

    _patch_client(monkeypatch, lambda: DummyLyricsClient())

    response = client.get("/api/v1/lyrics/t1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["track_id"] == "t1"
    assert payload["synced"] is True
    assert payload["lines"][0] == {"start": 0, "text": "First line"}
    assert payload["lines"][1]["start"] == 11640


def test_get_lyrics_returns_empty_lines(monkeypatch):
    class EmptyLyricsClient:
        async def get_lyrics(self, track_id: str):
            return {"track_id": track_id, "synced": False, "lines": []}

    _patch_client(monkeypatch, lambda: EmptyLyricsClient())

    response = client.get("/api/v1/lyrics/t2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["synced"] is False
    assert payload["lines"] == []


def test_get_lyrics_503_on_navidrome_error(monkeypatch):
    class FailingLyricsClient:
        async def get_lyrics(self, track_id: str):
            raise RuntimeError("Navidrome unavailable")

    _patch_client(monkeypatch, lambda: FailingLyricsClient())

    response = client.get("/api/v1/lyrics/t3")

    assert response.status_code == 503
    assert response.json()["detail"] == "service unavailable"
