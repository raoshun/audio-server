from urllib.parse import quote, urlencode
import xml.etree.ElementTree as ET

from aiohttp import (
    ClientSession,
    ClientTimeout,
    ClientResponseError,
)
# Import Settings from the sibling ``app`` package.
from backend.app.config import Settings


class NavidromeClient:
    """Async client for a subset of Navidrome API used by the DWE backend.

    The original implementation used a synchronous ``ClientSession`` which is
    invalid.  This version makes the client fully async and adds a helper for
    GET requests.  It currently supports listing albums for the configured
    artist but can be extended for other endpoints.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        # ``navidrome_url`` is a ``pydantic.HttpUrl``; convert to ``str``
        # so we can manipulate it (e.g. strip trailing slash) without
        # attribute errors.
        self.base_url = str(settings.navidrome_url)
        # ``SecretStr`` stores the real value encrypted; ``get_secret_value``
        # returns the plaintext password.
        # Store authentication tuple (username, password). ``SecretStr``
        # provides ``get_secret_value`` to retrieve the plain password.
        # Store authentication details for Subsonic‑style query parameters.
        self._auth_user = settings.navidrome_user
        self._auth_pass = settings.navidrome_password.get_secret_value()
        self.timeout = settings.navidrome_timeout_seconds
        self.dwe_artist = settings.dwe_artist

    def _auth_params(self) -> dict:
        """Return query‑string authentication parameters for Subsonic API.

        ``c`` (client name) and ``v`` (protocol version) are required by the
        Subsonic compatibility layer. The values are static for this project.
        """
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
        """Perform a GET request to a Subsonic endpoint and parse the XML.

        Parameters
        ----------
        endpoint:
            Path relative to ``self.base_url`` (e.g. ``/rest/search``).
        params:
            Additional query parameters specific to the endpoint.
        """
        query_dict: dict = self._auth_params()
        if params:
            query_dict.update(params)
        query = urlencode(query_dict, safe="*", quote_via=quote)
        url = f"{self.base_url.rstrip('/')}{endpoint}?{query}"
        async with ClientSession() as session:
            async with session.get(
                url,
                timeout=ClientTimeout(total=self.timeout),
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
                try:
                    return ET.fromstring(text)
                except ET.ParseError as e:
                    raise ValueError(
                        f"Failed to parse XML from {url}: {e}"
                    ) from e

    async def _search_artist_id(self, name: str) -> str:
        """Search Navidrome for an artist name and return its ID.

        The Navidrome API does not accept an arbitrary name in the
        ``/artist/{id}/albums`` endpoint; it expects a numeric/UUID artist ID.
        We therefore perform a search request and take the first matching
        result's ``id`` field. If no result is found, a ``ValueError``
        is raised.
        """
        # Navidrome supports a generic search endpoint; we limit the search
        # to artist objects via the ``type`` query parameter.
        # Use Subsonic ``/rest/search`` endpoint. It returns XML.
        try:
            # ``/rest/search2`` is the preferred endpoint; ``/rest/search``
            # may be deprecated on newer Navidrome versions.
            root = await self._get_xml(
                "/rest/search2",
                {"query": name, "type": "artist"},
            )
        except ClientResponseError:
            # Fallback to the full artist list if search is unavailable.
            root = await self._get_xml("/rest/getArtists")

        # The XML response may include a namespace. Iterate over all elements
        # and match on the local tag name ``artist``.
        for artist_el in root.iter():
            if artist_el.tag.split('}')[-1] == "artist":
                if artist_el.attrib.get("name", "").lower() == name.lower():
                    return str(artist_el.attrib.get("id"))
        raise ValueError(f"Artist '{name}' not found via Navidrome")

    async def list_albums(self) -> dict:
        """Return a merged album list for all configured ``dwe_artist``.

        * For each configured artist name we first resolve the Navidrome
          artist ID via ``_search_artist_id``.
        * Using the obtained ID we fetch ``/api/v1/artist/{id}/albums``.
        * Albums are de‑duplicated across artists by their identifier.
        """
        merged: dict = {"albums": []}
        seen = set()
        for artist in self.dwe_artist:
            # Ensure artist entry is a string; otherwise skip with warning.
            if not isinstance(artist, str):
                # In production we would log; here we simply skip.
                continue
            # Resolve the artist's numeric ID first. If the artist cannot be
            # found, skip it rather than raising an exception that aborts the
            # whole list operation.
            try:
                artist_id = await self._search_artist_id(artist)
            except ValueError:
                # Artist not found – ignore this entry.
                continue
            # Use Subsonic ``/rest/getArtist``.
            # The response contains nested ``album`` elements.
            root = await self._get_xml(
                "/rest/getArtist",
                {"id": artist_id},
            )
            for album_el in root.iter():
                if album_el.tag.split('}')[-1] == "album":
                    album_id = album_el.attrib.get("id")
                    if album_id and album_id not in seen:
                        seen.add(album_id)
                        merged["albums"].append({
                            "id": album_id,
                            "title": album_el.attrib.get("title"),
                            "artist": album_el.attrib.get("artist"),
                        })
        return merged

    async def search_music(
        self,
        query: str,
        filters: dict | None = None,
    ) -> dict:
        """Query Navidrome for music matching a natural-language prompt."""
        params = {"query": query}
        if filters:
            params.update(filters)
        # Subsonic search – returns XML. Convert to a simple dict.
        root = await self._get_xml("/rest/search", params)
        results = []
        for el in root.iter("artist"):
            results.append({
                "id": el.attrib.get("id"),
                "name": el.attrib.get("name"),
            })
        return {"results": results}

    @staticmethod
    def _build_query_string(params: dict) -> str:
        """Build a URL-encoded query string for a search request."""
        return "&".join(
            f"{quote(str(key))}={quote(str(value))}"
            for key, value in params.items()
        )

    # NOTE: Local fallback is explicitly prohibited by project policy.
    # The method is retained only to satisfy the reference in older code paths.
    # It raises NotImplementedError to ensure accidental usage fails fast.
    def _list_local_albums(self) -> list:  # pragma: no cover
        """Local filesystem album discovery (disabled).

        The design mandates that Navidrome API must be the sole source
        of truth. If a fallback is ever required, it should be implemented
        as a separate recovery workflow, not within this client.
        """
        raise NotImplementedError(
            "Local album fallback is disabled by design."
        )
