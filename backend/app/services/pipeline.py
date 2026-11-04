"""Fetch, normalize, persist, and diff a source as one durable scraping run."""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import ListingHistory, ListingSnapshot, PriceChange, RawRecord, ScrapingRun, Source
from app.scrapers.fetch import fetch_records
from app.services.change_detection import SnapshotView, detect_changes
from app.services.normalizer import NormalizedListing, normalize, validate_raw


def create_run(db: Session, source: Source) -> ScrapingRun:
    run = ScrapingRun(source_id=source.id, status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def execute_run(run_id: int) -> None:
    """Background task entry point. Errors are persisted on the run instead of lost."""
    with SessionLocal() as db:
        run = db.get(ScrapingRun, run_id)
        if run is None:
            return
        source = db.get(Source, run.source_id)
        if source is None or not source.enabled:
            run.status, run.error = "failed", "Source was deleted or disabled before execution"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            return
        run.status = "running"
        db.commit()
        try:
            settings = get_settings()
            time.sleep(random.uniform(settings.scraper_min_delay, settings.scraper_max_delay))
            raw_records, html = fetch_records(source, settings.scraper_user_agent)
            run.pages_fetched = 1
            valid: list[tuple[NormalizedListing, dict]] = []
            missing_counts: dict[str, int] = {}
            for raw in raw_records:
                missing = validate_raw(raw, tuple(source.expected_fields) or ("title", "url"))
                if missing:
                    run.validation_failures += 1
                    for field in missing:
                        missing_counts[field] = missing_counts.get(field, 0) + 1
                    continue
                try:
                    valid.append((normalize(raw), raw))
                except (ValueError, TypeError, ArithmeticError):
                    run.validation_failures += 1
            run.missing_fields = missing_counts
            if not valid:
                raise ValueError("No valid listings were extracted; empty runs do not mark existing listings as removed")

            unique: dict[str, tuple[NormalizedListing, dict]] = {}
            for listing, raw in valid:
                unique.setdefault(listing.dedupe_hash, (listing, raw))
            now = datetime.now(timezone.utc)
            all_snapshots = list(db.scalars(select(ListingSnapshot).where(ListingSnapshot.source_id == source.id)))
            previous_rows = [row for row in all_snapshots if row.removed_at is None]
            previous = {row.dedupe_hash: SnapshotView(row.dedupe_hash, row.title, row.description, row.price, row.availability) for row in previous_rows}
            current = {key: SnapshotView(key, listing.title, listing.description, listing.price, listing.availability)
                       for key, (listing, _) in unique.items()}
            changes = detect_changes(previous, current)
            snapshots = {row.dedupe_hash: row for row in all_snapshots}
            for index, (key, (listing, raw)) in enumerate(unique.items()):
                snapshot = snapshots.get(key)
                if snapshot is None:
                    snapshot = ListingSnapshot(source_id=source.id, dedupe_hash=key, first_seen_at=now)
                    db.add(snapshot)
                    snapshots[key] = snapshot
                _apply_listing(snapshot, listing)
                snapshot.last_seen_at, snapshot.removed_at = now, None
                db.flush()
                db.add(ListingHistory(snapshot_id=snapshot.id, run_id=run.id, price=listing.price,
                                     availability=listing.availability, observed_at=now))
                if source.store_raw_html:
                    db.add(RawRecord(run_id=run.id, payload=raw, html_snapshot=html if index == 0 else None))

            for row in previous_rows:
                if row.dedupe_hash not in unique:
                    row.removed_at = now
            for change in changes:
                snapshot = snapshots.get(change.dedupe_hash)
                if snapshot is None:
                    continue
                db.add(PriceChange(snapshot_id=snapshot.id, run_id=run.id, event_type=change.event_type.value,
                                   old_value=change.old_value, new_value=change.new_value,
                                   abs_change=change.abs_change, pct_change=change.pct_change, detected_at=now))

            source.last_success_at = now
            run.items_extracted = len(unique)
            run.status, run.finished_at = "success", now
            db.commit()
        except Exception as exc:
            db.rollback()
            run = db.get(ScrapingRun, run_id)
            if run:
                run.status, run.finished_at = "failed", datetime.now(timezone.utc)
                run.error = str(exc)[:4000]
                db.commit()


def _apply_listing(snapshot: ListingSnapshot, listing: NormalizedListing) -> None:
    snapshot.title = listing.title
    snapshot.url = listing.url
    snapshot.brand = listing.brand
    snapshot.seller = listing.seller
    snapshot.location = listing.location
    snapshot.description = listing.description
    snapshot.price = listing.price
    snapshot.currency = listing.currency
    snapshot.availability = listing.availability
    snapshot.rating = listing.rating
    snapshot.review_count = listing.review_count
    snapshot.image_url = listing.image_url
