"""Small configurable fetchers for static HTML, rendered HTML, and JSON APIs."""
from __future__ import annotations

import ipaddress
import json
import socket
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_ITEMS = 5000
MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 20


def _check_target(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Source URL must be an HTTP(S) URL without embedded credentials")
    try:
        addresses = {ipaddress.ip_address(row[4][0]) for row in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))}
    except OSError as exc:
        raise ValueError(f"Could not resolve source host: {exc}") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Source host must resolve only to public IP addresses")


def _get(url: str, headers: dict[str, str]) -> tuple[requests.Response, str]:
    current = url
    session = requests.Session()
    session.trust_env = False
    try:
        for _ in range(MAX_REDIRECTS + 1):
            _check_target(current)
            response = session.get(current, headers=headers, timeout=TIMEOUT_SECONDS, allow_redirects=False, stream=True)
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise ValueError("Redirect response had no Location header")
                current = urljoin(current, location)
                continue
            body = bytearray()
            for chunk in response.iter_content(64 * 1024):
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    response.close()
                    raise ValueError(f"Source response exceeds {MAX_RESPONSE_BYTES} bytes")
            response._content = bytes(body)
            response._content_consumed = True
            response.raise_for_status()
            return response, current
        raise ValueError("Source exceeded the redirect limit")
    finally:
        session.close()


def _value(root, spec):
    if isinstance(spec, dict):
        selector, attr = spec.get("selector", ""), spec.get("attr", "text")
    else:
        selector, attr = spec, "text"
    node = root.select_one(selector) if selector else root
    if node is None:
        return None
    if attr == "text":
        return node.get_text(" ", strip=True)
    return node.get(attr)


def _html_items(html: str, base_url: str, selectors: dict) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    item_selector = selectors.get("item")
    rows = soup.select(item_selector) if item_selector else [soup]
    fields = {k: v for k, v in selectors.items() if k not in {"item", "items_path"}}
    if not fields:
        raise ValueError("HTML source selectors must map fields such as title and url")
    output = []
    for row in rows:
        record = {field: _value(row, selector) for field, selector in fields.items()}
        if record.get("url"):
            record["url"] = urljoin(base_url, str(record["url"]))
        if record.get("image_url"):
            record["image_url"] = urljoin(base_url, str(record["image_url"]))
        output.append(record)
    return output


def _path(value, path: str):
    for part in path.split(".") if path else ():
        if isinstance(value, list) and part.isdigit():
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _api_items(payload, selectors: dict, base_url: str) -> list[dict]:
    collection = _path(payload, selectors.get("items_path", ""))
    if collection is None:
        collection = payload
    if isinstance(collection, dict):
        collection = [collection]
    if not isinstance(collection, list):
        raise ValueError("API response did not contain a JSON object or list")
    fields = {k: v for k, v in selectors.items() if k != "items_path"}
    if not fields:
        rows = [x for x in collection if isinstance(x, dict)]
    else:
        rows = [{field: _path(row, path) if isinstance(path, str) else None for field, path in fields.items()} for row in collection]
    for row in rows:
        for field in ("url", "image_url"):
            if row.get(field):
                row[field] = urljoin(base_url, str(row[field]))
    return rows


def _check_robots(url: str, user_agent: str) -> None:
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        response, final_url = _get(robots_url, {"User-Agent": user_agent})
        parser = RobotFileParser(final_url)
        parser.parse(response.text.splitlines())
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in {404, 410}:
            return
        raise
    if not parser.can_fetch(user_agent, url):
        raise PermissionError("robots.txt disallows this source URL")


def fetch_records(source, user_agent: str) -> tuple[list[dict], str | None]:
    headers = {"User-Agent": user_agent, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"}
    _check_robots(source.url, user_agent)
    if source.scraper_type == "javascript":
        from playwright.sync_api import sync_playwright

        _check_target(source.url)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=user_agent)
            page.route("**/*", lambda route: route.continue_() if _safe_route(route.request.url) else route.abort())
            try:
                page.goto(source.url, wait_until="domcontentloaded", timeout=TIMEOUT_SECONDS * 1000)
                page.wait_for_timeout(750)
                html, final_url = page.content(), page.url
            finally:
                browser.close()
        records = _html_items(html, final_url, source.selectors or {})
        if len(records) > MAX_ITEMS:
            raise ValueError(f"Source produced more than {MAX_ITEMS} items")
        return records, html

    response, final_url = _get(source.url, headers)
    body = response.text
    if source.scraper_type == "api":
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("API source did not return valid JSON") from exc
        records = _api_items(payload, source.selectors or {}, final_url)
        if len(records) > MAX_ITEMS:
            raise ValueError(f"Source produced more than {MAX_ITEMS} items")
        return records, None
    if source.scraper_type != "static":
        raise ValueError(f"Unsupported scraper type: {source.scraper_type}")
    records = _html_items(body, final_url, source.selectors or {})
    if len(records) > MAX_ITEMS:
        raise ValueError(f"Source produced more than {MAX_ITEMS} items")
    return records, body


def _safe_route(url: str) -> bool:
    try:
        _check_target(url)
        return True
    except (ValueError, OSError):
        return False
