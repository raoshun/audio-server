import inspect
import urllib.request
from pathlib import Path

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
async def test_list_albums_returns_json(settings_fixture, monkeypatch):
    """``list_albums`` は ``search3`` の ``album`` フィルタでアルバム一覧を返す。

    ``getAlbums`` 端点は 404 を返すため実装は ``search3`` を使う。返り値は
    ``{id, title, artist}`` 形式の辞書をまとめた ``{"albums": [...]}``。
    """
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<response xmlns="http://subsonic.org/restapi">'
        '<album id="album-1" name="Album One" artist="Artist One"/>'
        '<album id="album-2" name="Album Two" artist="Artist Two"/>'
        "</response>"
    )

    client = NavidromeClient(settings_fixture)
    client.dwe_artist = "Disney's World of English"
    client.base_url = "http://example.com"
    captured: dict[str, str] = {}

    def fake_urlopen(url, timeout=None):
        captured["url"] = url
        return _FakeResponse(xml)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = await client.list_albums()

    albums = result["albums"]
    assert len(albums) == 2
    assert albums[0] == {
        "id": "album-1",
        "title": "Album One",
        "artist": "Artist One",
    }
    assert albums[1]["id"] == "album-2"
    assert albums[1]["title"] == "Album Two"
    # search3 の album フィルタが含まれているか検証する。
    assert "search3" in captured["url"]
    assert "album=" in captured["url"]
    assert "Disney" in captured["url"]


# ---------------------------------------------------------------------------
# auth_params と _get_xml 以降の拡張テスト (urllib.request.urlopen を差し替え)
# ---------------------------------------------------------------------------


class _FakeResponse:
    """``urllib.request.urlopen`` の文脈に適合する偽レスポンス。"""

    def __init__(self, body: str, status: int = 200):
        self._body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body.encode("utf-8")


@pytest.mark.asyncio
async def test_auth_params_contains_fixed_cli_and_version(settings_fixture):
    """``auth_params`` はユーザー・パスワード・固定 ``c``・固定 ``v`` を返す。"""
    client = NavidromeClient(settings_fixture)
    params = client.auth_params()
    assert params["c"] == "cli"
    assert params["v"] == "1.16.1"
    assert params["u"] == "user"
    assert params["p"] == "secret"


@pytest.mark.asyncio
async def test_get_xml_parses_namespaced_xml(settings_fixture, monkeypatch):
    """``_get_xml`` は名前空間付き Subsonic XML を Element に変換する。

    ``_get_xml`` は ``asyncio.to_thread`` 内で ``urllib.request.urlopen`` を
    呼ぶため、グローバルな ``urlopen`` を差し替える。
    """
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<response xmlns="http://subsonic.org/restapi">'
        '<artist id="a42" name="Disney\'s World of English"/>'
        "</response>"
    )
    fake = _FakeResponse(xml)

    def fake_urlopen(url, timeout=None):
        # URL にクエリが含まれ、 authentication パラメータが付いているか検証する。
        assert "u=user" in url
        assert "v=1.16.1" in url
        return fake

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = NavidromeClient(settings_fixture)
    root = await client._get_xml("/rest/getAlbums")

    local_tag = root.tag.split("}")[-1]
    assert local_tag == "response"
    artists = [el for el in root.iter() if el.tag.split("}")[-1] == "artist"]
    assert len(artists) == 1
    assert artists[0].attrib["id"] == "a42"


@pytest.mark.asyncio
async def test_get_xml_invalid_xml_raises(
    settings_fixture, monkeypatch,
):
    """不正な XML が返った場合は ``_get_xml`` が ``ValueError`` を出す。"""
    def fake_urlopen(url, timeout=None):
        return _FakeResponse("<response><unclosed>")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = NavidromeClient(settings_fixture)
    with pytest.raises(ValueError):
        await client._get_xml("/rest/getAlbums")


@pytest.mark.asyncio
async def test_search_artist_id_found(settings_fixture, monkeypatch):
    """``_search_artist_id`` は名前に一致するアーティストの ID を返す。"""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<response xmlns="http://subsonic.org/restapi">'
        '<artist id="artist-99" name="Disney\'s World of English"/>'
        "</response>"
    )
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=None: _FakeResponse(xml))

    client = NavidromeClient(settings_fixture)
    client.dwe_artist = "Disney's World of English"
    client.base_url = "http://example.com"
    result = await client._search_artist_id("Disney's World of English")
    assert result == "artist-99"


@pytest.mark.asyncio
async def test_search_artist_id_not_found(
    settings_fixture, monkeypatch,
):
    """一致するアーティストがいない場合は ``_search_artist_id`` が ``ValueError`` を出す。"""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<response xmlns="http://subsonic.org/restapi"></response>'
    )
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=None: _FakeResponse(xml))

    client = NavidromeClient(settings_fixture)
    client.base_url = "http://example.com"
    with pytest.raises(ValueError):
        await client._search_artist_id("Nope Artist")


@pytest.mark.asyncio
async def test_search_music_artist_results(
    settings_fixture, monkeypatch,
):
    """``search_music`` は ``{id, title, artist}`` 形式のトラック結果を返す。"""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<response xmlns="http://subsonic.org/restapi">'
        '<song id="s1" title="Song One" artist="Artist One"/>'
        '<song id="s2" title="Song Two" artist="Artist Two"/>'
        "</response>"
    )
    client = NavidromeClient(settings_fixture)
    client.base_url = "http://example.com"
    captured: dict[str, str] = {}

    def fake_urlopen(url, timeout=None):
        captured["url"] = url
        return _FakeResponse(xml)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = await client.search_music("Artist", {"artist": "Artist One"})

    results = result["results"]
    assert len(results) == 2
    assert results[0] == {
        "id": "s1", "title": "Song One", "artist": "Artist One",
    }
    assert results[1]["id"] == "s2"
    assert results[1]["title"] == "Song Two"
    # type=track がクエリに含まれているか検証する。
    assert "type=track" in captured["url"]


@pytest.mark.asyncio
async def test_get_all_tracks_song_results(
    settings_fixture, monkeypatch,
):
    """``get_all_tracks`` は ``<song>`` 要素をすべて辞書として返す。"""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<response xmlns="http://subsonic.org/restapi">'
        '<song id="s1" title="Song One" artist="Artist One"/>'
        '<song id="s2" title="Song Two" artist="Artist Two"/>'
        "</response>"
    )
    captured = {}

    def fake_urlopen(url, timeout=None):
        captured["url"] = url
        return _FakeResponse(xml)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = NavidromeClient(settings_fixture)
    client.base_url = "http://example.com"
    result = await client.get_all_tracks()

    tracks = result["results"]
    assert len(tracks) == 2
    assert tracks[0]["id"] == "s1"
    assert tracks[0]["title"] == "Song One"
    # ワイルドカード検索と type=track が付いているか検証する。
    assert "query=*" in captured["url"]
    assert "type=track" in captured["url"]
    assert "size=1000" in captured["url"]


@pytest.mark.asyncio
async def test_get_album_tracks_returns_track_results(
    settings_fixture, monkeypatch,
):
    """``get_album_tracks`` は ``search3`` の名前クエリで ``<song>`` 要素を取得する。

    Subsonic の ``getAlbumById`` 端点が 404 を返すため、実装はアルバム名による
    ``search3`` 名前クエリを使い、``<song>`` の ``parent`` 属性でアルバムを
    フィルタする。返り値は ``{id, title, artist, album, albumId}`` 形式の辞書。
    """
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<response xmlns="http://subsonic.org/restapi">'
        '><album id="al42" name="Album One" artist="Artist One"/>'
        '<song id="s1" title="Song One" artist="Artist One" parent="al42" album="Album One"/>'
        '<song id="s2" title="Song Two" artist="Artist One" parent="al42" album="Album One"/>'
        '<song id="s3" title="Other Song" artist="Artist Two" parent="al99" album="Album Two"/>'
        "</response>"
    )
    assert inspect.iscoroutinefunction(NavidromeClient.get_album_tracks)
    client = NavidromeClient(settings_fixture)
    client.base_url = "http://example.com"
    captured: dict[str, str] = {}

    def fake_urlopen(url, timeout=None):
        captured["url"] = url
        return _FakeResponse(xml)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = await client.get_album_tracks("al42")

    tracks = result["tracks"]
    assert len(tracks) == 2
    assert tracks[0] == {
        "id": "s1",
        "title": "Song One",
        "artist": "Artist One",
        "album": "Album One",
        "albumId": "al42",
    }
    # 別アルバムの曲はフィルターで除外される。
    assert all(t["albumId"] == "al42" for t in tracks)
    # アルバム名による search3 クエリと type=track が付いているか验证する。
    # captured は最終 urlopen を持つため、get_album_tracks が呼ぶ search3 分岐が対象。
    assert "search3" in captured["url"]
    assert "query=Album%20One" in captured["url"]
    assert "type=track" in captured["url"]
