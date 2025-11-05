"""Fetch Tel Aviv nightlife events from Go Out."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from jobs.event_records import EventRecord, build_event_records
from jobs.go_out import GoOutFetcher

LOGGER = logging.getLogger(__name__)
OUTPUT_FILE = Path("events_nightlife.json")


def run_job(
    referral: Optional[str] = None, output_file: Path = OUTPUT_FILE
) -> List[EventRecord]:
    """Fetch nightlife events and persist them to *output_file*.

    Parameters
    ----------
    referral:
        Optional affiliate identifier appended to generated URLs.
    output_file:
        File that will store the JSON representation of the fetched event records.
    """
    fetcher = GoOutFetcher(referral=referral)
    urls = fetcher.fetch_nightlife_events()
    records = build_event_records("nightlife", urls)
    _write_event_records(output_file, records)
    LOGGER.info("Saved %%d nightlife events to %%s", len(records), output_file)
    return records


def _write_event_records(path: Path, records: List[EventRecord]) -> None:
    payload = {
        "retrieved_at": datetime.now(tz=timezone.utc).isoformat(),
        "count": len(records),
        "events": records,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_job()
