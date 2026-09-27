"""Playwright end‑to‑end test for the DWE web UI.

The UI consists of a simple search box that sends a POST request to
``/api/v1/search/music`` and displays a list of artist results.  Clicking a
result fetches a streaming URL from ``/api/v1/track/<id>`` and plays the audio
in an ``<audio>`` element.

This test launches the application (the Docker‑compose ``backend`` service
exposes port 8000) and verifies the following user scenario:

1. Load the homepage.
2. Enter a query that matches an existing artist (``Disney`` – the default
   artist configured in ``Settings``).
3. Click the *検索* button.
4. Ensure at least one result appears.
5. Click the first result and verify that the audio player becomes visible
   and its ``src`` attribute points to a Navidrome streaming endpoint.

The test uses ``pytest-playwright`` which provides the ``page`` fixture.
The backend service must be running before the test is executed; the CI
environment typically runs ``docker compose up -d backend`` first.
"""

import re

# The test dependencies (pytest, playwright) are provided in the Docker test
# environment. Import them lazily to avoid static analysis import errors.
try:
    import pytest  # type: ignore
except ImportError:  # pragma: no cover
    pytest = None  # type: ignore

try:
    from playwright.sync_api import expect  # type: ignore
except ImportError:  # pragma: no cover
    expect = None  # type: ignore


@pytest.mark.playwright
def test_user_flow(page):
    # 1. Open the UI – backend serves static files at the root.
    # In the Docker test container, the backend service is reachable via its
    # service name.
    page.goto("http://backend:8000")

    # 2. Fill the search input with a known artist name.
    query_input = page.locator("#query")
    query_input.fill("Disney")

    # 3. Click the search button.
    page.locator("#searchBtn").click()

    # 4. Wait for at least one result item.
    result_items = page.locator("#resultList li")
    expect(result_items).to_have_count(1, timeout=5000)

    # 5. Click the first result.
    first_item = result_items.nth(0)
    # Capture the data-id attribute which holds the Navidrome track/artist id.
    track_id = first_item.get_attribute("data-id")
    first_item.click()

    # Verify the audio player appears and has a stream URL.
    player_section = page.locator(".player")
    expect(player_section).to_be_visible()
    audio = page.locator("#player")
    # The UI now uses the FastAPI proxy endpoint for streaming audio.
    expect(audio).to_have_attribute(
        "src",
        re.compile(r"/api/v1/track/stream/"),
    )
    # Optional: ensure the URL contains the captured track_id.
    if track_id:
        expect(audio).to_have_attribute("src", re.compile(track_id))
