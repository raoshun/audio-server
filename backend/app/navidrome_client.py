import asyncio
import urllib.error

# 依存関係を増やさないため、組み込み urllib を使用して HTTP リクエストを行います。
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote, urlencode

# 兄弟パッケージ ``app`` から Settings をインポートします。
from backend.app.config import Settings

class NavidromeClient:
    """DWE バックエンドが利用する Navidrome API 用非同期クライアント。
    主にアルバム取得・検索・全トラック取得を提供し、必要に応じて拡張可能。
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        # Settings から URL、認証情報、タイムアウト、アーティスト名を取得。
        self.base_url = str(settings.navidrome_url)
        self._auth_user = settings.navidrome_user
        self._auth_pass = settings.navidrome_password.get_secret_value()
        self.timeout = settings.navidrome_timeout_seconds
        self.dwe_artist = settings.dwe_artist

    def auth_params(self) -> dict:
        """認証パラメータへの公開アクセサ。
        Subsonic API 用認証クエリを返す (固定 `c`, `v` を含む)。"""
        return {
            "u": self._auth_user,
            "p": self._auth_pass,
            "c": "cli",
            "v": "1.16.1",
        }

    async def _get_xml(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> ET.Element:
        """GET で Subsonic XML を取得し Element に変換するヘルパー。"""
        query_dict: dict = self.auth_params()
        if params:
            query_dict.update(params)
        query = urlencode(query_dict, safe="*", quote_via=quote)
        url = f"{self.base_url.rstrip('/')}{endpoint}?{query}"
        # Perform a synchronous request inside the async context.
        # ``urllib.request.urlopen`` respects a timeout argument.

        def _fetch():
            # デバッグ出力 (必要最低限)
            print(f"[NavidromeClient] GET {url}")
            try:
                with urllib.request.urlopen(
                    url,
                    timeout=self.timeout,
                ) as response:
                    status = getattr(response, "status", "N/A")
                    print(
                        f"[NavidromeClient] GET {url} -> status {status}"
                    )
                    return response.read().decode()
            except urllib.error.HTTPError as e:
                print(
                    f"[NavidromeClient] HTTPError {e.code} for {url}: "
                    f"{e.reason}"
                )
                raise
        text = await asyncio.to_thread(_fetch)
        try:
            return ET.fromstring(text)
        except ET.ParseError as e:
            raise ValueError(f"XML のパースに失敗しました (URL: {url}): {e}") from e

    async def _search_artist_id(self, name: str) -> str:
        """Navidrome でアーティスト名を検索し、ID を返します。

        ``/artist/{id}/albums`` エンドポイントは任意の名前を受け付けず、
        数値または UUID のアーティスト ID が必要です。そのため検索リクエストを
        行い、最初にマッチした結果の ``id`` フィールドを取得します。該当が無い
        場合は ``ValueError`` を送出します。
        """
        # Navidrome は汎用検索エンドポイントを提供しています。ここでは検索対象を
        # アーティストオブジェクトに限定するため ``type`` クエリパラメータを使用します。
        # Subsonic の ``/rest/search`` エンドポイント (XML を返す) を呼び出します。
        # アーティストが見つからない場合は例外を送出し、広範なフォールバックは
        # 行いません (コードの Lint を保つため)。
        root = await self._get_xml(
            "/rest/search2",
            {"query": name, "type": "artist"},
        )

        # XML には名前空間が付くことがあります。全要素を走査し、ローカルタグ名 ``artist``
        # と一致する要素を探します。
        for artist_el in root.iter():
            if (
                artist_el.tag.split('}')[-1] == "artist"
                and artist_el.attrib.get("name", "").lower() == name.lower()
            ):
                return str(artist_el.attrib.get("id"))
        raise ValueError(f"Navidrome でアーティスト '{name}' が見つかりませんでした")

    async def list_albums(self) -> dict:
        """アルバム一覧を取得する。

        Navidrome の ``getAlbums`` 端点は 404 を返すため、``search3`` の
        ``album`` フィルタを利用し、``dwe_artist`` に一致するアルバムを返す。
        各アルバムは ``{id, title, artist}`` 形式の辞書として返す。
        """
        root = await self._get_xml(
            "/rest/search3", {"album": self.dwe_artist},
        )
        # <album> 要素を全走査し、一覧を構築する。タグには名前空間が付く
        # ことがあるためローカルタグ名で比較する。
        albums: list[dict[str, str | None]] = []
        for el in root.iter():
            if el.tag.split("}")[-1] == "album":
                albums.append({
                    "id": el.attrib.get("id"),
                    "title": el.attrib.get("name"),
                    "artist": el.attrib.get("artist"),
                })
        return {"albums": albums}

    async def get_album_tracks(self, album_id: str) -> dict:
        """アルバムIDから収録トラック一覧を取得する。

        Subsonic の ``getAlbumById`` 端点が 404 を返すため、``search3`` の
        名前クエリでアルバムに属する曲を取得する。各曲の ``parent`` 属性が
        ``album_id`` と一致するため、それで最終的に絞り込む。
        各トラックは ``{id, title, artist, album, albumId}`` 形式の辞書として返す。
        ローカルの音楽ディレクトリへはフォールバックしない。
        """
        # album_id からアルバム名を取得する。list_albums() で取得した一覧から
        # ID をキーにタイトルを検索する。
        album_name: str | None = None
        for album in (await self.list_albums())["albums"]:
            if album["id"] == album_id:
                album_name = album["title"]
                break
        # アルバム名が見つからない場合は空結果を返す。
        if album_name is None:
            return {"album_id": album_id, "tracks": []}
        # search3 の名前クエリで該当アルバムに属する曲を取得する。``type=track``
        # を指定して曲のみを返し、``size`` を大きめに設定して一覧を網羅する。
        search_params = {"query": album_name, "type": "track", "size": "1000"}
        root = await self._get_xml("/rest/search3", search_params)
        # <song> 要素を全走査し、アルバムID（parent 属性）でフィルターする。
        # タグには名前空間が付くことができるためローカルタグ名で比較する。
        tracks: list[dict[str, str | None]] = []
        for el in root.iter():
            if el.tag.split("}")[-1] == "song" and el.attrib.get("parent") == album_id:
                tracks.append({
                    "id": el.attrib.get("id"),
                    "title": el.attrib.get("title"),
                    "artist": el.attrib.get("artist"),
                    "album": el.attrib.get("album"),
                    "albumId": el.attrib.get("parent"),
                })
        return {"album_id": album_id, "tracks": tracks}

    async def search_music(
        self,
        query: str,
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Search for songs in Navidrome matching the query.

        Returns song-shaped results ``{id, title, artist}`` so that the
        frontend can display the title and stream the track id directly.
        Local fallback to the DWE music directory is intentionally disabled.
        """
        query_dict: dict[str, str] = {
            "query": query,
            "type": "track",
            "artist": (filters or {}).get("artist", ""),
        }
        query_dict = {k: v for k, v in query_dict.items() if v}
        # Query is required by the backend.
        query_dict["query"] = query
        root = await self._get_xml("/rest/search2", query_dict)
        # Match song elements by local tag name regardless of namespace.
        songs = [
            el for el in root.iter()
            if el.tag.split("}")[-1] == "song"
        ]
        # Build song-shaped results that match the frontend contract.
        results = [
            {
                "id": el.attrib.get("id"),
                "title": el.attrib.get("title"),
                "artist": el.attrib.get("artist"),
            }
            for el in songs
        ]
        return {"results": results}

    async def get_all_tracks(self) -> dict:
        """全トラックを取得し、{'results': [...]} 形式で返す。
        ``/rest/getSongs`` が無いため、ワイルドカード検索で全件取得。
        """
        # Perform a search with a wildcard query that matches all tracks.
        # ``size`` is set high enough to cover the catalog; Navidrome caps the
        # maximum internally (e.g., 5000), but 1000 is ample for typical use.
        # ``type=track`` ensures Navidrome returns song entries rather than
        # defaulting to artists. Without this parameter the endpoint may
        # respond with a 404 or an empty result set.
        search_params = {"query": "*", "size": "1000", "type": "track"}
        # デバッグ用 URL 出力
        auth = self.auth_params()
        auth.update(search_params)
        query = urlencode(auth, safe="*", quote_via=quote)
        print(
            f"[NavidromeClient] get_all_tracks URL: "
            f"{self.base_url.rstrip('/')}/rest/search2?{query}"
        )

        root = await self._get_xml("/rest/search2", search_params)

        # Extract <song> elements. The tag may include a namespace, so we
        # compare the local name after the ``}`` separator.
        tracks: list[dict[str, str | None]] = []
        for el in root.iter():
            if el.tag.split('}')[-1] == "song":
                # Copy all attributes; values are already strings.
                tracks.append(dict(el.attrib))

        return {"results": tracks}

    @staticmethod
    def _build_query_string(params: dict) -> str:
        """検索パラメータを URL エンコードした文字列に変換する。"""
        return "&".join(
            f"{quote(str(k))}={quote(str(v))}" for k, v in params.items()
        )
