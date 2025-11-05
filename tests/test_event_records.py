from __future__ import annotations

from jobs.event_records import EventRecord, build_event_records, merge_event_records


def test_build_event_records_adds_title() -> None:
    records = build_event_records("nightlife", ["https://example.com/a", "b"])
    assert records == [
        {"title": "nightlife", "url": "https://example.com/a"},
        {"title": "nightlife", "url": "b"},
    ]


def test_merge_event_records_flattens_lists() -> None:
    collections: list[list[EventRecord]] = [
        build_event_records("nightlife", ["a"]),
        build_event_records("weekend", ["b", "c"]),
    ]
    merged = merge_event_records(collections)
    assert merged == [
        {"title": "nightlife", "url": "a"},
        {"title": "weekend", "url": "b"},
        {"title": "weekend", "url": "c"},
    ]
