from fastapi.testclient import TestClient

from backend.app.search_api import app


client = TestClient(app)


def test_search_music_success(monkeypatch):
    class DummyNavidromeClient:
        async def search_music(self, query: str, filters=None):
            return {
                "results": [
                    {
                        "id": "a1",
                        "title": "Greatest Hits",
                        "artist": "Artist One",
                        "album": "Greatest Hits",
                        "source": "navidrome",
                    }
                ]
            }

    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: DummyNavidromeClient(),
    )

    response = client.post(
        "/api/v1/search/music",
        json={
            "query": "Artist One Greatest Hits",
            "filters": {"artist": "Artist One"},
        },
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["artist"] == "Artist One"


def test_search_music_503_on_navidrome_error(monkeypatch):
    class FailingNavidromeClient:
        async def search_music(self, query: str, filters=None):
            raise RuntimeError("Navidrome unavailable")

    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        lambda: FailingNavidromeClient(),
    )

    response = client.post(
        "/api/v1/search/music",
        json={"query": "Artist One Greatest Hits"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "service unavailable"


def test_search_music_invalid_query():
    response = client.post(
        "/api/v1/search/music",
        json={"filters": {"artist": "Artist One"}},
    )

    assert response.status_code == 422
