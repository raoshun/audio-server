from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from backend.app.config import Settings
from backend.app.navidrome_client import NavidromeClient


@pytest.fixture
def settings_fixture():
    """Provide a Settings instance with harmless test values."""
    return Settings(
        navidrome_url="http://example.com",
        navidrome_user="user",
        navidrome_password=SecretStr("secret"),
        navidrome_timeout_seconds=5,
        dwe_music_dir=Path("/tmp/nonexistent-dwe-music"),
        dwe_artist="Artist One",
    )


@pytest.mark.asyncio
async def test_list_albums_returns_json(settings_fixture):
    """Ensure ``list_albums`` performs a GET request and returns the parsed
    JSON.

    The aiohttp ``ClientSession`` is patched to return a controlled response.
    """
    expected = {"albums": ["a1", "a2"]}

    # Create an async mock for the response object.
    mock_resp = AsyncMock()
    # Make the mock response work with "async with".
    mock_resp.__aenter__.return_value = mock_resp
    mock_resp.__aexit__.return_value = None
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = expected

    # ``ClientSession`` is used as an async context manager; we mock both
    # the ``__aenter__`` returning an object with a ``get`` method that
    # returns the mock response directly.
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.get.return_value = mock_resp

    with patch(
        "backend.app.navidrome_client.ClientSession",
        return_value=mock_session,
    ):
        client = NavidromeClient(settings_fixture)
        result = await client.list_albums()

        assert result == expected
