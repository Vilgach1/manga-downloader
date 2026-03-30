"""Webtoons.com scraper."""

import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup

from ..base import BaseSite, Chapter, SeriesInfo, normalize_chapter_no, safe_filename

AGE_COOKIES = {
    'needCCPA': 'false', 'needCOPPA': 'false', 'needGDPR': 'false',
    'pagGDPR': 'true', 'atGDPR': 'AD_CONSENT',
}


class WebtoonsSite(BaseSite):
    NAME = "Webtoons"
    DOMAINS = ["webtoons.com"]

    def search(self, session, query: str) -> list[SeriesInfo]:
        import requests

        url = f"https://www.webtoons.com/en/search?keyword={requests.utils.quote(query)}"
        resp = session.get(url, cookies=AGE_COOKIES)
        soup = BeautifulSoup(resp.text, 'html.parser')

        results = []
        seen = set()
        for a in soup.select('.card_lst .card_item a, .search_result a[href*="title_no="]'):
            href = a.get('href', '')
            if 'title_no=' not in href or href in seen:
                continue
            seen.add(href)
            title = a.get_text(strip=True)[:80] or "Untitled"
            full_url = href if href.startswith('http') else f"https://www.webtoons.com{href}"
            results.append(SeriesInfo(
                id=parse_qs(urlparse(full_url).query).get('title_no', [''])[0],
                title=title,
                url=full_url,
                site=self.NAME,
            ))
        return results

    def get_series_info(self, session, url: str) -> SeriesInfo:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        title_no = params.get('title_no', [None])[0]
        if not title_no:
            raise ValueError(f"No title_no in URL: {url}")

        resp = session.get(url, cookies=AGE_COOKIES)
        soup = BeautifulSoup(resp.text, 'html.parser')
        title_el = soup.select_one('meta[property="og:title"], meta[name="title"], h1._subj, h1')
        title = (
            title_el.get('content', '').strip()
            if title_el and title_el.get('content')
            else title_el.get_text(strip=True) if title_el else ""
        )
        if not title:
            path_parts = [p for p in parsed.path.split('/') if p]
            title = path_parts[-2] if len(path_parts) >= 3 else f"webtoon_{title_no}"
        return SeriesInfo(id=title_no, title=safe_filename(title, fallback=f"webtoon_{title_no}"), url=url, site=self.NAME)

    def get_chapters(self, session, url: str) -> list[Chapter]:
        info = self.get_series_info(session, url)
        base = url
        if '/list' not in base:
            base = base.rstrip('/') + '/list'
        parsed = urlparse(base)

        episodes = {}
        page = 1
        seen_pages = set()
        while True:
            params = {'title_no': info.id, 'page': page}
            list_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(params)}"
            if list_url in seen_pages:
                break
            seen_pages.add(list_url)

            resp = session.get(list_url, cookies=AGE_COOKIES)
            soup = BeautifulSoup(resp.text, 'html.parser')

            ep_links = soup.select('#_listUl a, ul#_listUl li a, .detail_lst a')
            if not ep_links:
                ep_links = soup.select('a[href*="episode_no="]')

            found_new = False
            for a_tag in ep_links:
                href = a_tag.get('href', '')
                if 'episode_no=' not in href:
                    continue
                ep_url = href if href.startswith('http') else urljoin(list_url, href)
                ep_no = normalize_chapter_no(parse_qs(urlparse(ep_url).query).get('episode_no', [0])[0])
                if isinstance(ep_no, (int, float)) and ep_no not in episodes:
                    title_span = a_tag.select_one('.subj span, .ellipsis')
                    ep_title = title_span.get_text(strip=True) if title_span else f"Episode {ep_no}"
                    episodes[ep_no] = Chapter(no=ep_no, title=ep_title, url=ep_url)
                    found_new = True

            if not found_new:
                break
            page += 1

        return sorted(episodes.values(), key=lambda e: float(e.no))

    def get_page_urls(self, session, chapter: Chapter) -> list[str]:
        resp = session.get(chapter.url, cookies=AGE_COOKIES)
        soup = BeautifulSoup(resp.text, 'html.parser')
        images = soup.select('#_imageList img, .viewer_img img, ._images img, img[data-url], img[src]')
        urls = []
        seen = set()
        for img in images:
            url = (img.get('data-url') or img.get('src') or '').strip()
            if not url:
                continue
            if url.startswith('//'):
                url = f"https:{url}"
            if not url.startswith('http'):
                url = urljoin(chapter.url, url)
            url = re.sub(r'\?type=q\d+', '', url)
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls
