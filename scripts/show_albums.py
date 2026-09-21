import asyncio
from backend.app.config import Settings
from backend.app.navidrome_client import NavidromeClient


async def main() -> None:
    # Settings reads .env (mounted via compose) for Navidrome connection
    settings = Settings()
    client = NavidromeClient(settings)

    # Fetch album list for configured artists
    result = await client.list_albums()
    albums = result.get("albums", [])

    if not albums:
        # Message kept under 79 characters per style guide
        print(
            "📭 No albums were returned. Check NAVIDROME_URL "
            "and DWE_ARTIST settings."
        )
        return

    print(f"🔎 Retrieved {len(albums)} albums. Showing up to 5 titles:")
    for i, album in enumerate(albums[:5]):
        if isinstance(album, dict):
            title = album.get("title") or album.get("name") or album.get("id")
        else:
            title = str(album)
        print(f"{i+1}. {title}")

if __name__ == "__main__":
    asyncio.run(main())
