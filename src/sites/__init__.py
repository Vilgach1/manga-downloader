from urllib.parse import urlparse

from .webtoons import WebtoonsSite
from .mangadex import MangaDexSite
from .manganato import ManganatoSite

SITES = {
    'webtoons': WebtoonsSite,
    'mangadex': MangaDexSite,
    'manganato': ManganatoSite,
}


def detect_site(url: str):
    """Auto-detect site from URL."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    url_lower = url.lower()
    for cls in SITES.values():
        for domain in cls.DOMAINS:
            domain = domain.lower()
            if host == domain or host.endswith(f'.{domain}') or domain in url_lower:
                return cls()
    return None


def get_site_names() -> list[str]:
    return list(SITES.keys())
