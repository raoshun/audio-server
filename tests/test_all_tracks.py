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


def test_list_albums_success(monkeypatch):
    """Ensure the /api/v1/albums endpoint returns the album list.

    The Navidrome client is mocked to return a predictable album list.
    """

    class DummyNavidromeClient:
        async def list_albums(self):
            return {
                "albums": [
                    {"id": "al1", "title": "Album One", "artist": "Artist A"},
                    {"id": "al2", "title": "Album Two", "artist": "Artist B"},
                ],
            }

    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: DummyNavidromeClient(),
    )

    response = client.get("/api/v1/albums")
    assert response.status_code == 200
    payload = response.json()
    assert "albums" in payload
    assert isinstance(payload["albums"], list)
    assert len(payload["albums"]) == 2
    first = payload["albums"][0]
    assert first["id"] == "al1"


def test_list_albums_503_on_navidrome_error(monkeypatch):
    """Ensure the /api/v1/albums endpoint returns 503 on Navidrome failure."""

    class FailingNavidromeClient:
        async def list_albums(self):
            raise RuntimeError("Navidrome unavailable")

    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: FailingNavidromeClient(),
    )

    response = client.get("/api/v1/albums")
    assert response.status_code == 503
    assert response.json()["detail"] == "service unavailable"


def test_get_album_detail_success(monkeypatch):
    """Ensure the /api/v1/albums/{id} endpoint returns the album tracks."""

    class DummyNavidromeClient:
        async def get_album_tracks(self, album_id: str):
            assert album_id == "al1"
            return {
                "album_id": "al1",
                "tracks": [
                    {"id": "s1", "title": "Song One", "artist": "Artist A"},
                    {"id": "s2", "title": "Song Two", "artist": "Artist A"},
                ],
            }

    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: DummyNavidromeClient(),
    )

    response = client.get("/api/v1/albums/al1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["album_id"] == "al1"
    assert len(payload["tracks"]) == 2
    assert payload["tracks"][0]["id"] == "s1"


def test_get_album_detail_503_on_navidrome_error(monkeypatch):
    """Ensure the /api/v1/albums/{id} endpoint returns 503 on failure."""

    class FailingNavidromeClient:
        async def get_album_tracks(self, album_id: str):
            raise RuntimeError("Navidrome unavailable")

    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: FailingNavidromeClient(),
    )

    response = client.get("/api/v1/albums/al1")
    assert response.status_code == 503
    assert response.json()["detail"] == "service unavailable"
