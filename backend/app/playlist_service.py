"""チャット指示からプレイリストを組み立てるサービス（Issue #12）.

流れ:
1. Navidrome からカタログ（トラック一覧）を取得する。音楽情報の取得元は
   Navidrome のみで、ローカル音楽ディレクトリ走査へのフォールバックは禁止。
2. LLM プロバイダーへ指示とカタログを渡し、JSON schema で選曲させる。
3. LLM の出力を Pydantic で検証し、catalog に存在しない id を除外する。

LLM の出力は文字列のまま URL や Navidrome パラメータへ連結しない。
"""

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from backend.app.config import Settings
from backend.app.llm_client import LLMProvider
from backend.app.navidrome_client import NavidromeClient

# LLM へ要求する構造化出力の JSON schema。catalog の id だけを扱うことを
# schema で明示するため、モデルが外部の曲名を創作する余地を減らす。
PLAYLIST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "playlist": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["id"],
            },
        }
    },
    "required": ["playlist"],
}


class CatalogTrack(BaseModel):
    """LLM へ渡すカタログの1曲（Navidrome の song 形状から構築する）。"""

    id: str
    title: str
    artist: str | None = None


class PlaylistItem(BaseModel):
    """検証済みのプレイリスト1曲。``reason`` は LLM の選曲理由。"""

    id: str
    title: str
    artist: str | None = None
    reason: str | None = None


class SelectionEntry(BaseModel):
    """LLM 出力の1項目。catalog 照合前なので ``title`` は持たない。"""

    id: str = Field(min_length=1)
    reason: str | None = None


class SelectionOutput(BaseModel):
    """LLM の構造化出力全体。"""

    playlist: list[SelectionEntry]


class PlaylistResult(BaseModel):
    """プレイリスト生成結果（API レスポンスのモデル）。"""

    model: str
    catalog_size: int
    playlist: list[PlaylistItem]


def build_catalog(response: dict[str, Any], limit: int) -> list[CatalogTrack]:
    """Navidrome の ``{"results": [...]}`` 応答からカタログを構築する。

    id を持たない項目は LLM が参照できないため除外し、``limit`` 件で切る。
    """
    catalog: list[CatalogTrack] = []
    for item in response.get("results", []):
        track_id = item.get("id")
        if not track_id:
            continue
        catalog.append(
            CatalogTrack(
                id=str(track_id),
                title=str(item.get("title") or item.get("name") or "Unnamed track"),
                artist=item.get("artist"),
            )
        )
        if len(catalog) >= limit:
            break
    return catalog


def build_prompt(instruction: str, catalog: list[CatalogTrack], limit: int) -> str:
    """LLM へ渡すユーザープロンプトを組み立てる。

    カタログは JSON 配列として渡す。LLM は catalog の id のみを扱える。
    曲数上限は catalog の件数ではなく要求されたプレイリスト長（``limit``）を
    示す。ここを catalog 件数にすると LLM が全件分の選曲理由を書こうとして
    応答がトークン上限で切り詰められ、JSON が壊れる（502 の原因）。
    """
    catalog_json = json.dumps(
        [{"id": t.id, "title": t.title, "artist": t.artist} for t in catalog],
        ensure_ascii=False,
    )
    return (
        f"指示: {instruction}\n\n"
        f"選曲数上限: {limit}\n\n"
        f"catalog（{len(catalog)}件）:\n{catalog_json}"
    )


async def create_playlist(
    instruction: str,
    limit: int,
    navidrome_client: NavidromeClient,
    llm_client: LLMProvider,
    settings: Settings,
) -> PlaylistResult:
    """指示からプレイリストを作成する。

    Navidrome 障害は呼び出し側へ伝播させる（API 層で 503 に変換）。
    LLM の不正出力は ``ValidationError`` / ``LlmOutputError`` として伝播させる。
    """
    # 結果の model 表記は設定値を使う（プロバイダー抽象の属性に依存しない）。
    model_name = settings.ollama_model

    # Navidrome へ全トラック（カタログ）を要求する。読み取り専用で、
    # ローカル音楽ディレクトリへのフォールバックは行わない。
    response = await navidrome_client.get_all_tracks()

    catalog = build_catalog(response, settings.playlist_catalog_limit)
    if not catalog:
        return PlaylistResult(model=model_name, catalog_size=0, playlist=[])

    output = await llm_client.complete_json(
        system_prompt=(
            "あなたは音楽プレイリスト作成アシスタントです。"
            "catalog に存在する id のみを playlist へ選んで、選曲理由を日本語で添える。"
            "catalog に無い曲名や id を創作しない。JSON のみ出力する。"
        ),
        user_prompt=build_prompt(instruction, catalog, limit),
        schema=PLAYLIST_SCHEMA,
    )

    try:
        selection = SelectionOutput.model_validate(output)
    except ValidationError as exc:
        raise ValueError(f"LLM の出力が期待した形ではありません: {exc}") from exc

    # LLM が挙げた id を catalog へ照合する。存在しない id（創作された曲）は
    # 除外し、重複は最初の1件だけ残す。順序は LLM の選曲順を尊重する。
    by_id = {track.id: track for track in catalog}
    playlist: list[PlaylistItem] = []
    seen: set[str] = set()
    for entry in selection.playlist:
        track = by_id.get(entry.id)
        if track is None or entry.id in seen:
            continue
        seen.add(entry.id)
        playlist.append(
            PlaylistItem(
                id=track.id,
                title=track.title,
                artist=track.artist,
                reason=entry.reason,
            )
        )
        if len(playlist) >= limit:
            break

    return PlaylistResult(
        model=llm_client.model,
        catalog_size=len(catalog),
        playlist=playlist,
    )
