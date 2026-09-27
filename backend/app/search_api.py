# ruff: noqa
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request  # type: ignore
from fastapi.staticfiles import StaticFiles  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

from backend.app.config import Settings
from backend.app.navidrome_client import NavidromeClient

import logging
import requests
from fastapi.responses import StreamingResponse

# Docker コンテナ内で stdout / stderr にログを出力するため、基本的なロギングを設定します。
# これにより、現在 503 応答になるようなバリデーションやランタイムエラーが可視化されます。
logging.basicConfig(level=logging.INFO)

# Settings のロードをインポート時に試み、ValidationError が即座に記録されるようにします。
# API はリクエストごとにも Settings を作成しますが、早期に可視化できるとデバッグが楽になります。
# ValidationError は上記で BaseModel と Field をインポートしています。

try:
    _startup_settings = Settings()
    # 行長制限を超えないように設定情報をログ出力します。
    logging.info(
        "[search_api] Settings loaded successfully: %s",
        _startup_settings,
    )
except Exception as e:  # pragma: no cover - 実行時にハンドリング  # noqa: BLE001
    logging.error("[search_api] Settings load error: %s", e)


class MusicSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    filters: dict[str, str] | None = None


class MusicSearchResponse(BaseModel):
    results: list[dict[str, Any]]


def get_client() -> NavidromeClient:
    """Create the Navidrome client from app settings."""
    return NavidromeClient(Settings())


app = FastAPI(title="DWE Music Search API")


@app.post("/api/v1/search/music", response_model=MusicSearchResponse)
async def search_music(payload: MusicSearchRequest):
    """Search music via Navidrome while forbidding local fallback."""
    # Log entry and payload to verify that the endpoint is hit.
    logging.info("[search_music] received payload: %s", payload.dict())
    try:
        client = get_client()
        response = await client.search_music(payload.query, payload.filters)
        return MusicSearchResponse(results=response.get("results", []))
    except Exception as exc:  # pragma: no cover - API behavior guard
        # Log the exception details to aid debugging (captured in Docker logs).
        # Use lazy formatting to avoid premature string interpolation.
        logging.error("[search_music] error: %r", exc)
        raise HTTPException(
            status_code=503,
            detail="service unavailable",
        ) from exc

# ---------------------------------------------------------------------------
# Frontend static files
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Track streaming endpoint (internal Navidrome Subsonic API)
# ---------------------------------------------------------------------------
# Ensure a blank line before the route decorator as per style guide.


@app.get("/api/v1/track/{track_id}")
async def get_track_url(track_id: str):
    """Return a Navidrome streaming URL for the given track ID.

    The URL includes the required authentication query parameters.  The
    client stores the base URL and authentication details; we reuse them.
    """
    client = get_client()
    base = client.base_url.rstrip('/')
    # Access protected method of NavidromeClient to obtain auth params.
    # Use public accessor to retrieve authentication parameters.
    auth_params = client.auth_params()
    # Build query string with proper URL‑encoding.
    query = "&".join(f"{k}={quote(str(v))}" for k, v in auth_params.items())
    stream_url = f"{base}/rest/stream?id={track_id}&{query}"
    return {"stream_url": stream_url}

# ---------------------------------------------------------------------------
# Proxy endpoint for streaming a track through this service.
# ---------------------------------------------------------------------------


@app.get("/api/v1/track/stream/{track_id}")
def proxy_track_stream(track_id: str, request: Request):
    """Fetch the raw audio stream from Navidrome and return it to the client.

    The Navidrome instance is only reachable from within the Docker network
    (hostname ``navidrome``). Browsers cannot access it directly, so we proxy
    the request through this FastAPI service. The returned response streams the
    content directly to the client, preserving the original ``Content-Type``
    (e.g., ``audio/flac``).
    """
    # Forward relevant headers from the incoming FastAPI request.
    client = get_client()
    # Build the same URL that ``get_track_url`` would produce.
    base = client.base_url.rstrip('/')
    auth_params = client.auth_params()
    query = "&".join(f"{k}={quote(str(v))}" for k, v in auth_params.items())
    stream_url = f"{base}/rest/stream?id={track_id}&{query}"
    # Log the target stream URL for debugging.
    # Log incoming request headers if available for debugging.
    if request:
        logging.info(
            "[proxy_track_stream] incoming request headers: %s",
            dict(request.headers),
        )
    logging.info("[proxy_track_stream] fetching %s", stream_url)
    # Perform a streamed request to Navidrome.
    # Include a reasonable timeout to avoid hanging indefinitely.
    # Log the exact URL we are about to request for debugging purposes.
    logging.info("[proxy_track_stream] final request URL: %s", stream_url)
    # Some services (including Navidrome) reject requests that lack a typical
    # User-Agent header, leading to a 404. We include a minimal UA to mimic a
    # browser request.
    # Include typical Accept header to satisfy Navidrome expectations.
    # Navidrome may enforce strict header checks (e.g., Referer or Host).
    # Include typical browser-like headers to satisfy those checks.
    # Navidrome appears to identify the client by the User‑Agent header.
    # The logs show successful streams with a client type "DWE-Proxy".
    # Use that identifier and let ``requests`` set the Host automatically.
    # Build headers mimicking a successful DWE‑Proxy client.
    # Use the exact User-Agent string that was observed to succeed when calling
    # Navidrome directly. Navidrome is strict about this header and will return
    # a 404 for unknown agents.
    # Navidrome enforces a realistic User-Agent header. Use a common browser UA
    # string to avoid 404 responses caused by strict header validation.
    custom_headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Referer": f"{client.base_url}/",
        # Some servers require an Origin header that matches the
        # Referer header value.
        "Origin": f"{client.base_url}",
    }
    # Do NOT forward the incoming Host header; let ``requests`` set the
    # correct Host based on the URL.
    # Log the request headers to aid debugging of 404 responses.
    logging.info("[proxy_track_stream] request headers: %s", custom_headers)
    # Prepare request to log the exact headers being sent.
    session = requests.Session()
    req = requests.Request("GET", stream_url, headers=custom_headers)
    prepped = session.prepare_request(req)
    logging.info("[proxy_track_stream] prepared request URL: %s", prepped.url)
    logging.info(
        "[proxy_track_stream] prepared request headers: %s",
        prepped.headers,
    )
    resp = session.send(
        prepped,
        stream=True,
        timeout=10,
    )
    logging.info(
        "[proxy_track_stream] Navidrome response %s",
        resp.status_code,
    )
    if resp.status_code != 200:
        # Log a snippet of the response body for easier debugging.
        try:
            body_snippet = resp.text[:200]
        except requests.RequestException:  # noqa: BLE001
            body_snippet = "<unable to read body>"
        logging.error(
            "[proxy_track_stream] unexpected status %s, body snippet: %s",
            resp.status_code,
            body_snippet,
        )
    # Propagate the status code and content type.
    return StreamingResponse(
        resp.iter_content(chunk_size=8192),
        media_type=resp.headers.get(
            "Content-Type", "application/octet-stream"
        ),
        status_code=resp.status_code,
    )

# ---------------------------------------------------------------------------
# Endpoint to list all tracks (full catalog)
# ---------------------------------------------------------------------------


@app.get("/api/v1/tracks")
async def list_all_tracks():
    """Return a list of all tracks available in Navidrome.

    The Navidrome API does not provide a dedicated "list all tracks"
    endpoint, but a wildcard search ("*") returns the full catalog. This
    implementation forwards such a request to ``search_music``.
    """
    try:
        client = get_client()
        # Log settings values for debugging authentication issues.
        # Use the public attribute from the client settings for the username.
        # The dummy test client may not have the full Settings attribute used
        # by the real Navidrome client. Use ``getattr`` with sensible
        # fall‑backs so the log statement never raises an ``AttributeError``
        # during tests.
        logging.info(
            "[list_all_tracks] Settings: user=%s, timeout=%s",
            getattr(
                getattr(client, "settings", None),
                "navidrome_user",
                "<no user>",
            ),
            getattr(client, "timeout", "<no timeout>"),
        )
        # Prefer the explicit ``get_all_tracks`` method, which queries the
        # Navidrome ``/rest/search2`` endpoint with a wildcard.
        # The test suite provides a dummy client that only implements
        # ``search_music``; in that case we fall back to the wildcard search
        # that historically returned all tracks.
        try:
            response = await client.get_all_tracks()
        except AttributeError:
            # Compatibility fallback for clients lacking ``get_all_tracks``.
            response = await client.search_music("*", None)
        # Ensure the dict contains a ``results`` list.
        return {"results": response.get("results", [])}
    except Exception as exc:  # pragma: no cover - defensive
        logging.error("[list_all_tracks] error: %r", exc)
        raise HTTPException(
            status_code=503,
            detail="service unavailable",
        ) from exc

# ---------------------------------------------------------------------------
# Frontend static files
# ---------------------------------------------------------------------------
# Serve UI static files from the frontend directory inside the container.
# This mount is placed after API routes so that the API endpoints are matched
# before the static file fallback.
# FastAPI checks routes first, then falls back to mounted applications, but
# moving the mount clarifies intent and avoids potential path‑resolution
# edge cases in testing environments.
app.mount(
    "/",
    StaticFiles(directory="/app/frontend", html=True),
    name="frontend",
)
