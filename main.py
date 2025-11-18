"""Entry point for fetching daily event data."""
from __future__ import annotations

import argparse
import logging
from typing import List, Optional

from jobs import my_events, nightlife, weekend
from jobs.event_records import EventRecord, merge_event_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--referral",
        help="Affiliate code appended to public Go Out event URLs",
        default=None,
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser.parse_args()


def run(referral: Optional[str] = None) -> List[EventRecord]:
    """Run all fetch jobs and return merged event records."""

    collections = [
        my_events.run_job(),
    ]
    return merge_event_records(collections)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    try:
        run(referral=args.referral)
    except Exception as exc:  # pragma: no cover - to ensure non-zero exit on failure
        logging.getLogger(__name__).exception("Fetcher failed: %%s", exc)
        raise
