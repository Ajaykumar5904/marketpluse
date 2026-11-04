"""Pure normalization + validation: raw scraped dict -> common schema."""
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}
CURRENCY_CODES = {"USD", "EUR", "GBP", "INR", "JPY"}
REQUIRED_FIELDS = ("title", "url")
_IN = ("in stock", "available", "instock", "in_stock", "add to cart", "ready to ship")
_OUT = ("out of stock", "sold out", "unavailable", "outofstock", "out_of_stock", "currently unavailable")


@dataclass(frozen=True)
class NormalizedListing:
    title: str
    url: str
    external_id: str | None
    price: Decimal | None
    currency: str | None
    availability: str
    brand: str | None
    seller: str | None
    location: str | None
    description: str | None
    rating: float | None
    review_count: int | None
    image_url: str | None
    dedupe_hash: str


def parse_price(raw: Any) -> tuple[Decimal | None, str | None]:
    """'₹1,299.00' -> (1299.00, 'INR'); '1.299,50 €' -> (1299.50, 'EUR')."""
    if raw is None or raw == "":
        return None, None
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw)), None
    text = str(raw)
    currency = next((c for s, c in CURRENCY_SYMBOLS.items() if s in text), None)
    if currency is None:
        m = re.search(r"\b([A-Z]{3})\b", text)
        currency = m.group(1) if m and m.group(1) in CURRENCY_CODES else None
    digits = re.sub(r"[^\d.,]", "", text)
    if not re.search(r"\d", digits):
        return None, currency
    if "." in digits and "," in digits:
        dec = "." if digits.rfind(".") > digits.rfind(",") else ","
        thou = "," if dec == "." else "."
        digits = digits.replace(thou, "").replace(dec, ".")
    elif "," in digits:
        tail = digits.rsplit(",", 1)[1]
        digits = digits.replace(",", ".") if len(tail) <= 2 and digits.count(",") == 1 else digits.replace(",", "")
    elif digits.count(".") > 1:
        digits = digits.replace(".", "")
    try:
        return Decimal(digits).quantize(Decimal("0.01")), currency
    except InvalidOperation:
        return None, currency


def normalize_availability(raw: Any) -> str:
    t = str(raw or "").strip().lower()
    if any(k in t for k in _OUT):  # check "out" first so "unavailable" is not read as "available"
        return "out_of_stock"
    if any(k in t for k in _IN):
        return "in_stock"
    return "unknown"


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", title.lower())).strip()


def canonical_url(url: str) -> str:
    p = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref"))]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/", urlencode(sorted(q)), ""))


def dedupe_hash(url: str, external_id: str | None, title: str) -> str:
    key = "|".join([canonical_url(url), (external_id or "").strip().lower(), normalize_title(title)])
    return hashlib.sha256(key.encode()).hexdigest()


def _int(v: Any) -> int | None:
    m = re.search(r"\d[\d,]*", str(v)) if v not in (None, "") else None
    return int(m.group().replace(",", "")) if m else None


def _float(v: Any) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", str(v)) if v not in (None, "") else None
    return float(m.group()) if m else None


def _clean(v: Any) -> str | None:
    s = re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""
    return s or None


def validate_raw(raw: dict[str, Any], required: tuple[str, ...] = REQUIRED_FIELDS) -> list[str]:
    """Returns the list of missing required fields (empty = valid)."""
    return [f for f in required if not _clean(raw.get(f))]


def normalize(raw: dict[str, Any], default_currency: str | None = None) -> NormalizedListing:
    missing = validate_raw(raw)
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    title, url = _clean(raw["title"]) or "", canonical_url(str(raw["url"]))
    price, cur = parse_price(raw.get("price") if raw.get("price") is not None else raw.get("salary"))
    explicit = _clean(raw.get("currency"))
    ext = _clean(raw.get("external_id"))
    desc = _clean(raw.get("description"))
    return NormalizedListing(
        title=title, url=url, external_id=ext, price=price,
        currency=(explicit.upper() if explicit else cur or default_currency),
        availability=normalize_availability(raw.get("availability")),
        brand=_clean(raw.get("brand")), seller=_clean(raw.get("seller") or raw.get("company") or raw.get("agent")),
        location=_clean(raw.get("location")), description=desc[:500] if desc else None,
        rating=_float(raw.get("rating")), review_count=_int(raw.get("review_count")),
        image_url=_clean(raw.get("image_url")), dedupe_hash=dedupe_hash(url, ext, title),
    )


def dedupe(items: list[NormalizedListing]) -> list[NormalizedListing]:
    """Keeps the first occurrence of each stable hash."""
    seen: dict[str, NormalizedListing] = {}
    for it in items:
        seen.setdefault(it.dedupe_hash, it)
    return list(seen.values())
