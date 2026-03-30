"""Base class and shared helpers for manga/manhwa site scrapers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import re
import unicodedata


@dataclass
class SeriesInfo:
    id: str
    title: str
    url: str
    site: str


@dataclass
class Chapter:
    no: int | float
    title: str
    url: str
    id: str = ""


def normalize_chapter_no(value: int | float | str | None) -> int | float | str:
    """Normalize a chapter number for sorting and state keys."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)

    text = str(value).strip()
    if not text:
        return 0

    text = text.replace(",", ".")
    if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        number = float(text)
        return int(number) if number.is_integer() else number
    return text


def chapter_token(value: int | float | str | None) -> str:
    """Create a stable token for filenames and resume state."""
    normalized = normalize_chapter_no(value)
    if isinstance(normalized, int):
        return f"{normalized:04d}"
    if isinstance(normalized, float):
        whole = int(abs(normalized))
        fractional = f"{normalized:.6f}".rstrip("0").rstrip(".")
        if "." in fractional:
            whole_text, _, frac = fractional.partition(".")
            return f"{int(whole_text):04d}.{frac}"
        return f"{whole:04d}"
    return safe_filename(str(normalized), fallback="chapter")


def chapter_sort_key(chapter: Chapter) -> tuple[int, float | str, str]:
    """Sort chapters by numeric value first and by title as a fallback."""
    normalized = normalize_chapter_no(chapter.no)
    if isinstance(normalized, (int, float)):
        return (0, float(normalized), chapter.title.casefold())
    return (1, str(normalized).casefold(), chapter.title.casefold())


def safe_filename(text: str, fallback: str = "item", max_length: int = 120) -> str:
    """Convert arbitrary text to a filesystem-friendly name."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.strip().replace("/", "_").replace("\\", "_")
    normalized = re.sub(r'[<>:"|?*\x00-\x1f]', "_", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ._")
    normalized = re.sub(r"_+", "_", normalized)
    if not normalized:
        normalized = fallback
    return normalized[:max_length]


def _stable_id_token(value: str, max_length: int = 12) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "", value or "")
    if not token:
        return ""
    return token[-max_length:]


def chapter_folder_name(chapter: Chapter) -> str:
    """Create the on-disk folder name for a chapter."""
    parts = [chapter_token(chapter.no), safe_filename(chapter.title, fallback="chapter", max_length=80)]
    if chapter.id:
        suffix = _stable_id_token(chapter.id)
        if suffix:
            parts.append(suffix)
    return "_".join(parts)


class BaseSite(ABC):
    NAME: str = ""
    DOMAINS: list[str] = []

    @abstractmethod
    def search(self, session, query: str) -> list[SeriesInfo]:
        ...

    @abstractmethod
    def get_series_info(self, session, url: str) -> SeriesInfo:
        ...

    @abstractmethod
    def get_chapters(self, session, url: str) -> list[Chapter]:
        ...

    @abstractmethod
    def get_page_urls(self, session, chapter: Chapter) -> list[str]:
        ...

    def get_referer(self, chapter: Chapter) -> str:
        return chapter.url
