"""
Fetches the og:image from a story URL.
When you post a URL in a tweet, Twitter auto-generates a link card
with this image — so including the URL is usually enough. This module
surfaces the image URL explicitly so the operator can also attach it
as a standalone image if they prefer stronger visual impact.
"""

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 6.0
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ContentCopilot/1.0)"}

# Both attribute orderings Twitter / Open Graph parsers can produce
_OG_PATTERNS = [
    re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\'>\s]+)["\']', re.I),
    re.compile(r'<meta[^>]+content=["\'](https?://[^"\'>\s]+)["\'][^>]+property=["\']og:image["\']', re.I),
    re.compile(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\'](https?://[^"\'>\s]+)["\']', re.I),
    re.compile(r'<meta[^>]+content=["\'](https?://[^"\'>\s]+)["\'][^>]+name=["\']twitter:image["\']', re.I),
]


async def fetch_og_image(url: str) -> str | None:
    """
    Return the og:image (or twitter:image) URL for the given article URL.
    Returns None on any failure — callers should treat this as optional.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text[:50_000]  # only parse the head section

        for pattern in _OG_PATTERNS:
            match = pattern.search(html)
            if match:
                img_url = match.group(1).strip()
                logger.debug("og:image found for %s: %s", url[:60], img_url[:60])
                return img_url

    except Exception as e:
        logger.debug("Could not fetch og:image from %s: %s", url[:60], e)

    return None
