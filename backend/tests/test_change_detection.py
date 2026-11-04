from decimal import Decimal
from app.services.change_detection import EventType, SnapshotView, detect_changes


def sv(h, price="100", avail="in_stock", title="T", desc=None):
    return SnapshotView(h, title, desc, Decimal(price) if price is not None else None, avail)


def types(changes):
    return [c.event_type for c in changes]


def test_baseline_run_emits_nothing():
    assert detect_changes({}, {"a": sv("a")}) == []


def test_price_drop_values():
    [c] = detect_changes({"a": sv("a", "200")}, {"a": sv("a", "150")})
    assert c.event_type == EventType.PRICE_DECREASE
    assert c.abs_change == Decimal("-50") and c.pct_change == Decimal("-25.00")


def test_price_increase():
    [c] = detect_changes({"a": sv("a", "100")}, {"a": sv("a", "110")})
    assert c.event_type == EventType.PRICE_INCREASE and c.pct_change == Decimal("10.00")


def test_new_and_removed():
    ch = detect_changes({"a": sv("a"), "b": sv("b")}, {"a": sv("a"), "c": sv("c")})
    assert sorted(types(ch)) == [EventType.LISTING_REMOVED, EventType.NEW_LISTING]


def test_stock_transitions():
    assert types(detect_changes({"a": sv("a")}, {"a": sv("a", avail="out_of_stock")})) == [EventType.OUT_OF_STOCK]
    assert types(detect_changes({"a": sv("a", avail="out_of_stock")}, {"a": sv("a")})) == [EventType.BACK_IN_STOCK]


def test_unknown_to_in_stock_is_not_back_in_stock():
    assert detect_changes({"a": sv("a", avail="unknown")}, {"a": sv("a")}) == []


def test_title_and_description_changes():
    ch = detect_changes({"a": sv("a", title="Old", desc="x")}, {"a": sv("a", title="New", desc="y")})
    assert set(types(ch)) == {EventType.TITLE_CHANGED, EventType.DESCRIPTION_CHANGED}


def test_missing_price_is_safe_and_no_change_is_silent():
    assert detect_changes({"a": sv("a", None)}, {"a": sv("a", "10")}) == []
    assert detect_changes({"a": sv("a")}, {"a": sv("a")}) == []
