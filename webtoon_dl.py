#!/usr/bin/env python3
"""Interactive CLI for downloading manga and webtoon chapters."""

from __future__ import annotations

import os
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.base import chapter_sort_key, normalize_chapter_no, safe_filename
from src.downloader import download_series
from src.session import SmartSession
from src.sites import SITES, detect_site

console = Console()

STYLE = questionary.Style([
    ("qmark", "fg:cyan bold"),
    ("question", "fg:white bold"),
    ("answer", "fg:cyan"),
    ("pointer", "fg:cyan bold"),
    ("highlighted", "fg:cyan bold"),
    ("selected", "fg:green"),
    ("separator", "fg:#6C6C6C"),
    ("instruction", "fg:#6C6C6C"),
])

DOWNLOADS = Path("downloads")


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    clear()
    text = "Manga Downloader\nWebtoons | MangaDex | Manganato\nResume | Proxy | Parallel downloads"
    console.print(Panel.fit(text, border_style="cyan", title="Downloader"))


def ask_proxy():
    use = questionary.confirm("Use proxy?", default=False, style=STYLE).ask()
    if use:
        return questionary.text(
            "Proxy URL:",
            instruction="(http://ip:port)",
            style=STYLE,
        ).ask() or None
    return None


def ask_speed():
    return questionary.select(
        "Download speed:",
        choices=[
            questionary.Choice("Slow & safe (1 thread)", value=1),
            questionary.Choice("Normal (3 threads)", value=3),
            questionary.Choice("Fast (5 threads)", value=5),
            questionary.Choice("Turbo (8 threads)", value=8),
        ],
        default=3,
        style=STYLE,
    ).ask()


def ask_range(total: int):
    choice = questionary.select(
        "Which chapters?",
        choices=["All", "Custom range", "Last N chapters"],
        style=STYLE,
    ).ask()
    if choice is None:
        return None
    if choice == "All":
        return ("all", None, None)
    if choice == "Last N chapters":
        n = questionary.text(
            "How many last chapters?",
            default="10",
            validate=lambda v: v.isdigit() and int(v) > 0,
            style=STYLE,
        ).ask()
        if not n:
            return None
        return ("last", int(n), None)

    start_text = questionary.text(
        "Start chapter:",
        default="1",
        validate=lambda v: _is_chapter_input(v),
        style=STYLE,
    ).ask()
    end_text = questionary.text(
        "End chapter (empty = all):",
        default="",
        validate=lambda v: not v or _is_chapter_input(v),
        style=STYLE,
    ).ask()
    if start_text is None or end_text is None:
        return None
    start = normalize_chapter_no(start_text) if start_text else 1
    end = normalize_chapter_no(end_text) if end_text else None
    return ("range", start, end)


def _is_chapter_input(value: str) -> bool:
    try:
        normalized = str(value).strip().replace(",", ".")
        if not normalized:
            return False
        float(normalized)
        return True
    except ValueError:
        return False


def _series_output_dir(site, title: str) -> Path:
    return DOWNLOADS / site.NAME.lower() / safe_filename(title, fallback=site.NAME.lower())


def _apply_chapter_selection(chapters, selection):
    mode, first, second = selection
    ordered = sorted(chapters, key=chapter_sort_key)

    if mode == "all":
        return ordered

    if mode == "last":
        last_n = max(1, int(first or 1))
        return ordered[-last_n:]

    filtered = []
    start = float(first if first is not None else 1)
    end = float(second) if second is not None else None
    for chapter in ordered:
        ch_no = normalize_chapter_no(chapter.no)
        if isinstance(ch_no, (int, float)):
            numeric = float(ch_no)
            if numeric < start:
                continue
            if end is not None and numeric > end:
                continue
        filtered.append(chapter)
    return filtered


def _show_download_summary(title: str, output_dir: Path, success: int, failed: int):
    console.print()
    t = Table(show_header=False, border_style="cyan")
    t.add_column(style="bold")
    t.add_column()
    t.add_row("Series", title)
    t.add_row("Success", f"[green]{success}[/]")
    t.add_row("Failed", f"[red]{failed}[/]" if failed else "[green]0[/]")
    t.add_row("Saved to", str(output_dir.resolve()))
    if failed:
        t.add_row("Status", "[yellow]Run again to retry failed chapters[/]")
    console.print(t)


def download_series_flow(site, session, info, chapters):
    """Shared download flow for direct URLs and search results."""
    if not chapters:
        console.print("[bold red]No chapters found![/]")
        return

    ordered = sorted(chapters, key=chapter_sort_key)
    console.print(Panel(f"[bold]{info.title}[/]", subtitle=f"[dim]{site.NAME}[/]", border_style="green"))
    console.print(f"Found [bold]{len(ordered)}[/] chapters  (#{ordered[0].no} - #{ordered[-1].no})")

    selection = ask_range(len(ordered))
    if selection is None:
        return

    selected = _apply_chapter_selection(ordered, selection)
    if not selected:
        console.print("[red]No chapters in range![/]")
        return

    workers = ask_speed()
    if workers is None:
        return

    output_dir = _series_output_dir(site, info.title)
    output_dir.mkdir(parents=True, exist_ok=True)

    if selection[0] == "last":
        console.print(f"\n[bold]{len(selected)} chapters[/] (last {selection[1]}) -> [dim]{output_dir}[/]\n")
    else:
        console.print(f"\n[bold]{len(selected)} chapters[/] -> [dim]{output_dir}[/]\n")

    success, failed = download_series(session, site, selected, output_dir, workers=workers)
    _show_download_summary(info.title, output_dir, success, failed)


def action_download_url():
    """Download by pasting a URL."""
    url = questionary.text(
        "Paste manga/manhwa URL:",
        instruction="(webtoons.com, mangadex.org, manganato.gg)",
        style=STYLE,
    ).ask()
    if not url:
        return

    site = detect_site(url)
    if not site:
        console.print(f"[bold red]Unknown site![/] Supported: {', '.join(SITES.keys())}")
        return

    console.print(f"[dim]Detected:[/] [bold cyan]{site.NAME}[/]")
    proxy = ask_proxy()
    session = SmartSession(proxy=proxy)

    with console.status(f"[cyan]Fetching info from {site.NAME}..."):
        info = site.get_series_info(session, url)

    with console.status("[cyan]Loading chapters..."):
        chapters = site.get_chapters(session, url)

    download_series_flow(site, session, info, chapters)


def action_search():
    """Search across sites."""
    site_name = questionary.select(
        "Search on which site?",
        choices=[
            questionary.Choice("Webtoons", value="webtoons"),
            questionary.Choice("MangaDex", value="mangadex"),
            questionary.Choice("Manganato", value="manganato"),
        ],
        style=STYLE,
    ).ask()
    if not site_name:
        return

    query = questionary.text("Search:", style=STYLE).ask()
    if not query:
        return

    proxy = ask_proxy()
    site = SITES[site_name]()
    session = SmartSession(proxy=proxy)

    with console.status(f"[cyan]Searching {site.NAME}..."):
        results = site.search(session, query)

    if not results:
        console.print(f"[yellow]No results for '{query}'[/]")
        return

    t = Table(title=f"Search: {query} ({site.NAME})")
    t.add_column("#", style="dim", width=4)
    t.add_column("Title", min_width=30)
    t.add_column("URL", style="dim", max_width=60)
    for i, result in enumerate(results[:20], 1):
        t.add_row(str(i), result.title, result.url[:60])
    console.print(t)

    if questionary.confirm("Download one?", default=True, style=STYLE).ask():
        choices = [questionary.Choice(result.title[:60], value=result) for result in results[:20]]
        picked = questionary.select("Pick:", choices=choices, style=STYLE).ask()
        if picked:
            with console.status(f"[cyan]Loading chapters from {picked.title}..."):
                chapters = site.get_chapters(session, picked.url)
            download_series_flow(site, session, picked, chapters)


def action_info():
    """Show chapters list for a URL."""
    url = questionary.text("Paste URL:", style=STYLE).ask()
    if not url:
        return

    site = detect_site(url)
    if not site:
        console.print("[red]Unknown site![/]")
        return

    session = SmartSession()
    with console.status("[cyan]Loading..."):
        info = site.get_series_info(session, url)
        chapters = site.get_chapters(session, url)

    chapters = sorted(chapters, key=chapter_sort_key)
    t = Table(title=f"{info.title} ({len(chapters)} chapters)")
    t.add_column("#", style="dim", width=8)
    t.add_column("Title")
    for chapter in chapters:
        t.add_row(str(chapter.no), chapter.title)
    console.print(t)


def action_settings():
    """Show current settings / paths."""
    t = Table(title="Info", show_header=False)
    t.add_column(style="bold")
    t.add_column()
    t.add_row("Download folder", str(DOWNLOADS.resolve()))
    t.add_row("Supported sites", "Webtoons, MangaDex, Manganato")
    t.add_row("Output structure", "downloads/<site>/<series>/0001_Chapter_Name_<id>/")
    t.add_row("Resume state", ".webtoon_dl_state.json")
    console.print(t)


def main():
    while True:
        banner()

        action = questionary.select(
            "What do you want to do?",
            choices=[
                questionary.Choice("Download (paste URL)", value="download"),
                questionary.Choice("Search manga", value="search"),
                questionary.Choice("Show chapter list", value="info"),
                questionary.Choice("Settings / Info", value="settings"),
                questionary.Choice("Exit", value="exit"),
            ],
            style=STYLE,
        ).ask()

        if action is None or action == "exit":
            console.print("[dim]Bye![/]")
            break

        console.print()

        try:
            if action == "download":
                action_download_url()
            elif action == "search":
                action_search()
            elif action == "info":
                action_info()
            elif action == "settings":
                action_settings()
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/]")
        except Exception as exc:
            console.print(f"\n[bold red]Error:[/] {type(exc).__name__}: {exc}")

        console.print()
        questionary.press_any_key_to_continue(style=STYLE).ask()


if __name__ == "__main__":
    main()

