"""Core download engine."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn

from .base import BaseSite, Chapter, chapter_folder_name, chapter_sort_key

console = Console()
STATE_FILE = ".webtoon_dl_state.json"
LEGACY_STATE_FILES = (".dl_state.json",)
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def _state_path(output_dir: Path) -> Path:
    current = output_dir / STATE_FILE
    if current.exists():
        return current
    for legacy_name in LEGACY_STATE_FILES:
        legacy = output_dir / legacy_name
        if legacy.exists():
            return legacy
    return current


def _chapter_key(chapter: Chapter) -> str:
    """Create a stable resume key for a chapter."""
    return chapter.id or chapter.url or f"{chapter.no}:{chapter.title}"


def _normalize_state_list(values) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def load_state(output_dir: Path) -> dict:
    path = _state_path(output_dir)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"completed": [], "failed": []}

        completed = raw.get("completed", raw.get("completed_urls", []))
        failed = raw.get("failed", raw.get("failed_urls", []))
        return {
            "completed": _normalize_state_list(completed),
            "failed": _normalize_state_list(failed),
        }
    return {"completed": [], "failed": []}


def save_state(output_dir: Path, state: dict):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / STATE_FILE
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "completed": _normalize_state_list(state.get("completed", [])),
        "failed": _normalize_state_list(state.get("failed", [])),
    }
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _guess_extension(img_url: str) -> str:
    url = img_url.lower().split("?", 1)[0].split("#", 1)[0]
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if url.endswith(ext):
            return ext
    return ".jpg"


def _chapter_pages(chapter_dir: Path) -> list[Path]:
    pages: list[Path] = []
    for ext in IMAGE_EXTENSIONS:
        pages.extend(chapter_dir.glob(f"*{ext}"))
    return sorted(pages)


def download_chapter(session, site: BaseSite, chapter: Chapter, output_dir: Path, workers=3) -> tuple[bool, int]:
    """Download all pages of a chapter. Returns (success, page_count)."""
    ch_dir = output_dir / chapter_folder_name(chapter)
    ch_dir.mkdir(parents=True, exist_ok=True)

    page_urls = site.get_page_urls(session, chapter)
    if not page_urls:
        return False, 0

    referer = site.get_referer(chapter)
    expected_files = [ch_dir / f"{i:03d}{_guess_extension(img_url)}" for i, img_url in enumerate(page_urls, 1)]

    if expected_files and all(path.exists() and path.stat().st_size > 0 for path in expected_files):
        return True, len(expected_files)

    def _download(item):
        index, img_url = item
        target = expected_files[index - 1]
        if target.exists() and target.stat().st_size > 0:
            return True

        tmp = target.with_suffix(target.suffix + ".part")
        data = session.get_image(img_url, referer=referer)
        if not data:
            return False

        tmp.write_bytes(data)
        tmp.replace(target)
        return True

    ok = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_download, (i, url)): i for i, url in enumerate(page_urls, 1)}
        for future in as_completed(futures):
            if future.result():
                ok += 1

    return ok == len(expected_files), ok


def download_series(session, site: BaseSite, chapters: list[Chapter], output_dir: Path, workers=3):
    """Download multiple chapters with progress bar and resume."""
    output_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(output_dir)
    completed = set(state["completed"])
    failed = set(state["failed"])

    ordered_chapters = sorted(chapters, key=chapter_sort_key)
    remaining = [ch for ch in ordered_chapters if _chapter_key(ch) not in completed]

    if len(remaining) < len(ordered_chapters):
        console.print(f"[yellow]Resuming: {len(ordered_chapters) - len(remaining)} done, {len(remaining)} left[/]")

    if not remaining:
        console.print("[bold green]All chapters already downloaded![/]")
        return 0, 0

    success, failed_count = 0, 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading", total=len(remaining))
        for chapter in remaining:
            desc = f"Ch {chapter.no}: {chapter.title[:35]}"
            progress.update(task, description=desc)
            key = _chapter_key(chapter)

            try:
                ok, count = download_chapter(session, site, chapter, output_dir, workers=workers)
                if ok:
                    success += 1
                    completed.add(key)
                    failed.discard(key)
                    progress.console.print(f"  [green]Ch {chapter.no}[/] {count} pages")
                else:
                    failed_count += 1
                    failed.add(key)
                    progress.console.print(f"  [red]Ch {chapter.no}[/] incomplete or no pages")
            except Exception as exc:
                failed_count += 1
                failed.add(key)
                progress.console.print(f"  [red]Ch {chapter.no}[/] error: {exc}")

            save_state(output_dir, {"completed": sorted(completed), "failed": sorted(failed)})
            progress.advance(task)

    return success, failed_count

