"""Controlled available RAM for stdio contract fixtures; real RSS and disk probes."""

from pathlib import Path

from web_search.resources import system_capacity


def contract_capacity(directory: Path) -> tuple[int, int, int]:
    _, rss, disk = system_capacity(directory)
    return 8_000_000_000, rss, disk
