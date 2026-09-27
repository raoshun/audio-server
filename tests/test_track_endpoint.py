"""Tests for the ``/api/v1/track/{track_id}`` endpoint.

The endpoint builds a Navidrome streaming URL using the ``NavidromeClient``
configuration.  To avoid network calls and dependence on the real settings,
the ``get_client`` factory is monkey‑patched to return a lightweight dummy
object that supplies the required ``base_url`` attribute and a public
``auth_params`` method.
"""

from fastapi.testclient import TestClient

from backend.app.search_api import app


class DummyClient:
    """Minimal stub mimicking :class:`NavidromeClient` for tests."""

    def __init__(self) -> None:
        # Base URL used for constructing the streaming URL.
        self.base_url = "http://dummy.navidrome.local"

    def auth_params(self) -> dict:
        # Return a static set of authentication query parameters.
        return {"u": "testuser", "p": "testpass", "c": "cli", "v": "1.16.1"}


def test_get_track_url(monkeypatch):
    """Validate that the endpoint returns the correctly formatted stream URL.

    The expected URL format is:
    ``{base}/rest/stream?id={track_id}&{query}``
    where ``query`` is built from the authentication parameters.
    """

    # Patch the ``get_client`` function used by the endpoint to return our
    # ``DummyClient`` instance.
    # Patch the ``get_client`` function used by the endpoint to return our
    # ``DummyClient`` instance. Using a named function avoids the linter's
    # "lambda may not be necessary" warning.
    def _dummy_client_factory():
        return DummyClient()

    monkeypatch.setattr(
        "backend.app.search_api.get_client",
        _dummy_client_factory,
    )

    client = TestClient(app)
    track_id = "12345"
    response = client.get(f"/api/v1/track/{track_id}")

    assert response.status_code == 200
    data = response.json()
    assert "stream_url" in data

    # Verify that the URL contains the expected components.
    expected_prefix = (
        f"http://dummy.navidrome.local/rest/stream?id={track_id}&"
    )
    assert data["stream_url"].startswith(expected_prefix)

    # Ensure all auth parameters appear in the query string.
    for key, value in DummyClient().auth_params().items():
        assert f"{key}={value}" in data["stream_url"]
