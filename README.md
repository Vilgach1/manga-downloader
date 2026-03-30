# Manga Downloader

Terminal downloader for manga, manhwa, and webtoon chapters from:

- Webtoons
- MangaDex
- Manganato

## Features

- Download by direct series URL
- Search and pick a title from the terminal
- Resume interrupted downloads from a per-series state file
- Parallel page downloads with request throttling and retries
- Safe filesystem names for series and chapter folders
- Optional proxy support

## Requirements

- Python 3.10 or newer

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the interactive CLI:

```bash
python webtoon_dl.py
```

If you prefer an installed entry point:

```bash
pip install .
manga-downloader
```

## Output Structure

```text
downloads/
  <site>/
    <series>/
      0001_Chapter_Title_<id>/
        001.jpg
        002.jpg
      .webtoon_dl_state.json
```

## Project Layout

```text
webtoon_dl.py        CLI entry point
src/base.py          shared models and helpers
src/session.py       HTTP session and retry logic
src/downloader.py    download engine
src/sites/           site-specific adapters
```