"""Manganato/Chapmanganato scraper."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..base import BaseSite, Chapter, SeriesInfo, normalize_chapter_no, safe_filename


class ManganatoSite(BaseSite):
    NAME = "Manganato"
    DOMAINS = ["manganato", "chapmanganato", "readmanganato", "natomanga", "nelomanga"]
    BASE = "https://manganato.gg"

    def search(self, session, query: str) -> list[SeriesInfo]:
        search_query = query.strip().replace(' ', '_')
        url = f"{self.BASE}/search/story/{search_query}"
        resp = session.get(url)
        soup = BeautifulSoup(resp.text, 'html.parser')

        results = []
        seen = set()
        for item in soup.select('.search-story-item, .content-genres-item'):
            a = item.select_one('a.item-title, a.genres-item-name, h3 a')
            if not a:
                continue
            href = a.get('href', '')
            title = a.get_text(strip=True)
            if not href:
                continue
            full_url = href if href.startswith('http') else urljoin(self.BASE, href)
            key = full_url.rstrip('/')
            if key in seen:
                continue
            seen.add(key)
            manga_id = urlparse(full_url).path.rstrip('/').split('/')[-1]
            results.append(SeriesInfo(
                id=manga_id,
                title=safe_filename(title, fallback=manga_id),
                url=full_url,
                site=self.NAME,
            ))
        return results

    def get_series_info(self, session, url: str) -> SeriesInfo:
        resp = session.get(url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        title_el = soup.select_one('meta[property="og:title"], h1, .story-info-right h1, .panel-story-info .story-info-right h1')
        title = (
            title_el.get('content', '').strip()
            if title_el and title_el.get('content')
            else title_el.get_text(strip=True) if title_el else url.split('/')[-1]
        )
        manga_id = url.rstrip('/').split('/')[-1]
        return SeriesInfo(id=manga_id, title=safe_filename(title, fallback=manga_id), url=url, site=self.NAME)

    def get_chapters(self, session, url: str) -> list[Chapter]:
        resp = session.get(url)
        soup = BeautifulSoup(resp.text, 'html.parser')

        chapters: list[Chapter] = []
        seen_urls = set()
        ch_list = soup.select(
            '.panel-story-chapter-list .row-content-chapter li a, '
            '.chapter-list .row li a, '
            'ul.row-content-chapter li a'
        )
        if not ch_list:
            ch_list = soup.select('a[href*="chapter"]')

        for a in ch_list:
            href = a.get('href', '')
            if not href:
                continue
            full_url = href if href.startswith('http') else urljoin(url, href)
            full_url = full_url.split('#', 1)[0]
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            title = a.get_text(strip=True)
            no = self._extract_chapter_no(full_url, title)
            chapters.append(Chapter(no=no, title=safe_filename(title, fallback='chapter'), url=full_url))

        chapters.sort(key=lambda ch: float(normalize_chapter_no(ch.no)))
        return chapters

    def get_page_urls(self, session, chapter: Chapter) -> list[str]:
        resp = session.get(chapter.url)
        soup = BeautifulSoup(resp.text, 'html.parser')

        images = soup.select('.container-chapter-reader img')
        if not images:
            images = soup.select('.reading-detail .page-chapter img, #vungdoc img')

        urls = []
        seen = set()
        for img in images:
            src = img.get('src') or img.get('data-src') or ''
            src = src.strip()
            if not src:
                continue
            if src.startswith('//'):
                src = f"https:{src}"
            if not src.startswith('http'):
                src = urljoin(chapter.url, src)
            if src not in seen:
                seen.add(src)
                urls.append(src)
        return urls

    def get_referer(self, chapter: Chapter) -> str:
        return self.BASE + "/"

    def _extract_chapter_no(self, url: str, title: str):
        m = re.search(r'chapter[_-](\d+(?:\.\d+)?)', url, re.IGNORECASE)
        if m:
            return normalize_chapter_no(m.group(1))
        m = re.search(r'chapter\s*(\d+(?:\.\d+)?)', title, re.IGNORECASE)
        if m:
            return normalize_chapter_no(m.group(1))
        return 0
