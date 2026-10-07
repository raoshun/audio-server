import logging
from typing import Any
from urllib.parse import quote

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from backend.app.config import Settings
from backend.app.navidrome_client import NavidromeClient

# Docker コンテナ内で stdout / stderr にログを出力するため、モジュールレベルのロギングを設定します。
# これにより、現在 503 応答になるようなバリデーションやランタイムエラーが可視化されます。
logging.basicConfig(level=logging.INFO)

# Settings のロードをインポート時に試み、ValidationError が即座に記録されるようにします。
# API はリクエストごとにも Settings を作成しますが、早期に可視化できるとデバッグが楽になります。
# ValidationError は上記で BaseModel と Field をインポートしています。
logger = logging.getLogger(__name__)

try:
    _startup_settings = Settings()
    # 行長制限を超えないように設定情報をログ出力します。
    logger.info(
        "[search_api] Settings loaded successfully: %s",
        _startup_settings,
    )
except ValidationError as e:  # pragma: no cover - 実行時にハンドリング
    logger.error("[search_api] Settings load error: %s", e)


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
    # エンドポイントが呼ばれたことを確認するため、ペイロードとともにログ出力します。
    logger.info("[search_music] received payload: %s", payload.model_dump())
    try:
        client = get_client()
        response = await client.search_music(payload.query, payload.filters)
        return MusicSearchResponse(results=response.get("results", []))
    except Exception as exc:  # pragma: no cover - API behavior guard
        # デバッグを支援するため例外詳細をログ出力します（Docker ログに記録されます）。
        # 遅延フォーマットを使用して、早期の文字列補間を避けます。
        logger.error("[search_music] error: %r", exc)
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
    # 公開アクセサを使用して認証パラメータを取得します。
    auth_params = client.auth_params()
    # 適切な URL エンコードを使用してクエリ文字列を構築します。
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
    # get_track_url と同じ URL を構築します。
    client = get_client()
    base = client.base_url.rstrip('/')
    auth_params = client.auth_params()
    query = "&".join(f"{k}={quote(str(v))}" for k, v in auth_params.items())
    stream_url = f"{base}/rest/stream?id={track_id}&{query}"
    # 着リクエストのヘッダがあればログ出力します。
    if request:
        logger.info(
            "[proxy_track_stream] incoming request headers: %s",
            dict(request.headers),
        )
    logger.info("[proxy_track_stream] fetching %s", stream_url)
    # Navidrome へストリームリクエストを送信します。長時間待機しないようタイムアウトを設定します。
    # User-Agent ヘッダがないと Navidrome が 404 を返すため、ブラウザ類似の UA を含めます。
    custom_headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Referer": f"{client.base_url}/",
        # Referer と一致する Origin ヘッダを要求するサーバーがあります。
        "Origin": f"{client.base_url}",
    }
    session = requests.Session()
    req = requests.Request("GET", stream_url, headers=custom_headers)
    prepped = session.prepare_request(req)
    resp = session.send(prepped, stream=True, timeout=10)
    if resp.status_code != 200:
        # 応答本文のスニペットをログ出力してデバッグを容易にします。
        try:
            body_snippet = resp.text[:200]
        except requests.RequestException:
            body_snippet = "<unable to read body>"
        logger.error(
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
        # 認証問題のデバッグのため設定値をログ出力します。
        # ダミーのテストクライアントは本物の Navidrome クライアントが使う全設定属性を持たないため、
        # getattr に適切なフォールバックを渡し、テスト中に AttributeError が発生しないようにします。
        logger.info(
            "[list_all_tracks] Settings: user=%s, timeout=%s",
            getattr(
                getattr(client, "settings", None),
                "navidrome_user",
                "<no user>",
            ),
            getattr(client, "timeout", "<no timeout>"),
        )
        # Navidrome の ``/rest/search2`` エンドポイントにワイルドカードを付けて照会する、
        # 明示的な ``get_all_tracks`` メソッドを優先します。
        # テストスイートは ``search_music`` のみを実装するダミークライアントを提供するため、
        # その場合はかつて全トラックを返したワイルドカード検索にフォールバックします。
        try:
            response = await client.get_all_tracks()
        except AttributeError:
            # ``get_all_tracks`` が実装されていないクライアント用の相互互換フォールバック。
            response = await client.search_music("*", None)
        # 辞書に ``results`` リストが含まれるようにします。
        return {"results": response.get("results", [])}
    except Exception as exc:  # pragma: no cover - 防御的
        logger.error("[list_all_tracks] error: %r", exc)
        raise HTTPException(
            status_code=503,
            detail="service unavailable",
        ) from exc


# ---------------------------------------------------------------------------
# Album listing + album-detail endpoints (Navidrome-only data source)
# ---------------------------------------------------------------------------


class AlbumListResponse(BaseModel):
    albums: list[dict[str, Any]]


class AlbumDetailResponse(BaseModel):
    album_id: str
    tracks: list[dict[str, Any]]


@app.get("/api/v1/albums", response_model=AlbumListResponse)
async def list_albums():
    """Return the album list from Navidrome.

    The album list is fetched from the ``list_albums`` Navidrome client
    method (``/rest/getAlbums``). Local directory fallback is
    intentionally disabled.
    """
    try:
        client = get_client()
        response = await client.list_albums()
        return AlbumListResponse(albums=response.get("albums", []))
    except Exception as exc:  # pragma: no cover - 防御的
        logger.error("[list_albums] error: %r", exc)
        raise HTTPException(
            status_code=503,
            detail="service unavailable",
        ) from exc


@app.get("/api/v1/albums/{album_id}", response_model=AlbumDetailResponse)
async def get_album_detail(album_id: str):
    """Return the tracks contained in a single album.

    The album detail is fetched from the ``get_album_tracks`` Navidrome
    client method (``/rest/getAlbumById``). Local directory fallback is
    intentionally disabled.
    """
    try:
        client = get_client()
        response = await client.get_album_tracks(album_id)
        return AlbumDetailResponse(
            album_id=response.get("album_id", album_id),
            tracks=response.get("tracks", []),
        )
    except Exception as exc:  # pragma: no cover - 防御的
        logger.error("[get_album_detail] error: %r", exc)
        raise HTTPException(
            status_code=503,
            detail="service unavailable",
        ) from exc


# ---------------------------------------------------------------------------
# Frontend static files
# ---------------------------------------------------------------------------
# Serve UI static files from the frontend/dist directory inside the container.
# The frontend is built with Vite (node image, frontend/Dockerfile) and the
# build output is placed in frontend/dist. This mount is placed after API routes
# so that the API endpoints are matched before the static file fallback.
# FastAPI checks routes first, then falls back to mounted applications, but
# moving the mount clarifies intent and avoids potential path‑resolution
# edge cases in testing environments.
# NOTE: frontend/dist must be built before the backend starts (e.g. via
# `docker compose build frontend` or `npm run build` in frontend/).
app.mount(
    "/",
    StaticFiles(directory="/app/frontend/dist", html=True),
    name="frontend",
)
