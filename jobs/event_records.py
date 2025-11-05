"""Shared helpers for representing fetched event URLs."""
from __future__ import annotations

from typing import Iterable, List, Sequence, TypedDict


class EventRecord(TypedDict):
    """Structure describing a fetched event URL."""

    title: str
    url: str


def build_event_records(title: str, urls: Sequence[str]) -> List[EventRecord]:
    """Return ``EventRecord`` objects for *urls* with the provided *title*."""

    return [{"title": title, "url": url} for url in urls]


def merge_event_records(collections: Iterable[Sequence[EventRecord]]) -> List[EventRecord]:
    """Flatten an iterable of event record collections into a single list."""

    merged: List[EventRecord] = []
    for records in collections:
        merged.extend(records)
    return merged

