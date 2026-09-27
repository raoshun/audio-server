from fastapi.testclient import TestClient

from backend.app.search_api import app

client = TestClient(app)


def test_list_all_tracks_success(monkeypatch):
    """Ensure the /api/v1/tracks endpoint returns the client results.

    The Navidrome client is mocked to return a predictable list of tracks.
    The endpoint should wrap the result in a ``{"results": [...]}`` payload.
    """

    class DummyNavidromeClient:
        async def search_music(self, query: str, _filters=None):
            # The wildcard query is expected to be "*" for all tracks.
            assert query == "*"
            return {
                "results": [
                    {"id": "t1", "title": "Song One", "artist": "Artist A"},
                    {"id": "t2", "title": "Song Two", "artist": "Artist B"},
                ]
            }

    # Patch the helper that creates the Navidrome client instance.
    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: DummyNavidromeClient(),
    )

    response = client.get("/api/v1/tracks")
    assert response.status_code == 200
    payload = response.json()
    # The endpoint should expose the ``results`` key directly.
    assert "results" in payload
    assert isinstance(payload["results"], list)
    assert len(payload["results"]) == 2
    # Verify the first item matches the mocked data.
    first = payload["results"][0]
    assert first["id"] == "t1"
    assert first["title"] == "Song One"
    assert first["artist"] == "Artist A"
