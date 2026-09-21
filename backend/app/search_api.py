from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.app.config import Settings
from backend.app.navidrome_client import NavidromeClient


class MusicSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    filters: Optional[Dict[str, str]] = None


class MusicSearchResponse(BaseModel):
    results: list[dict[str, Any]]


def get_client() -> NavidromeClient:
    """Create the Navidrome client from app settings."""
    return NavidromeClient(Settings())


app = FastAPI(title="DWE Music Search API")


@app.post("/api/v1/search/music", response_model=MusicSearchResponse)
async def search_music(payload: MusicSearchRequest):
    """Search music via Navidrome while forbidding local fallback."""
    try:
        client = get_client()
        response = await client.search_music(payload.query, payload.filters)
        return MusicSearchResponse(results=response.get("results", []))
    except Exception as exc:  # pragma: no cover - API behavior guard
        raise HTTPException(
            status_code=503,
            detail="service unavailable",
        ) from exc
