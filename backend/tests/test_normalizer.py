from decimal import Decimal
import pytest
from app.services.normalizer import (canonical_url, dedupe, dedupe_hash, normalize, normalize_availability,
                                      parse_price, validate_raw)


@pytest.mark.parametrize("raw,expected", [
    ("₹1,299.00", (Decimal("1299.00"), "INR")),
    ("$1,299.50", (Decimal("1299.50"), "USD")),
    ("1.299,50 €", (Decimal("1299.50"), "EUR")),
    ("12,50", (Decimal("12.50"), None)),
    ("1,299", (Decimal("1299.00"), None)),
    ("GBP 45", (Decimal("45.00"), "GBP")),
    ("Call for price", (None, None)),
    (None, (None, None)),
    (19.99, (Decimal("19.99"), None)),
])
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Out of Stock", "out_of_stock"), ("Sold out", "out_of_stock"), ("Currently unavailable", "out_of_stock"),
    ("In Stock", "in_stock"), ("Add to cart", "in_stock"), ("", "unknown"), (None, "unknown"),
])
def test_availability(raw, expected):
    assert normalize_availability(raw) == expected


def test_canonical_url_strips_tracking_and_fragment():
    assert canonical_url("HTTPS://Shop.com/p/1/?utm_source=x&b=2&a=1#reviews") == "https://shop.com/p/1?a=1&b=2"


def test_dedupe_hash_stable_across_cosmetic_differences():
    h1 = dedupe_hash("https://s.com/p/1?utm_x=1", "A1", "Wireless  Earbuds, Pro!")
    h2 = dedupe_hash("https://s.com/p/1", "a1", "wireless earbuds pro")
    assert h1 == h2


def test_validate_and_normalize_errors():
    assert validate_raw({"title": " ", "url": "https://x.com"}) == ["title"]
    with pytest.raises(ValueError, match="title"):
        normalize({"url": "https://x.com"})


def test_normalize_full_record_and_job_fields():
    n = normalize({"title": "  Python Dev ", "url": "https://j.com/1", "salary": "₹18,00,000", "company": "Acme",
                   "rating": "4.5 out of 5", "review_count": "1,204 ratings"})
    assert n.title == "Python Dev" and n.seller == "Acme" and n.rating == 4.5 and n.review_count == 1204
    assert n.currency == "INR"


def test_dedupe_keeps_first():
    r = {"title": "A", "url": "https://x.com/1"}
    assert len(dedupe([normalize(r), normalize({**r, "price": "5"})])) == 1
