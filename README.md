# Manga Downloader

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Interface-Interactive_CLI-111111?style=for-the-badge&logo=gnubash&logoColor=white" alt="Interactive CLI">
  <img src="https://img.shields.io/badge/Downloads-Resumable-1F8B4C?style=for-the-badge" alt="Resumable Downloads">
  <img src="https://img.shields.io/badge/Pages-Parallel-0F766E?style=for-the-badge" alt="Parallel Downloads">
</p>

<p align="center">
  A versatile command-line tool for downloading manga, manhwa, and webtoon chapters from supported sources for offline reading.
</p>

## Overview

Manga Downloader is a terminal-first utility for:

- downloading directly from a series URL
- searching titles from the CLI
- selecting all chapters, a custom range, or the latest N chapters
- resuming interrupted downloads without re-fetching completed chapters
- saving everything into clean, filesystem-safe folders

## Supported Sites

| Site | Domain | Notes |
| --- | --- | --- |
| Webtoons | `webtoons.com` | Webtoon-style chapter downloads |
| MangaDex | `mangadex.org` | Uses MangaDex API |
| Manganato | `manganato.gg` | Also works with common mirrors such as `chapmanganato.com` |

## Feature Highlights

| Feature | Description |
| --- | --- |
| Interactive CLI | Question-based interface for all main actions |
| Multiple Modes | Download from a series URL or search and select a title |
| Chapter Selection | Download all chapters, a custom range, or the latest N chapters |
| Resumable Downloads | Tracks completed and failed chapters in a per-series state file |
| Parallel Downloads | Configurable speed presets from 1 to 8 threads |
| Robust Session Handling | Retries, throttling, rotating user agents, and optional proxy support |
| Organized Output | Filesystem-safe folder names for series and chapters |

## Requirements

- Python `3.10` or newer

## Installation

Clone the repository:

```bash
git clone https://github.com/Vilgach1/manga-downloader.git
cd manga-downloader
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Start the interactive downloader:

```bash
python webtoon_dl.py
```

You will be prompted to choose an action such as:

- download from a series URL
- search for a title
- inspect available chapters
- review local settings and output paths

## Optional CLI Installation

If you want a reusable system-wide command:

```bash
pip install .
```

Then run:

```bash
manga-downloader
```

## Output Structure

Downloads are saved inside the `downloads/` directory:

```text
downloads/
  <site_name>/
    <series_title>/
      0001_Chapter_Title_<id>/
        001.jpg
        002.jpg
      .webtoon_dl_state.json
```

The `.webtoon_dl_state.json` file stores completed and failed chapters so the downloader can resume cleanly after interruptions.

## Why It Feels Nice To Use

- fast setup with a single script entry point
- clear prompts instead of long command flags
- sensible output layout for offline reading
- safer retries and resume support for unstable connections

## Project Layout

```text
webtoon_dl.py        CLI entry point
src/base.py          Shared models and naming helpers
src/session.py       HTTP session, throttling, retry logic
src/downloader.py    Core download engine
src/sites/           Site-specific adapters
```

## Quick Start

```bash
pip install -r requirements.txt
python webtoon_dl.py
```

<p align="center">
  <sub>Built for straightforward offline chapter downloads from supported sources.</sub>
</p>