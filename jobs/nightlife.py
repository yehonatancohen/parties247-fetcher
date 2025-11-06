"""Fetch Tel Aviv nightlife events from Go Out."""
from __future__ import annotations

import logging
from typing import List, Optional

from jobs.backend import PartiesAdminClient
from jobs.event_records import EventRecord, build_event_records
from jobs.go_out import GoOutFetcher

LOGGER = logging.getLogger(__name__)
CAROUSEL_NAME = "nightlife"


def run_job(
    referral: Optional[str] = None,
    *,
    admin_client: Optional[PartiesAdminClient] = None,
) -> List[EventRecord]:
    """Fetch nightlife events and upload them to the backend."""

    fetcher = GoOutFetcher(referral=referral)
    urls = fetcher.fetch_nightlife_events()
    records = build_event_records(CAROUSEL_NAME, urls)

    client = admin_client or PartiesAdminClient()
    client.import_carousel_urls(
        carousel_name=CAROUSEL_NAME,
        referral=referral,
        urls=urls,
    )
    LOGGER.info("Uploaded %d nightlife events", len(records))
    return records


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_job()
