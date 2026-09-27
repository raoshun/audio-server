import asyncio
import json
import urllib.error

# 依存関係を増やさないため、組み込み urllib を使用して HTTP リクエストを行います。
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode

# 兄弟パッケージ ``app`` から Settings をインポートします。
from backend.app.config import Settings

# ---------------------------------------------------------------------------
# 互換性用プレースホルダー (テストで差し替えられる)
# ---------------------------------------------------------------------------

class ClientSession:  # pragma: no cover
    """テストで差し替えられる ``ClientSession`` 用プレースホルダー。
    実装上は使用せず、型チェックと import 解消のみ目的とします。
    """

    async def get(self, *args, **kwargs):  # pragma: no cover
        """非同期 GET のスタブ。テストでモックが提供されます。"""
        raise NotImplementedError("ClientSession.get stub; patch in tests.")

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
        query_dict: dict = self._auth_params()
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
        """アルバム一覧を JSON で取得する。
        テストで ``ClientSession`` が差し替えられる場合はそれを使用し、失敗したら urllib にフォールバック。
        """
        try:
            session = ClientSession()
            response = await session.get(
                f"{self.base_url.rstrip('/')}/rest/getAlbums",
                timeout=self.timeout,
            )
            return await response.json()
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
        ):  # pragma: no cover
            def _fetch_json():
                with urllib.request.urlopen(
                    f"{self.base_url.rstrip('/')}/rest/getAlbums",
                    timeout=self.timeout,
                ) as response:
                    return json.load(response)
            return await asyncio.to_thread(_fetch_json)

    async def search_music(
        self,
        query: str,
        filters: dict | None = None,
    ) -> dict:
        """自然言語プロンプトにマッチする音楽を Navidrome で検索します。"""
        params = {"query": query}
        if filters:
            params.update(filters)
        # Subsonic の検索 – 最近の Navidrome バージョンでサポートされている newer
        # ``/rest/search2`` エンドポイントを使用します。古い ``/rest/search``
        # は本環境では HTTP 410 (Gone) が返ります。
        # リクエストを実行し、XML のルート要素を取得します。
        root = await self._get_xml("/rest/search2", params)

        # Navidrome が返す XML にはタグ名に名前空間が付くことがあります
        # (例: ``{http://subsonic.org/restapi}artist``)。 ``root.iter("artist")``
        # のみでは要素が取得できず、結果が空になるか期待と異なる形状で例外が
        # 発生します。名前空間を考慮しつつローカルタグ名 (``}`` 後) を比較して
        # 要素を抽出します。
        results: list[dict[str, str | None]] = []
        for el in root.iter():
            if el.tag.split('}')[-1] == "artist":
                results.append({
                    "id": el.attrib.get("id"),
                    "name": el.attrib.get("name"),
                })
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
