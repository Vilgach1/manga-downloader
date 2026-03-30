"""MangaDex scraper via official API (no scraping needed)."""

from __future__ import annotations

from ..base import BaseSite, Chapter, SeriesInfo, normalize_chapter_no, safe_filename

API = "https://api.mangadex.org"


class MangaDexSite(BaseSite):
    NAME = "MangaDex"
    DOMAINS = ["mangadex.org"]

    def _pick_title(self, titles: dict[str, str]) -> str:
        return titles.get('en') or next(iter(titles.values()), '???')

    def search(self, session, query: str) -> list[SeriesInfo]:
        data = session.get_json(f"{API}/manga", params={
            'title': query,
            'limit': 20,
            'contentRating[]': ['safe', 'suggestive', 'erotica'],
            'includes[]': ['cover_art'],
        })
        results = []
        for manga in data.get('data', []):
            attrs = manga.get('attributes', {})
            title = self._pick_title(attrs.get('title', {}))
            mid = manga.get('id', '')
            if not mid:
                continue
            results.append(SeriesInfo(
                id=mid,
                title=safe_filename(title, fallback='mangadex'),
                url=f"https://mangadex.org/title/{mid}",
                site=self.NAME,
            ))
        return results

    def get_series_info(self, session, url: str) -> SeriesInfo:
        manga_id = self._extract_id(url)
        data = session.get_json(f"{API}/manga/{manga_id}")
        attrs = data.get('data', {}).get('attributes', {})
        title = self._pick_title(attrs.get('title', {}))
        return SeriesInfo(id=manga_id, title=safe_filename(title, fallback=manga_id), url=url, site=self.NAME)

    def get_chapters(self, session, url: str, lang: str = "en") -> list[Chapter]:
        manga_id = self._extract_id(url)
        chapters: list[Chapter] = []
        seen_ids: set[str] = set()
        offset = 0
        limit = 100

        while True:
            data = session.get_json(f"{API}/manga/{manga_id}/feed", params={
                'translatedLanguage[]': [lang],
                'order[chapter]': 'asc',
                'limit': limit,
                'offset': offset,
            })
            items = data.get('data', [])
            for ch in items:
                ch_id = ch.get('id', '')
                if not ch_id or ch_id in seen_ids:
                    continue
                seen_ids.add(ch_id)
                attrs = ch.get('attributes', {})
                ch_num = attrs.get('chapter')
                no = normalize_chapter_no(ch_num)
                if no == 0 and not ch_num:
                    no = len(chapters) + 1
                title = attrs.get('title') or f"Chapter {ch_num or '?'}"
                chapters.append(Chapter(
                    no=no,
                    title=safe_filename(title, fallback=f"chapter_{len(chapters)+1}"),
                    url=f"https://mangadex.org/chapter/{ch_id}",
                    id=ch_id,
                ))

            total = data.get('total', 0)
            offset += limit
            if offset >= total or not items:
                break

        return chapters

    def get_page_urls(self, session, chapter: Chapter) -> list[str]:
        data = session.get_json(f"{API}/at-home/server/{chapter.id}")
        base_url = data['baseUrl']
        ch_hash = data['chapter']['hash']
        pages = data['chapter']['data']
        return [f"{base_url}/data/{ch_hash}/{page}" for page in pages]

    def get_referer(self, chapter: Chapter) -> str:
        return "https://mangadex.org/"

    def _extract_id(self, url: str) -> str:
        parts = url.rstrip('/').split('/')
        for i, part in enumerate(parts):
            if part in ('title', 'chapter') and i + 1 < len(parts):
                return parts[i + 1]
        raise ValueError(f"Can't extract MangaDex ID from: {url}")
