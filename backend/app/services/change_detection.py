"""Pure diff between the previous snapshot set and the current run."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class EventType(StrEnum):
    NEW_LISTING = "new_listing"
    PRICE_DECREASE = "price_decrease"
    PRICE_INCREASE = "price_increase"
    OUT_OF_STOCK = "out_of_stock"
    BACK_IN_STOCK = "back_in_stock"
    LISTING_REMOVED = "listing_removed"
    TITLE_CHANGED = "title_changed"
    DESCRIPTION_CHANGED = "description_changed"


@dataclass(frozen=True)
class SnapshotView:
    dedupe_hash: str
    title: str
    description: str | None
    price: Decimal | None
    availability: str


@dataclass(frozen=True)
class Change:
    dedupe_hash: str
    event_type: EventType
    old_value: str | None = None
    new_value: str | None = None
    abs_change: Decimal | None = None
    pct_change: Decimal | None = None


def _pct(old: Decimal, new: Decimal) -> Decimal:
    return ((new - old) / old * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def detect_changes(
    previous: dict[str, SnapshotView], current: dict[str, SnapshotView], *, is_baseline: bool | None = None
) -> list[Change]:
    """Compare runs. The first run for a source is a baseline and emits no events,
    otherwise every listing would be flagged as 'new'. Call only after a SUCCESSFUL,
    non-empty run so a failed scrape never produces mass 'removed' events."""
    if is_baseline is None:
        is_baseline = not previous
    if is_baseline:
        return []
    out: list[Change] = []
    for h, cur in current.items():
        prev = previous.get(h)
        if prev is None:
            out.append(Change(h, EventType.NEW_LISTING, None, cur.title))
            continue
        if prev.price is not None and cur.price is not None and prev.price != cur.price:
            diff = cur.price - prev.price
            et = EventType.PRICE_DECREASE if diff < 0 else EventType.PRICE_INCREASE
            pct = _pct(prev.price, cur.price) if prev.price != 0 else None
            out.append(Change(h, et, str(prev.price), str(cur.price), diff, pct))
        if prev.availability != cur.availability:
            if cur.availability == "out_of_stock":
                out.append(Change(h, EventType.OUT_OF_STOCK, prev.availability, cur.availability))
            elif cur.availability == "in_stock" and prev.availability == "out_of_stock":
                out.append(Change(h, EventType.BACK_IN_STOCK, prev.availability, cur.availability))
        if prev.title != cur.title:
            out.append(Change(h, EventType.TITLE_CHANGED, prev.title, cur.title))
        if (prev.description or "") != (cur.description or ""):
            out.append(Change(h, EventType.DESCRIPTION_CHANGED, prev.description, cur.description))
    for h, prev in previous.items():
        if h not in current:
            out.append(Change(h, EventType.LISTING_REMOVED, prev.title, None))
    return out
